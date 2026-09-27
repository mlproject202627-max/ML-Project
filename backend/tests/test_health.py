import pytest
from fastapi.testclient import TestClient


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_health_is_liveness_only(client):
    """`/health` must not report model state (spec §29).

    Detection model availability is a readiness question. Reporting it here
    meant a fresh, entirely functional install described itself as degraded
    purely because no model had been trained yet — and an orchestrator reading
    that would have pulled a healthy process out of rotation.
    """
    data = client.get("/health").json()
    assert "ml_model" not in data
    assert "anomalyModel" not in data


def test_readiness_reports_untrained_model_without_failing(client):
    """An untrained model lowers precision, not availability.

    The rule engine needs no training and still fills the alert queue, so
    "untrained" must not be reported as "not ready". This test runs against an
    empty database with no model artefact, which is exactly that state.
    """
    response = client.get("/ready")
    assert response.status_code == 200

    data = response.json()
    assert data["database"] == "ready"
    assert data["anomalyModel"] in {"ready", "untrained"}
    # The decisive assertion: a database-only failure is what makes us unready.
    expected = "ready" if data["database"] == "ready" else "not_ready"
    assert data["status"] == expected


def test_readiness_reports_the_detector_that_scores_risk(client):
    """`/ready` must report the model wired into the risk engine.

    It previously reported `ml.inference` — a fixed-weight stub used by the
    ingestion path that contributes to no alert, and whose `model_version` was
    "sentinel-ueba-v1". An operator reading it learned about the wrong model.
    """
    data = client.get("/ready").json()
    assert "modelTrainingRows" in data
    assert isinstance(data["modelTrainingRows"], int)
    assert "model_version" not in data
    assert "sentinel-ueba-v1" not in str(data)


def test_root(client):
    """Test root endpoint."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Sentinel"
    assert data["version"] == "1.0.0"


def test_docs_available(client):
    """Test OpenAPI docs are available."""
    response = client.get("/docs")
    assert response.status_code == 200
