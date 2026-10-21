"""La API solo confía sin clave en peticiones hechas desde la propia máquina, nunca en las que llegan por un túnel."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from apuestas.api.app import current_user, is_local
from apuestas.config import get_settings


def request(client="127.0.0.1", **headers):
    raw = [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "client": (client, 50000), "headers": raw})


def test_local_request_without_key_is_the_owner():
    assert is_local(request())
    assert current_user(request(), x_api_key=None) == get_settings().default_user


@pytest.mark.parametrize("headers", [
    {"x_forwarded_for": "190.12.3.4"},       # ngrok, cloudflared
    {"cf_connecting_ip": "190.12.3.4"},      # túnel de Cloudflare
    {"forwarded": "for=190.12.3.4"},
])
def test_tunneled_request_needs_a_key(headers):
    assert not is_local(request(**headers))
    with pytest.raises(HTTPException) as exc:
        current_user(request(**headers), x_api_key=None)
    assert exc.value.status_code == 401


def test_remote_client_needs_a_key():
    assert not is_local(request(client="192.168.1.20"))
