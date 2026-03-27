from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

from app.settings_ui import _ConnectionWorker, _get_connection_error_message


@pytest.fixture
def qapp():
    """Create a QApplication if not already created."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_httpx_response():
    """Create a mock HTTP response object."""
    response = MagicMock()
    response.is_success = False
    response.status_code = 200
    return response


def test_connection_worker_success_on_200(qapp, mock_httpx_response):
    """Test that 200 status code triggers success signal."""
    mock_httpx_response.is_success = True
    mock_httpx_response.status_code = 200

    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = (
            mock_httpx_response
        )

        worker = _ConnectionWorker(
            endpoint="https://api.example.com",
            api_key="test",
            timeout=10,
            model="",
        )

        success_signals = []
        worker.succeeded.connect(lambda: success_signals.append(True))

        worker.run()

        assert len(success_signals) == 1, "Success signal should have been emitted for 200 status"


def test_connection_worker_failure_on_404(qapp, mock_httpx_response):
    """Test that 404 status code triggers failure signal (NOT success)."""
    mock_httpx_response.is_success = False
    mock_httpx_response.status_code = 404

    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = (
            mock_httpx_response
        )

        worker = _ConnectionWorker(
            endpoint="https://api.example.com",
            api_key="test",
            timeout=10,
            model="",
        )

        failure_signals = []
        worker.failed.connect(lambda msg: failure_signals.append(msg))

        worker.run()

        assert len(failure_signals) == 1, "Failure signal should have been emitted for 404 status"
        assert "URL" in failure_signals[0] or "端点" in failure_signals[0]


def test_connection_worker_failure_on_401(qapp, mock_httpx_response):
    """Test that 401 (Unauthorized) triggers failure signal (NOT success)."""
    mock_httpx_response.is_success = False
    mock_httpx_response.status_code = 401

    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = (
            mock_httpx_response
        )

        worker = _ConnectionWorker(
            endpoint="https://api.example.com",
            api_key="wrong_key",
            timeout=10,
            model="",
        )

        failure_signals = []
        worker.failed.connect(lambda msg: failure_signals.append(msg))

        worker.run()

        assert len(failure_signals) == 1, "Failure signal should have been emitted for 401 status"
        assert "API Key" in failure_signals[0]


def test_connection_worker_failure_on_500(qapp, mock_httpx_response):
    """Test that 500 status code triggers failure signal."""
    mock_httpx_response.is_success = False
    mock_httpx_response.status_code = 500

    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = (
            mock_httpx_response
        )

        worker = _ConnectionWorker(
            endpoint="https://api.example.com",
            api_key="test",
            timeout=10,
            model="",
        )

        failure_signals = []
        worker.failed.connect(lambda msg: failure_signals.append(msg))

        worker.run()

        assert len(failure_signals) == 1, "Failure signal should have been emitted for 500 status"
        assert "服务器" in failure_signals[0] or "Server" in failure_signals[0]


def test_connection_worker_success_on_201(qapp, mock_httpx_response):
    """Test that 201 (Created) status code triggers success signal."""
    mock_httpx_response.is_success = True
    mock_httpx_response.status_code = 201

    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = (
            mock_httpx_response
        )

        worker = _ConnectionWorker(
            endpoint="https://api.example.com",
            api_key="test",
            timeout=10,
            model="",
        )

        success_signals = []
        worker.succeeded.connect(lambda: success_signals.append(True))

        worker.run()

        assert len(success_signals) == 1, "Success signal should have been emitted for 201 status"


def test_connection_worker_model_validation_on_post(qapp, mock_httpx_response):
    """Test that when model is provided, a POST request is made to /chat/completions."""
    mock_httpx_response.is_success = True
    mock_httpx_response.status_code = 200

    with patch("httpx.Client") as mock_client:
        # Mock both GET and POST methods
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value.post.return_value = mock_httpx_response
        mock_client.return_value = mock_instance

        worker = _ConnectionWorker(
            endpoint="https://api.example.com",
            api_key="test-key",
            timeout=10,
            model="gpt-4o",
        )

        success_signals = []
        worker.succeeded.connect(lambda: success_signals.append(True))

        worker.run()

        # Verify POST was called
        mock_instance.__enter__.return_value.post.assert_called_once()
        call_args = mock_instance.__enter__.return_value.post.call_args
        assert "/chat/completions" in call_args[0][0]
        assert call_args[1]["json"]["model"] == "gpt-4o"

        assert len(success_signals) == 1


def test_error_message_on_401_api_key_invalid():
    """Test 401 error shows API Key hint."""
    msg = _get_connection_error_message(401, "", "https://api.example.com")
    assert "API Key" in msg
    assert "❌" in msg


def test_error_message_on_404_without_model():
    """Test 404 error without model shows URL hint."""
    msg = _get_connection_error_message(404, "", "https://api.example.com")
    assert "URL" in msg or "端点" in msg
    assert "❌" in msg


def test_error_message_on_404_with_model():
    """Test 404 error with model shows model name hint."""
    msg = _get_connection_error_message(404, "gpt-4o", "https://api.example.com")
    assert "gpt-4o" in msg
    assert "模型" in msg
    assert "❌" in msg


def test_error_message_on_400_with_model():
    """Test 400 error with model shows model compatibility hint."""
    msg = _get_connection_error_message(400, "invalid-model", "https://api.example.com")
    assert "invalid-model" in msg
    assert "❌" in msg


def test_error_message_on_403():
    """Test 403 error shows permission hint."""
    msg = _get_connection_error_message(403, "", "https://api.example.com")
    assert "权限" in msg or "Permission" in msg or "无权" in msg
    assert "❌" in msg


def test_error_message_on_500():
    """Test 500 error shows server problem hint."""
    msg = _get_connection_error_message(500, "", "https://api.example.com")
    assert "服务器" in msg or "Server" in msg
    assert "❌" in msg
