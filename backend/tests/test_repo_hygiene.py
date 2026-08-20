"""Guards for the things that are true today and would break quietly.

A one-off audit finds a leaked key once. These are the same checks written
down so the next commit has to keep passing them: no secret in the repo, no
caller-controlled string reaching a SQL statement, no cookie appearing in an
app that has no session to protect.
"""

import ast
import re
import subprocess
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent

SOURCE_DIRS = ("api", "cache", "history", "models", "services")


def backend_sources() -> list[Path]:
    files = [BACKEND / "main.py", BACKEND / "config.py", BACKEND / "security.py"]
    for name in SOURCE_DIRS:
        files.extend(sorted((BACKEND / name).rglob("*.py")))
    return files


def git(*args: str) -> str:
    try:
        return subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                              text=True, timeout=30, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git is not available here")


# --------------------------------------------------------------------------
# Secrets
# --------------------------------------------------------------------------

def test_no_env_file_is_tracked_except_the_examples():
    tracked = [line for line in git("ls-files").splitlines()
               if Path(line).name.startswith(".env")]
    assert sorted(tracked) == ["backend/.env.example", "frontend/.env.example"]


def test_the_real_env_files_are_actually_ignored():
    """Ignored by pattern, not merely absent from this checkout."""
    for candidate in ("backend/.env", ".env.local", "frontend/.env"):
        result = subprocess.run(("git", "check-ignore", "-q", candidate),
                                cwd=ROOT, capture_output=True)
        assert result.returncode == 0, f"{candidate} is not gitignored"


def test_example_env_files_carry_no_filled_in_values():
    """An example that ships a real value is the leak, not the .env."""
    secret_keys = ("API_KEY", "CLIENT_SECRET", "RECORDER_TOKEN", "DATABASE_URL",
                   "CLIENT_ID")
    for example in (ROOT / "backend/.env.example", ROOT / "frontend/.env.example"):
        for line in example.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if any(key in name for key in secret_keys):
                assert value.strip() == "", f"{name} has a value in {example.name}"


def test_no_source_file_hardcodes_a_credential():
    """Credentials arrive from settings, never from a literal in the tree."""
    assignment = re.compile(
        r"""(api_key|apikey|client_secret|password|recorder_token|database_url)"""
        r"""\s*[:=]\s*["'][^"']{8,}["']""", re.IGNORECASE)
    for path in backend_sources():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            assert not assignment.search(line), f"{path.name}:{number}: {line.strip()}"


def test_no_secret_is_exposed_to_the_browser_bundle():
    """Vite inlines every VITE_-prefixed variable into public JavaScript."""
    frontend = ROOT / "frontend"
    referenced = set()
    for path in (frontend / "src").rglob("*.js*"):
        referenced.update(re.findall(r"import\.meta\.env\.(\w+)",
                                     path.read_text(encoding="utf-8")))
    assert referenced <= {"VITE_API_BASE"}, referenced
    example = (frontend / ".env.example").read_text(encoding="utf-8")
    assert re.findall(r"^VITE_\w+", example, re.MULTILINE) == ["VITE_API_BASE"]


# --------------------------------------------------------------------------
# SQL
# --------------------------------------------------------------------------

SQL_WORDS = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|FROM|WHERE|VALUES)\b")

#: The only names any SQL string is allowed to interpolate.
#:
#: "table" is bound by iterating a module-level tuple of literal table names,
#: which a caller cannot reach. "marks" and "clause" are variable-length
#: placeholder runs for an IN list and an OR list: their content is question
#: marks and nothing else, and their *length* is the only thing caller data
#: influences. A variable-length IN clause has no other correct spelling, so
#: they are allowed here and pinned by the test below. Everything else must be
#: a bound parameter.
ALLOWED_PLACEHOLDERS = {"table", "marks", "clause"}

#: Names from ALLOWED_PLACEHOLDERS that must be built out of literal
#: placeholders rather than out of anything a caller supplied.
PLACEHOLDER_BUILDERS = ("marks", "clause")


