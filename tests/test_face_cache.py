import time
from app.services.face_service import preload_known_encodings, clear_known_encodings


def test_preload_caches_and_respects_force(monkeypatch):
    calls = {"count": 0}

    def fake_loader():
        calls["count"] += 1
        return [(1, [0.1, 0.2, 0.3], 'p')]

    monkeypatch.setattr('app.services.face_service._load_all_known_encodings', fake_loader)
    clear_known_encodings()

    data1 = preload_known_encodings()
    assert calls["count"] == 1
    data2 = preload_known_encodings()
    assert calls["count"] == 1  # cached
    data3 = preload_known_encodings(force=True)
    assert calls["count"] == 2  # forced reload


def test_preload_respects_ttl(monkeypatch):
    calls = {"count": 0}

    def fake_loader():
        calls["count"] += 1
        return [(2, [0.4, 0.5, 0.6], 'q')]

    monkeypatch.setattr('app.services.face_service._load_all_known_encodings', fake_loader)
    clear_known_encodings()
    data1 = preload_known_encodings()
    assert calls["count"] == 1
    # simulate ttl expiry by waiting a short time and calling with tiny ttl
    data2 = preload_known_encodings(ttl_seconds=0)
    assert calls["count"] == 2
