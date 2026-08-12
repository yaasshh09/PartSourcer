from types import SimpleNamespace

from services.part_service import ALL_DISTRIBUTORS, disabled_reasons


def cfg(mouser=None, dk_id=None, dk_secret=None):
    return SimpleNamespace(mouser_api_key=mouser, digikey_client_id=dk_id,
                           digikey_client_secret=dk_secret)


def test_lcsc_needs_no_credentials_and_is_never_disabled():
    assert "lcsc" not in disabled_reasons(cfg())


def test_with_no_keys_only_lcsc_is_enabled():
    off = disabled_reasons(cfg())
    assert set(off) == {"mouser", "digikey"}
    assert off["mouser"] == "no credentials configured"


def test_a_mouser_key_enables_mouser_alone():
    off = disabled_reasons(cfg(mouser="k"))
    assert "mouser" not in off
    assert "digikey" in off


def test_digikey_needs_both_halves_of_the_credential():
    assert "digikey" in disabled_reasons(cfg(dk_id="id"))
    assert "digikey" in disabled_reasons(cfg(dk_secret="sec"))
    assert "digikey" not in disabled_reasons(cfg(dk_id="id", dk_secret="sec"))


def test_an_empty_string_key_counts_as_absent():
    off = disabled_reasons(cfg(mouser="", dk_id="", dk_secret=""))
    assert set(off) == {"mouser", "digikey"}


def test_a_whitespace_only_key_counts_as_absent():
    off = disabled_reasons(cfg(mouser="   ", dk_id=" ", dk_secret="\t"))
    assert set(off) == {"mouser", "digikey"}


def test_the_distributor_order_is_fixed():
    assert ALL_DISTRIBUTORS == ("lcsc", "mouser", "digikey")
