"""OpenAPI contract smoke — app exports expected paths."""

from __future__ import annotations

from fastapi.testclient import TestClient

from source_extract.api.app import create_app


def test_openapi_has_core_paths() -> None:
    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/commands" in paths
    assert "/api/v1/jobs" in paths
    assert "/api/v1/models/ocr-region" in paths
    assert "/api/v1/review/sessions" in paths


def test_health_ok() -> None:
    client = TestClient(create_app())
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
