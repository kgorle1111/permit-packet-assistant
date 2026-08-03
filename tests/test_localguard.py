"""The localhost guard: DNS rebinding (bad Host) and cross-origin browser
requests (bad Origin) get 403; normal local traffic passes untouched."""

from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_rebound_host_rejected():
    r = client.get("/health", headers={"Host": "evil.example.com:5070"})
    assert r.status_code == 403


def test_cross_origin_rejected():
    r = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403


def test_local_origin_passes():
    assert client.get("/health", headers={"Origin": "http://localhost:5070"}).status_code == 200


def test_no_origin_passes():
    assert client.get("/health").status_code == 200
