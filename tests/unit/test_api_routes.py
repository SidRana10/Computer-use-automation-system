"""P6: the HTTP capability API — same request/response contract a caller
would see, built with a FakeRunner so no Playwright/live MERIDIAN traffic is
needed to test routing, status codes, and the invoke/run-lookup contract.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from ui_capabilities.api.app import build_app
from ui_capabilities.models.results import SuccessResult

from _api_test_support import make_service


def _success(artifact, inputs):
    return SuccessResult(
        run_id="api-route-test-1",
        capability_id=artifact.capability_id,
        capability_version=artifact.capability_version,
        outputs={"shares": [{"share": "100234-S0001-12", "balance": "1,234.56"}]},
    )


def _client(tmp_path, result_fn=_success):
    service, runner = make_service(tmp_path, result_fn)
    return TestClient(build_app(service)), runner


def test_list_capabilities_returns_all_seven(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 7
    ids = {c["capability_id"] for c in body}
    assert "meridian.get_member_balances" in ids
    assert "meridian.funds_transfer" in ids


def test_get_capability_detail_excludes_credentials(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/api/capabilities/meridian.get_member_balances")
    assert response.status_code == 200
    body = response.json()
    names = {i["name"] for i in body["inputs"]}
    assert names == {"member_number"}


def test_get_unknown_capability_is_404(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/api/capabilities/meridian.does_not_exist")
    assert response.status_code == 404


def test_invoke_unknown_capability_is_404_before_runner_touched(tmp_path):
    client, runner = _client(tmp_path)
    response = client.post("/api/capabilities/meridian.does_not_exist/invoke", json={"inputs": {}})
    assert response.status_code == 404
    assert runner.calls == []


def test_invoke_rejecting_credential_field_is_400_before_runner_touched(tmp_path):
    client, runner = _client(tmp_path)
    response = client.post(
        "/api/capabilities/meridian.get_member_balances/invoke",
        json={"inputs": {"member_number": "100234", "password": "hunter2"}},
    )
    assert response.status_code == 400
    assert runner.calls == []


def test_invoke_rejecting_human_approved_override_is_400(tmp_path):
    client, runner = _client(tmp_path)
    response = client.post(
        "/api/capabilities/meridian.get_member_balances/invoke",
        json={"inputs": {"member_number": "100234", "human_approved": True}},
    )
    assert response.status_code == 400
    assert runner.calls == []


def test_invoke_with_missing_required_input_returns_structured_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, runner = _client(tmp_path)
    response = client.post("/api/capabilities/meridian.get_member_balances/invoke", json={"inputs": {}})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failure"
    assert body["code"] == "INVOCATION_INVALID"
    assert runner.calls == []


def test_invoke_success_is_visible_via_run_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, runner = _client(tmp_path)

    response = client.post(
        "/api/capabilities/meridian.get_member_balances/invoke",
        json={"inputs": {"member_number": "100234"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    run_id = body["run_id"]
    assert len(runner.calls) == 1

    run_response = client.get(f"/api/runs/{run_id}")
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["capability_id"] == "meridian.get_member_balances"
    assert run_body["inputs"]["member_number"] == "[REDACTED]"

    list_response = client.get("/api/runs")
    assert any(r["run_id"] == run_id for r in list_response.json())


def test_get_unknown_run_is_404(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/api/runs/no-such-run")
    assert response.status_code == 404


def test_evidence_path_traversal_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, _ = _client(tmp_path)
    invoke_response = client.post(
        "/api/capabilities/meridian.get_member_balances/invoke",
        json={"inputs": {"member_number": "100234"}},
    )
    run_id = invoke_response.json()["run_id"]
    response = client.get(f"/api/runs/{run_id}/evidence/../../../etc/passwd")
    assert response.status_code == 404
