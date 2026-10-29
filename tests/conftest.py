import pytest

from apuestas.ingest import oddspapi


@pytest.fixture(autouse=True)
def no_oddspapi(monkeypatch):
    """Ninguna prueba llama a OddsPapi de verdad: cada llamada gasta cupo (250 al mes). Las que lo necesitan lo simulan."""

    def blocked(path, ttl, **params):
        raise RuntimeError(f"Una prueba intentó llamar a OddsPapi ({path}); simula `oddspapi._get`")

    monkeypatch.setattr(oddspapi, "_get", blocked)
