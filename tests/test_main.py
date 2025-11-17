import io
import pytest
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

class DummyResp:
    def __init__(self, ok=True, status_code=200, text="", data=None):
        self.ok = ok
        self.status_code = status_code
        self.text = text
        self._data = data or {}

    def json(self):
        return self._data


def make_file(content: str):
    return {"csv_file": ("hospitals.csv", content, "text/csv")}


def test_validate_csv_ok():
    csv = "name,address,phone\nAlpha,Addr1,123\nBeta,Addr2,456\n"
    resp = client.post("/hospitals/bulk/validate", files=make_file(csv))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "valid"
    assert body["count"] == 2


def test_validate_csv_missing_header():
    csv = "name,phone\nAlpha,123\n"
    resp = client.post("/hospitals/bulk/validate", files=make_file(csv))
    assert resp.status_code == 400
    assert "missing required headers" in resp.json()["detail"].lower() or "missing required headers" in resp.json()["detail"]


def test_bulk_create_success(monkeypatch):
    csv = "name,address,phone\nAlpha,Addr1,123\nBeta,Addr2,456\n"

    def fake_post(url, json=None, timeout=None):
        # return a created response
        return DummyResp(ok=True, status_code=201, data={"id": f"id-{json['name']}"})

    def fake_patch(url, timeout=None):
        return DummyResp(ok=True, status_code=200)

    monkeypatch.setattr(main.requests, "post", fake_post)
    monkeypatch.setattr(main.requests, "patch", fake_patch)

    resp = client.post("/hospitals/bulk", files=make_file(csv))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hospitals"] == 2
    assert body["processed_hospitals"] == 2
    assert body["failed_hospitals"] == 0
    assert body["batch_activated"] is True
    assert len(body["hospitals"]) == 2


def test_bulk_create_partial_failure(monkeypatch):
    csv = "name,address,phone\nAlpha,Addr1,123\nBadRow,,\n"

    # first call succeeds, second returns non-ok
    def fake_post(url, json=None, timeout=None):
        if json.get("name") == "Alpha":
            return DummyResp(ok=True, status_code=201, data={"id": "id-Alpha"})
        return DummyResp(ok=False, status_code=400, text="bad data")

    def fake_patch(url, timeout=None):
        return DummyResp(ok=False, status_code=500, text="activate failed")

    monkeypatch.setattr(main.requests, "post", fake_post)
    monkeypatch.setattr(main.requests, "patch", fake_patch)

    resp = client.post("/hospitals/bulk", files=make_file(csv))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hospitals"] == 2
    assert body["processed_hospitals"] == 1
    assert body["failed_hospitals"] == 1
    assert body["batch_activated"] is False
    assert body.get("failures") is not None
