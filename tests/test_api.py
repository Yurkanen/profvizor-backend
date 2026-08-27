from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _visualize(sample_photo_bytes, **overrides):
    data = {
        "profileType": "picket-solid",
        "ralCode": "RAL 6005",
        "heightM": "2.0",
        "leftPct": "10",
        "widthPct": "76",
    }
    data.update(overrides)
    files = {"photo": ("photo.jpg", sample_photo_bytes, "image/jpeg")}
    return client.post("/api/visualize", data=data, files=files)


def test_config_returns_reference_data():
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert {p["id"] for p in body["profiles"]} == {
        "corrugated", "louvre", "picket-gap", "picket-solid",
    }
    assert any(r["code"] == "RAL 6005" for r in body["ralPalette"])


def test_visualize_happy_path_with_mock_provider(sample_photo_bytes):
    resp = _visualize(sample_photo_bytes)
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "mock"
    assert body["imageBase64"]
    assert body["generationMs"] >= 0
    assert "requestId" in body


def test_visualize_rejects_unknown_profile(sample_photo_bytes):
    resp = _visualize(sample_photo_bytes, profileType="does-not-exist")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"


def test_visualize_rejects_unknown_ral(sample_photo_bytes):
    resp = _visualize(sample_photo_bytes, ralCode="RAL 0000")
    assert resp.status_code == 400


def test_visualize_rejects_height_out_of_range(sample_photo_bytes):
    resp = _visualize(sample_photo_bytes, heightM="9.9")
    assert resp.status_code == 400


def test_visualize_rejects_non_image_upload():
    resp = client.post(
        "/api/visualize",
        data={
            "profileType": "picket-solid",
            "ralCode": "RAL 6005",
            "heightM": "2.0",
            "leftPct": "10",
            "widthPct": "76",
        },
        files={"photo": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


def test_visualize_missing_field_returns_error_shape_from_tz(sample_photo_bytes):
    # раздел 7 ТЗ: тело ошибки — {"error": {"code","message"}}, а не сырой {"detail": ...}
    resp = client.post(
        "/api/visualize",
        data={"profileType": "picket-solid", "ralCode": "RAL 6005", "leftPct": "10", "widthPct": "76"},
        files={"photo": ("photo.jpg", sample_photo_bytes, "image/jpeg")},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body and "detail" not in body
    assert body["error"]["code"] == "bad_request"


def test_daily_limit_returns_429(sample_photo_bytes):
    # DAILY_LIMIT=3 задан в conftest через переменную окружения
    for _ in range(3):
        assert _visualize(sample_photo_bytes).status_code == 200
    resp = _visualize(sample_photo_bytes)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limited"
