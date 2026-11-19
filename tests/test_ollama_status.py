from unittest.mock import patch

from ui.ollama_status import (
    check_configured_model,
    check_ollama_server,
)


def test_ollama_server_running() -> None:
    with patch(
        "ui.ollama_status._request_json",
        return_value={
            "version": "0.40.16"
        },
    ):
        result = check_ollama_server()

    assert result["running"] is True
    assert result["version"] == "0.40.16"
    assert result["error"] is None


def test_ollama_server_stopped() -> None:
    with patch(
        "ui.ollama_status._request_json",
        side_effect=ConnectionError(
            "Connection refused"
        ),
    ):
        result = check_ollama_server()

    assert result["running"] is False
    assert result["version"] is None
    assert result["error"]


def test_configured_model_available() -> None:
    with patch(
        "ui.ollama_status.get_installed_ollama_models",
        return_value=[
            "llama3.2:latest"
        ],
    ):
        with patch(
            "ui.ollama_status.settings.ollama_model",
            "llama3.2:latest",
        ):
            result = (
                check_configured_model()
            )

    assert result["available"] is True


def test_configured_model_missing() -> None:
    with patch(
        "ui.ollama_status.get_installed_ollama_models",
        return_value=[
            "another-model:latest"
        ],
    ):
        with patch(
            "ui.ollama_status.settings.ollama_model",
            "llama3.2:latest",
        ):
            result = (
                check_configured_model()
            )

    assert result["available"] is False