"""Minimal server-side client for SPTrans Olho Vivo vehicle positions."""

from __future__ import annotations

import os
from typing import Any, Self

import httpx

DEFAULT_BASE_URL = "https://api.olhovivo.sptrans.com.br/v2.1"


class SPTransError(RuntimeError):
    """Raised when the SPTrans integration cannot return vehicle positions."""


class SPTransClient:
    """Fetch citywide vehicle positions using a server-side application key."""

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.Client | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        if not api_key.strip():
            raise ValueError("SPTrans API key must not be empty")
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.Client(timeout=15.0)

    @classmethod
    def from_env(cls, **kwargs: Any) -> SPTransClient:
        """Create the client from the server-only ``SPTRANS_API_KEY`` variable."""
        api_key = os.environ.get("SPTRANS_API_KEY", "").strip()
        if not api_key:
            raise SPTransError("SPTRANS_API_KEY is required")
        return cls(api_key, **kwargs)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._http.close()

    def fetch_vehicle_positions(self) -> dict[str, Any]:
        """Authenticate with SPTrans and return the current ``/Posicao`` payload."""
        try:
            authenticated = self._http.post(
                f"{self._base_url}/Login/Autenticar",
                params={"token": self._api_key},
            )
            authenticated.raise_for_status()
            if authenticated.json() is not True:
                raise SPTransError("SPTrans rejected the application key")

            response = self._http.get(f"{self._base_url}/Posicao")
            response.raise_for_status()
            payload = response.json()
        except SPTransError:
            raise
        except (httpx.HTTPError, ValueError):
            raise SPTransError("SPTrans vehicle-position request failed") from None

        if not isinstance(payload, dict) or not isinstance(payload.get("l"), list):
            raise SPTransError("SPTrans returned an unexpected vehicle-position payload")
        return payload
