from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from config.settings import settings


OLLAMA_EXECUTABLE = Path(
    r"C:\Users\Abhijeet.2.Kumar\OLLAMA\ollama.exe"
)


def _get_api_url(
    endpoint: str,
) -> str:
    base_url = (
        settings.ollama_base_url.rstrip("/")
    )

    normalized_endpoint = (
        endpoint
        if endpoint.startswith("/")
        else f"/{endpoint}"
    )

    return f"{base_url}{normalized_endpoint}"


def _request_json(
    endpoint: str,
    timeout_seconds: int = 3,
) -> dict[str, Any]:
    request = urllib.request.Request(
        _get_api_url(endpoint),
        method="GET",
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout_seconds,
    ) as response:
        response_text = response.read().decode(
            "utf-8"
        )

    data = json.loads(response_text)

    if not isinstance(data, dict):
        raise ValueError(
            "Ollama returned an unexpected response."
        )

    return data


def check_ollama_server() -> dict[str, Any]:
    """
    Check local Ollama API availability.

    This function does not start the server.
    """

    try:
        version_data = _request_json(
            "/api/version"
        )

        return {
            "running": True,
            "version": version_data.get(
                "version"
            ),
            "base_url": (
                settings.ollama_base_url
            ),
            "error": None,
        }

    except (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        return {
            "running": False,
            "version": None,
            "base_url": (
                settings.ollama_base_url
            ),
            "error": str(error),
        }


def get_installed_ollama_models() -> list[str]:
    """
    Return model names reported by the Ollama API.
    """

    try:
        response = _request_json(
            "/api/tags",
            timeout_seconds=10,
        )

    except Exception:
        return []

    models = response.get(
        "models",
        [],
    )

    model_names: list[str] = []

    for model in models:
        if not isinstance(model, dict):
            continue

        model_name = (
            model.get("name")
            or model.get("model")
        )

        if model_name:
            model_names.append(
                str(model_name)
            )

    return sorted(
        set(model_names)
    )


def check_configured_model() -> dict[str, Any]:
    """
    Check whether the configured Ollama model exists.
    """

    installed_models = (
        get_installed_ollama_models()
    )

    configured_model = (
        settings.ollama_model
    )

    return {
        "available": (
            configured_model
            in installed_models
        ),
        "configured_model": (
            configured_model
        ),
        "installed_models": (
            installed_models
        ),
    }


def start_ollama_server() -> dict[str, Any]:
    """
    Start the Ollama server as a background process.

    The executable path is fixed to the user's local
    installation path.
    """

    server_status = check_ollama_server()

    if server_status["running"]:
        return {
            "started": False,
            "already_running": True,
            "error": None,
        }

    if not OLLAMA_EXECUTABLE.exists():
        return {
            "started": False,
            "already_running": False,
            "error": (
                "Ollama executable was not found at "
                f"{OLLAMA_EXECUTABLE}."
            ),
        }

    try:
        creation_flags = (
            subprocess.CREATE_NO_WINDOW
            if hasattr(
                subprocess,
                "CREATE_NO_WINDOW",
            )
            else 0
        )

        subprocess.Popen(
            [
                str(OLLAMA_EXECUTABLE),
                "serve",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )

        return {
            "started": True,
            "already_running": False,
            "error": None,
        }

    except OSError as error:
        return {
            "started": False,
            "already_running": False,
            "error": str(error),
        }