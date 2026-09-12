#!/usr/bin/env python3

"""
Detect the host platform, operating system and Debian architecture.
"""

import shlex
import subprocess
from pathlib import Path


class HostDetectionError(RuntimeError):
    """Raised when required host information cannot be detected."""


def parse_os_release(path="/etc/os-release"):
    """Read selected values from an os-release file."""

    os_release_path = Path(path)

    try:
        lines = os_release_path.read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError as exc:
        raise HostDetectionError(
            f"Cannot read {os_release_path}: {exc}"
        ) from exc

    values = {}

    for line in lines:
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)

        try:
            parsed = shlex.split(
                raw_value,
                posix=True,
            )
        except ValueError as exc:
            raise HostDetectionError(
                f"Invalid {key} value in {os_release_path}"
            ) from exc

        values[key] = parsed[0] if parsed else ""

    os_id = values.get("ID", "").strip().lower()
    codename = (
        values.get("VERSION_CODENAME")
        or values.get("DEBIAN_CODENAME")
        or values.get("UBUNTU_CODENAME")
        or ""
    ).strip().lower()

    if not os_id:
        raise HostDetectionError(
            f"{os_release_path} does not define ID"
        )

    if not codename:
        raise HostDetectionError(
            f"{os_release_path} does not define a release codename"
        )

    return {
        "os_id": os_id,
        "codename": codename,
        "pretty_name": values.get(
            "PRETTY_NAME",
            os_id,
        ),
    }


def detect_architecture():
    """Return the host architecture used by Debian packages."""

    try:
        result = subprocess.run(
            [
                "/usr/bin/dpkg",
                "--print-architecture",
            ],
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HostDetectionError(
            "Cannot determine Debian package architecture."
        ) from exc

    architecture = result.stdout.strip().lower()

    if not architecture:
        raise HostDetectionError(
            "dpkg returned an empty architecture."
        )

    return architecture


def read_device_model(
    path="/proc/device-tree/model",
):
    """Return the device-tree model, or an empty string."""

    try:
        return (
            Path(path)
            .read_bytes()
            .rstrip(b"\x00")
            .decode("utf-8", errors="replace")
            .strip()
        )
    except OSError:
        return ""


def classify_platform(os_id, device_model):
    """Classify the supported hardware/platform family."""

    model = str(device_model or "").strip().lower()
    os_id = str(os_id or "").strip().lower()

    if "raspberry pi" in model:
        return "raspberry_pi"

    if "nanopi" in model and "neo" in model:
        return "nanopi_neo"

    if os_id == "debian":
        return "debian"

    return os_id or "unknown"


def detect_host(
    os_release_path="/etc/os-release",
    device_model_path="/proc/device-tree/model",
):
    """Return the host values required by package selection."""

    os_information = parse_os_release(
        os_release_path
    )
    architecture = detect_architecture()
    device_model = read_device_model(
        device_model_path
    )
    platform = classify_platform(
        os_information["os_id"],
        device_model,
    )

    return {
        "platform": platform,
        "os_id": os_information["os_id"],
        "codename": os_information["codename"],
        "architecture": architecture,
        "pretty_name": os_information["pretty_name"],
        "device_model": device_model,
    }
