"""P8: the dashboard is read-only — catalog and run history/detail render,
credential fields never appear as invokable rows, and there is no form on
any page that could mutate state or drive the browser."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from ui_capabilities.api.app import build_app
from ui_capabilities.models.results import FailureResult, SuccessResult

from _api_test_support import make_service


def _success(artifact, inputs):
    return SuccessResult(
        run_id="dash-test-1",
        capability_id=artifact.capability_id,
        capability_version=artifact.capability_version,
        outputs={"shares": [{"share": "100234-S0001-12", "balance": "1,234.56"}]},
    )


def _client(tmp_path, result_fn=_success):
    service, runner = make_service(tmp_path, result_fn)
    return TestClient(build_app(service)), service


def test_catalog_page_lists_capabilities(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "meridian.get_member_balances" in response.text
    assert "meridian.funds_transfer" in response.text


def test_catalog_page_has_no_mutating_form(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/dashboard")
    assert "<form" not in response.text.lower()


def test_capability_detail_page_never_lists_credential_inputs_as_rows(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/dashboard/capabilities/meridian.get_member_balances")
    assert response.status_code == 200
    html = response.text
    assert '<td class="mono">operator_id</td>' not in html
    assert '<td class="mono">password</td>' not in html
    assert '<td class="mono">branch</td>' not in html
    assert '<td class="mono">member_number</td>' in html


def test_unknown_capability_detail_is_404(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/dashboard/capabilities/meridian.does_not_exist")
    assert response.status_code == 404


def test_run_history_and_detail_render_after_an_invocation(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, service = _client(tmp_path)

    result = asyncio.run(service.invoke("meridian.get_member_balances", {"member_number": "100234"}))

    history = client.get("/dashboard/runs")
    assert history.status_code == 200
    assert result.run_id in history.text

    detail = client.get(f"/dashboard/runs/{result.run_id}")
    assert detail.status_code == 200
    assert "success" in detail.text
    assert "[REDACTED]" in detail.text  # member_number is sensitive
    assert "<form" not in detail.text.lower()


def test_unknown_run_detail_is_404(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/dashboard/runs/no-such-run")
    assert response.status_code == 404


def test_run_detail_renders_failure_result_clearly(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")

    def _failure(artifact, inputs):
        return FailureResult(
            run_id="dash-test-failure",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            code="TARGET_NOT_FOUND",
            expected="a resolvable control",
            observed="no matching element",
        )

    client, service = _client(tmp_path, _failure)
    result = asyncio.run(service.invoke("meridian.get_member_balances", {"member_number": "100234"}))
    detail = client.get(f"/dashboard/runs/{result.run_id}")
    assert detail.status_code == 200
    assert "TARGET_NOT_FOUND" in detail.text
    assert "no matching element" in detail.text
