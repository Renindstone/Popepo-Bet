"""Un host que no acepta conexiones se da por caído un rato: las demás descargas no esperan sus reintentos."""

import httpx
import pytest

from apuestas.ingest import http
from apuestas.services.queries import failure_reason


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.setattr(http.time, "sleep", lambda s: None)  # sin esperas entre reintentos

    def build(handler):
        calls = []

        def counting(request):
            calls.append(request.url.host)
            return handler(request)

        c = http.PoliteClient(min_interval=0, cache_dir=tmp_path)
        c._client = httpx.Client(transport=httpx.MockTransport(counting))
        return c, calls

    return build


def down(request):
    raise httpx.ConnectTimeout("timed out", request=request)


def test_host_that_does_not_connect_is_skipped_until_the_pause_ends(make_client, monkeypatch):
    c, calls = make_client(down)
    with pytest.raises(http.SourceUnavailable):
        c.get_bytes("https://www.football-data.co.uk/mmz4281/2627/E0.csv", ttl=0)
    assert len(calls) == 3  # los tres reintentos de siempre

    # El siguiente archivo del mismo host falla al momento, sin tocar la red
    with pytest.raises(http.SourceUnavailable, match="se vuelve a probar"):
        c.get_bytes("https://www.football-data.co.uk/mmz4281/2627/D1.csv", ttl=0)
    assert len(calls) == 3

    # Pasada la pausa, se vuelve a probar
    now = http.time.monotonic()
    monkeypatch.setattr(http.time, "monotonic", lambda: now + http.HOST_DOWN_PAUSE + 1)
    with pytest.raises(http.SourceUnavailable):
        c.get_bytes("https://www.football-data.co.uk/mmz4281/2627/SP1.csv", ttl=0)
    assert len(calls) == 6


def test_other_hosts_are_not_affected(make_client):
    def handler(request):
        if request.url.host == "www.football-data.co.uk":
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, content=b"ok")

    c, _ = make_client(handler)
    with pytest.raises(http.SourceUnavailable):
        c.get_bytes("https://www.football-data.co.uk/fixtures.csv", ttl=0)
    assert c.get_bytes("https://www.fotmob.com/api/leagues", ttl=0) == b"ok"


def test_slow_server_errors_do_not_mark_the_host_down(make_client):
    c, calls = make_client(lambda request: httpx.Response(503))
    with pytest.raises(RuntimeError) as err:
        c.get_bytes("https://understat.com/league/EPL", ttl=0)
    assert not isinstance(err.value, http.SourceUnavailable)
    with pytest.raises(RuntimeError):
        c.get_bytes("https://understat.com/league/EPL", ttl=0)
    assert len(calls) == 6  # se reintenta en cada descarga: conecta, solo responde mal


@pytest.mark.parametrize("error, reason", [
    (None, None),
    ("No se pudo descargar https://www.football-data.co.uk/mmz4281/2627/E0.csv: timed out\nTraceback ...",
     "El sitio no responde"),
    ("www.football-data.co.uk no responde; se vuelve a probar en 29 min", "El sitio no responde"),
    ("Interrumpida al reiniciar el worker", "Interrumpida al reiniciar el worker"),
])
def test_failure_reason_is_one_short_line(error, reason):
    assert failure_reason(error) == reason
