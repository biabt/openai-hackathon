"""Minimal SPTrans client tests."""

from __future__ import annotations

import httpx
import pytest

from city_os.integrations.sptrans import SPTransClient, SPTransError


def test_fetch_vehicle_positions_authenticates_and_returns_payload() -> None:
    requests: list[httpx.Request] = []
    payload = {"hr": "11:30", "l": [{"cl": 33887, "vs": []}]}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/Login/Autenticar"):
            assert request.method == "POST"
            assert request.url.params["token"] == "server-key"
            return httpx.Response(
                200, json=True, headers={"set-cookie": "session=abc; Path=/"}
            )
        assert request.url.path.endswith("/Posicao")
        assert request.headers["cookie"] == "session=abc"
        return httpx.Response(200, json=payload)

    with SPTransClient(
        "server-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ) as client:
        assert client.fetch_vehicle_positions() == payload

    assert len(requests) == 2


def test_from_env_requires_server_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPTRANS_API_KEY", raising=False)

    with pytest.raises(SPTransError, match="SPTRANS_API_KEY"):
        SPTransClient.from_env()


def test_rejected_key_does_not_leak_secret() -> None:
    client = SPTransClient(
        "do-not-leak",
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=False))
        ),
    )

    with pytest.raises(SPTransError) as captured:
        client.fetch_vehicle_positions()

    assert "do-not-leak" not in str(captured.value)


def test_unexpected_payload_is_rejected() -> None:
    responses = iter([httpx.Response(200, json=True), httpx.Response(200, json=[])])
    client = SPTransClient(
        "server-key",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: next(responses))),
    )

    with pytest.raises(SPTransError, match="unexpected"):
        client.fetch_vehicle_positions()
