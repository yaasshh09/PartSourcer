"""Registry, fan-out, merge, and status. The layer routes will see.

An adapter knows one distributor. This knows that there are three of them,
that any of them can be missing or broken, and that saying so plainly is
better than a 502 when two of them answered.
"""

ALL_DISTRIBUTORS: tuple[str, ...] = ("lcsc", "mouser", "digikey")

NO_CREDENTIALS = "no credentials configured"


def disabled_reasons(settings) -> dict[str, str]:
    """Which distributors are off, and why. Absent means enabled.

    Enablement is derived from secrets rather than declared in config, so
    the deployed app behaves exactly as it does today until a key exists,
    and DigiKey stays dark with no code branch.
    """
    off: dict[str, str] = {}
    if not settings.mouser_api_key:
        off["mouser"] = NO_CREDENTIALS
    if not (settings.digikey_client_id and settings.digikey_client_secret):
        off["digikey"] = NO_CREDENTIALS
    return off
