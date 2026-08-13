from types import SimpleNamespace

import httpx

from services.part_service import build_part_service


def cfg(mouser=None, dk_id=None, dk_secret=None):
    return SimpleNamespace(
        mouser_api_key=mouser, digikey_client_id=dk_id,
        digikey_client_secret=dk_secret,
        mouser_base_url="https://api.mouser.test",
        digikey_base_url="https://api.digikey.test",
        distributor_timeout_secs=3.0)


def test_with_no_keys_only_lcsc_is_registered_and_no_client_is_created():
    lcsc = httpx.AsyncClient()
    service, created = build_part_service(cfg(), lcsc)
    assert set(service.adapter_names()) == {"lcsc"}
    assert created == []
    assert set(service.disabled_names()) == {"mouser", "digikey"}


def test_a_mouser_key_registers_mouser_and_its_client():
    lcsc = httpx.AsyncClient()
    service, created = build_part_service(cfg(mouser="k"), lcsc)
    assert set(service.adapter_names()) == {"lcsc", "mouser"}
    assert len(created) == 1
    assert str(created[0].base_url).startswith("https://api.mouser.test")


def test_full_credentials_register_all_three():
    lcsc = httpx.AsyncClient()
    service, created = build_part_service(cfg("k", "id", "sec"), lcsc)
    assert set(service.adapter_names()) == {"lcsc", "mouser", "digikey"}
    assert len(created) == 2
    assert service.disabled_names() == []


def test_the_configured_timeout_reaches_the_service():
    lcsc = httpx.AsyncClient()
    service, _ = build_part_service(cfg(), lcsc)
    assert service.timeout_secs == 3.0
