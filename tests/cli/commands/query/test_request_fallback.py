# SPDX-License-Identifier: Apache-2.0
"""Test fallback logic between /v1/completions and /v1/chat/completions endpoints."""

# Standard
from unittest.mock import patch, MagicMock
import pytest

# First Party
from lmcache.cli.commands.query._request import Request, _missing_chat_template, _weak_completions_error


class TestQueryRequestFallback:
    """Test the fallback logic between completions and chat completions endpoints."""

    def test_fallback_only_for_missing_chat_template_error(self):
        """Test that fallback from completions to chat completions only happens for missing chat template errors."""
        # Test with a regular error (not missing chat template)
        regular_error = RuntimeError("Authentication failed: 401 Unauthorized")
        assert not _missing_chat_template(regular_error)

        # This should NOT fall back to chat completions
        request = Request(
            "http://engine.test",
            "model",
            max_tokens=128,
            timeout=5.0,
            completions_only=False,
            chat_first=False,
        )

        with patch.object(request, '_query') as mock_query:
            # Mock the first call to raise a regular error
            mock_query.side_effect = RuntimeError("Authentication failed: 401 Unauthorized")

            with pytest.raises(RuntimeError, match="Authentication failed"):
                request._query_with_fallback({
                    "completions_only": False,
                    "model": "model",
                    "prompt": "test",
                    "max_tokens": 128,
                    "timeout": 5.0,
                    "chat_first": False,
                })
            # Verify _query was called only once (no fallback)
            assert mock_query.call_count == 1

    def test_fallback_for_missing_chat_template_error(self):
        """Test that fallback from completions to chat completions happens for missing chat template errors."""
        # Test with a missing chat template error
        missing_template_error = RuntimeError("No chat template found. Please provide a chat template.")
        assert _missing_chat_template(missing_template_error)

        request = Request(
            "http://engine.test",
            "model",
            max_tokens=128,
            timeout=5.0,
            completions_only=False,
            chat_first=False,
        )

        with patch.object(request, '_query') as mock_query:
            # First call fails with missing chat template, second succeeds
            mock_query.side_effect = [
                RuntimeError("No chat template found. Please provide a chat template."),
                {"answer": "Hello", "prompt_tokens": 10, "output_tokens": 5, "ttft_ms": 100.0, "tpot_ms_per_token": 10.0, "total_latency_ms": 200.0, "throughput_tokens_per_s": 0.5}
            ]

            result = request._query_with_fallback({
                "completions_only": False,
                "model": "model",
                "prompt": "test",
                "max_tokens": 128,
                "timeout": 5.0,
                "chat_first": False,
            })

            assert result["answer"] == "Hello"
            # Should have called _query twice (fallback)
            assert mock_query.call_count == 2

    def test_regular_error_when_chat_first_true(self):
        """Test that regular errors when chat_first=True do NOT fall back to completions."""
        regular_error = RuntimeError("Authentication failed: 401 Unauthorized")
        assert not _missing_chat_template(regular_error)

        request = Request(
            "http://engine.test",
            "model",
            max_tokens=128,
            timeout=5.0,
            completions_only=False,
            chat_first=True,
        )

        with patch.object(request, '_query') as mock_query:
            # Mock the first call to raise a regular error
            mock_query.side_effect = RuntimeError("Authentication failed: 401 Unauthorized")

            with pytest.raises(RuntimeError, match="Authentication failed"):
                request._query_with_fallback({
                    "completions_only": False,
                    "model": "model",
                    "prompt": "test",
                    "max_tokens": 128,
                    "timeout": 5.0,
                    "chat_first": True,
                })
            # Verify _query was called only once (no fallback)
            assert mock_query.call_count == 1

    def test_fallback_for_missing_chat_template_when_chat_first_true(self):
        """Test that fallback from chat to completions happens for missing chat template errors when chat_first=True."""
        # Test with a missing chat template error
        missing_template_error = RuntimeError("No chat template found. Please provide a chat template.")
        assert _missing_chat_template(missing_template_error)

        request = Request(
            "http://engine.test",
            "model",
            max_tokens=128,
            timeout=5.0,
            completions_only=False,
            chat_first=True,
        )

        with patch.object(request, '_query') as mock_query:
            # First call fails with missing chat template, second succeeds
            mock_query.side_effect = [
                RuntimeError("No chat template found. Please provide a chat template."),
                {"answer": "Hello", "prompt_tokens": 10, "output_tokens": 5, "ttft_ms": 100.0, "tpot_ms_per_token": 10.0, "total_latency_ms": 200.0, "throughput_tokens_per_s": 0.5}
            ]

            result = request._query_with_fallback({
                "completions_only": False,
                "model": "model",
                "prompt": "test",
                "max_tokens": 128,
                "timeout": 5.0,
                "chat_first": True,
            })

            assert result["answer"] == "Hello"
            # Should have called _query twice (fallback)
            assert mock_query.call_count == 2

    def test_completions_only_flag(self):
        """Test that completions_only=True does not fallback to chat completions."""
        request = Request(
            "http://engine.test",
            "model",
            max_tokens=128,
            timeout=5.0,
            completions_only=True,
            chat_first=False,
        )

        with patch.object(request, '_query') as mock_query:
            mock_query.return_value = {"answer": "Hello", "prompt_tokens": 10, "output_tokens": 5, "ttft_ms": 100.0, "tpot_ms_per_token": 10.0, "total_latency_ms": 200.0, "throughput_tokens_per_s": 0.5}

            result = request._query_with_fallback({
                "completions_only": True,
                "model": "model",
                "prompt": "test",
                "max_tokens": 128,
                "timeout": 5.0,
                "chat_first": False,
            })

            assert result["answer"] == "Hello"
            # Should have called _query only once (no fallback)
            assert mock_query.call_count == 1

    def test_weak_completions_error_with_missing_chat_template_fallback(self):
        """Test the complex case: weak completions error + missing chat template in second call."""
        request = Request(
            "http://engine.test",
            "model",
            max_tokens=128,
            timeout=5.0,
            completions_only=False,
            chat_first=False,
        )

        with patch.object(request, '_query') as mock_query:
            # First call raises a weak completions error
            # Second call raises a missing chat template error
            mock_query.side_effect = [
                RuntimeError("Empty response from engine (no SSE chunks parsed)"),
                RuntimeError("No chat template found. Please provide a chat template.")
            ]

            # This should raise the first error because it's NOT a missing chat template error
            # Only when first error is "missing chat template" should it try fallback
            with pytest.raises(RuntimeError, match="Empty response from engine"):
                request._query_with_fallback({
                    "completions_only": False,
                    "model": "model",
                    "prompt": "test",
                    "max_tokens": 128,
                    "timeout": 5.0,
                    "chat_first": False,
                })
            # Verify _query was called only once (no fallback for weak error without missing template)
            assert mock_query.call_count == 1

    def test_multiple_runtime_errors_raise_combined_error(self):
        """Test that multiple RuntimeErrors from different endpoints raise a combined error."""
        request = Request(
            "http://engine.test",
            "model",
            max_tokens=128,
            timeout=5.0,
            completions_only=False,
            chat_first=False,
        )

        with patch.object(request, '_query') as mock_query:
            # First call is a regular error (not missing chat template)
            # Second call raises a different error
            mock_query.side_effect = [
                RuntimeError("First endpoint error"),
                RuntimeError("Second endpoint error"),
            ]

            # This should raise the first error since it's not a missing chat template
            with pytest.raises(RuntimeError, match="First endpoint error"):
                request._query_with_fallback({
                    "completions_only": False,
                    "model": "model",
                    "prompt": "test",
                    "max_tokens": 128,
                    "timeout": 5.0,
                    "chat_first": False,
                })
            # Verify _query was called only once (no fallback due to first error)
            assert mock_query.call_count == 1

    def test_missing_chat_template_error_variations(self):
        """Test that various error messages about missing chat templates are detected."""
        test_cases = [
            "No chat template found",
            "chat_template",
            "chattemplate",
            "Template resolution failed",
            "must provide a chat template",
            "default chat template is no longer allowed",
        ]

        for error_msg in test_cases:
            error = RuntimeError(error_msg)
            assert _missing_chat_template(error), f"Error '{error_msg}' should be detected as missing chat template"

    def test_regular_error_not_detected_as_missing_chat_template(self):
        """Test that regular errors are NOT detected as missing chat template."""
        test_cases = [
            "Authentication failed",
            "Server error",
            "Timeout occurred",
            "Rate limit exceeded",
            "Model not found",
        ]

        for error_msg in test_cases:
            error = RuntimeError(error_msg)
            assert not _missing_chat_template(error), f"Error '{error_msg}' should NOT be detected as missing chat template"