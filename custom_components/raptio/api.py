"""Async client for the RAPT cloud API."""

from __future__ import annotations

import time
from typing import Any

import aiohttp

from .const import API_URL, ENDPOINTS, LOGGER, STATE_FIELDS, TOKEN_URL

TIMEOUT = aiohttp.ClientTimeout(total=30)


class RaptApiError(Exception):
    """The RAPT API could not be reached or returned an error."""


class RaptAuthError(RaptApiError):
    """The email or API secret was rejected."""


class RaptClient:
    """Minimal read-only RAPT API client."""

    def __init__(self, session: aiohttp.ClientSession, email: str, secret: str) -> None:
        self._session = session
        self._email = email
        self._secret = secret
        self._token: str | None = None
        self._token_expiry = 0.0

    async def async_authenticate(self) -> str:
        """Return a bearer token, requesting a new one if the cached one is stale."""
        if self._token and time.monotonic() < self._token_expiry - 60:
            return self._token

        payload = {
            "client_id": "rapt-user",
            "grant_type": "password",
            "username": self._email,
            "password": self._secret,
        }
        try:
            async with self._session.post(TOKEN_URL, data=payload, timeout=TIMEOUT) as resp:
                if resp.status in (400, 401):
                    raise RaptAuthError("Invalid email or API secret")
                resp.raise_for_status()
                body = await resp.json(content_type=None)
            self._token = body["access_token"]
            self._token_expiry = time.monotonic() + int(body.get("expires_in", 3600))
        except (aiohttp.ClientError, TimeoutError, KeyError, TypeError, ValueError) as err:
            raise RaptApiError(f"Token request failed: {err!r}") from err
        return self._token

    async def _get(self, endpoint: str, token: str) -> list[dict[str, Any]]:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        try:
            async with self._session.get(
                API_URL + endpoint, headers=headers, timeout=TIMEOUT
            ) as resp:
                if resp.status == 401:
                    self._token = None
                resp.raise_for_status()
                return await resp.json(content_type=None) or []
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise RaptApiError(f"{endpoint} failed: {err!r}") from err

    async def async_get_devices(self) -> dict[str, dict[str, Any]]:
        """Return every device on the account, keyed by device id."""
        token = await self.async_authenticate()

        devices: dict[str, dict[str, Any]] = {}
        failures = 0
        for endpoint, model in ENDPOINTS.items():
            try:
                items = await self._get(endpoint, token)
            except RaptApiError as err:
                LOGGER.debug("%s", err)
                failures += 1
                continue
            for item in items:
                if not item.get("id") or item.get("deleted"):
                    continue
                device = {k: item[k] for k in STATE_FIELDS if k in item}
                device["model"] = model
                devices[item["id"]] = device

        if failures == len(ENDPOINTS):
            raise RaptApiError("Every RAPT API endpoint failed")
        return devices
