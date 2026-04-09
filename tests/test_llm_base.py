"""
tests/test_llm_base.py — Unit tests for llm/base.py (retry decorator).
"""

import pytest
from unittest.mock import patch
from llm.base import retry_on_transient, LLMResponse


class FakeAPIError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"API error {status_code}")


class TestRetryOnTransient:
    def test_no_retry_on_success(self):
        call_count = 0

        @retry_on_transient(max_retries=3, backoff=(0, 0, 0))
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count == 1

    def test_retries_on_429(self):
        call_count = 0

        @retry_on_transient(max_retries=3, backoff=(0, 0, 0), retryable_codes={429})
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise FakeAPIError(429)
            return "ok"

        with patch("time.sleep"):
            assert fail_then_succeed() == "ok"
            assert call_count == 3

    def test_raises_non_retryable_immediately(self):
        @retry_on_transient(max_retries=3, backoff=(0, 0, 0), retryable_codes={429})
        def fail_400():
            raise FakeAPIError(400)

        with pytest.raises(FakeAPIError):
            fail_400()

    def test_raises_after_max_retries(self):
        @retry_on_transient(max_retries=2, backoff=(0, 0), retryable_codes={502})
        def always_fail():
            raise FakeAPIError(502)

        with patch("time.sleep"):
            with pytest.raises(FakeAPIError):
                always_fail()

    def test_non_api_exceptions_propagate(self):
        @retry_on_transient(max_retries=3, backoff=(0, 0, 0))
        def runtime_error():
            raise RuntimeError("not an API error")

        with pytest.raises(RuntimeError, match="not an API error"):
            runtime_error()
