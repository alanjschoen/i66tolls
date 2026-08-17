"""Rate-limited HTTP client for vai66tolls.com."""

from __future__ import annotations

import random
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from i66tolls.api import BASE_URL

FetchFn = Callable[[str, dict[str, str]], str]


def _raw_fetch(handler: str, params: dict[str, str]) -> str:
    query = urlencode({"handler": handler, **params})
    with urlopen(f"{BASE_URL}?{query}", timeout=30) as response:
        return response.read().decode()


def _is_transient_error(error: BaseException) -> bool:
    if isinstance(error, HTTPError):
        return error.code >= 500
    return isinstance(error, (TimeoutError, URLError))


class RateLimitedClient:
    def __init__(
        self,
        *,
        delay: float = 0.1,
        jitter: float = 0.2,
        max_retries: int = 3,
        fetch: FetchFn = _raw_fetch,
    ) -> None:
        self.delay = delay
        self.jitter = jitter
        self.max_retries = max_retries
        self._fetch = fetch
        self._last_request_at = 0.0

    def _wait(self) -> None:
        pause = self.delay + random.uniform(0, self.jitter)
        elapsed = time.monotonic() - self._last_request_at
        remaining = pause - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def fetch(self, handler: str, params: dict[str, str]) -> str:
        attempt = 0
        while True:
            self._wait()
            try:
                body = self._fetch(handler, params)
            except BaseException as error:
                if not _is_transient_error(error) or attempt >= self.max_retries:
                    raise
                attempt += 1
                time.sleep(self.delay * (2**attempt))
                continue
            self._last_request_at = time.monotonic()
            return body