def test_no_sql_string_interpolates_anything_but_a_fixed_table_name():
    for path in backend_sources():
        source = path.read_text(encoding="utf-8")
        for literal in re.findall(r'f"([^"]*)"|f\'([^\']*)\'', source):
            text = literal[0] or literal[1]
            if not SQL_WORDS.search(text):
                continue
            names = {p.split(".")[0].split("[")[0].strip()
                     for p in re.findall(r"\{([^}]*)\}", text)}
            assert names <= ALLOWED_PLACEHOLDERS, f"{path.name}: {text!r}"


def test_the_variable_length_clauses_are_built_from_question_marks_only():
    """The one place an interpolated name is allowed, held to how it is made.

    Parsed rather than grepped because these assignments wrap across lines,
    and a line-based guard would quietly stop looking. If one of them ever
    starts joining values instead of placeholders, the IN clause becomes an
    injection point and the test above would wave it through on the name.
    """
    seen = 0
    for path in backend_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if not names & set(PLACEHOLDER_BUILDERS):
                continue
            seen += 1
            expression = ast.unparse(node.value)
            # Every string literal in the expression must be punctuation and
            # placeholders: no column value, no caller input, no f-string.
            literals = [n.value for n in ast.walk(node.value)
                        if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            assert literals, expression
            assert any("?" in text for text in literals), expression
            assert not any(isinstance(n, ast.JoinedStr) for n in ast.walk(node.value)),                 expression
            # Only the count may vary with caller data, never the content.
            assert "len(" in expression, expression
    assert seen >= 2, "the clause builders moved; this guard is now blind"


def test_no_sql_statement_is_built_by_concatenation_or_format():
    """The two other ways caller data gets into a statement."""
    suspicious = re.compile(r"""(execute|executemany|fetch|fetchrow|fetchval)"""
                            r"""\(\s*["'][^"']*["']\s*(\+|%|\.format)""")
    for path in backend_sources():
        source = path.read_text(encoding="utf-8")
        assert not suspicious.search(source), path.name


# --------------------------------------------------------------------------
# Blast radius
# --------------------------------------------------------------------------

def test_a_cache_schema_bump_cannot_drop_the_price_history():
    """The cache rebuilds itself for free. The history series does not.

    Bumping CACHE_SCHEMA_VERSION drops and recreates every name in the cache
    module's table tuple. The two history tables live in the same database, so
    the only thing standing between a routine version bump and losing a series
    nobody can re-fetch is that those names are absent from that tuple.
    """
    from cache.pg_store import _TABLES as PG_TABLES
    from cache.store import _CACHE_TABLES as SQLITE_TABLES

    history_source = (BACKEND / "history" / "store.py").read_text(encoding="utf-8")
    history_tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)",
                                    history_source))
    assert history_tables, "the history schema moved; this guard is now blind"
    assert history_tables.isdisjoint(PG_TABLES), history_tables & set(PG_TABLES)
    assert history_tables.isdisjoint(SQLITE_TABLES)
    # Prefix discipline is what keeps the two sets apart by construction.
    assert all(name.startswith("cache_") for name in PG_TABLES), PG_TABLES


# --------------------------------------------------------------------------
# Cookies
# --------------------------------------------------------------------------

def test_the_api_sets_no_cookies():
    """There is no session here. A cookie appearing means one was invented.

    If that ever changes, this test is the reminder that it needs Secure,
    HttpOnly and SameSite before it ships, and CSRF tokens behind it.
    """
    for path in backend_sources():
        source = path.read_text(encoding="utf-8")
        assert "set_cookie" not in source, path.name
        assert "Set-Cookie" not in source, path.name


def test_cors_never_allows_credentials():
    """Credentialed CORS is what turns a permissive origin into account theft."""
    main = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "allow_credentials=False" in main
    assert "allow_credentials=True" not in main
