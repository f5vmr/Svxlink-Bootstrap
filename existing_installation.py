#!/usr/bin/env python3

"""
Detect an existing SvxLink installation without modifying it.
"""

import pwd
import re
import shutil
import subprocess
from pathlib import Path


SUPPORTED_SVXLINK_VERSION = "26.05.1"

EMBEDDED_VERSION_PATTERN = re.compile(
    rb"SvxLink v"
    rb"([0-9]+(?:\.[0-9]+){2,}"
    rb"(?:@[0-9A-Za-z.+_-]+)?)"
)

def run_command_result(command):
    """Return the complete result of a read-only command."""

    try:
        result = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        return {
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }

    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def run_command(command):
    """Return successful command output, or an empty string."""

    result = run_command_result(command)

    if result["returncode"] != 0:
        return ""

    return result["stdout"]


def detect_embedded_version(executable):
    """Return an SvxLink version embedded in an executable."""

    if not executable:
        return ""

    try:
        content = Path(executable).read_bytes()
    except OSError:
        return ""

    match = EMBEDDED_VERSION_PATTERN.search(content)

    if not match:
        return ""

    return match.group(1).decode(
        "ascii",
        errors="ignore",
    )


def inspect_svxlink_executable(executable):
    """Inspect the executable and retain runtime failure details."""

    if not executable:
        return {
            "version": "",
            "version_source": "",
            "runtime_healthy": False,
            "runtime_error": "",
        }

    result = run_command_result([
        executable,
        "--version",
    ])

    if result["returncode"] == 0:
        output = (
            result["stdout"]
            or result["stderr"]
        )

        version = ""

        if output:
            version = output.splitlines()[0].strip()

        return {
            "version": version,
            "version_source": (
                "executable" if version else ""
            ),
            "runtime_healthy": True,
            "runtime_error": "",
        }

    embedded_version = detect_embedded_version(
        executable
    )

    runtime_error = (
        result["stderr"]
        or result["stdout"]
    )

    return {
        "version": embedded_version,
        "version_source": (
            "embedded" if embedded_version else ""
        ),
        "runtime_healthy": False,
        "runtime_error": runtime_error,
    }


def detect_svxlink_version(executable):
    """Return the reported or embedded SvxLink version."""

    return inspect_svxlink_executable(
        executable
    )["version"]


def version_is_supported(version_text):
    """Return True when the output identifies SvxLink 26.05.1."""

    return bool(
        re.search(
            r"(?<![\d.])26\.05\.1(?![\d.])",
            str(version_text or ""),
        )
    )


def detect_service():
    """Return the systemd load and active states."""

    systemctl = shutil.which("systemctl")

    if not systemctl:
        return {
            "load_state": "",
            "active_state": "",
        }

    load_state = run_command([
        systemctl,
        "show",
        "svxlink.service",
        "--property=LoadState",
        "--value",
    ])
    active_state = run_command([
        systemctl,
        "show",
        "svxlink.service",
        "--property=ActiveState",
        "--value",
    ])

    return {
        "load_state": load_state,
        "active_state": active_state,
    }


def detect_package_status():
    """Return the installed Debian package status, if present."""

    dpkg_query = shutil.which("dpkg-query")

    if not dpkg_query:
        return ""

    return run_command([
        dpkg_query,
        "--show",
        "--showformat=${db:Status-Abbrev} "
        "${Package} ${Version}",
        "svxlink",
    ])


def svxlink_user_exists():
    """Return True when the svxlink account exists."""

    try:
        pwd.getpwnam("svxlink")
    except KeyError:
        return False

    return True


def detect_existing_installation(
    config_directory="/etc/svxlink",
    default_file="/etc/default/svxlink",
):
    """Return evidence of an existing SvxLink installation."""

    executable = shutil.which("svxlink") or ""
    version = detect_svxlink_version(executable)
    service = detect_service()
    package_status = detect_package_status()

    config_path = Path(config_directory)
    main_config = config_path / "svxlink.conf"
    default_path = Path(default_file)

    evidence = {
        "executable": executable,
        "version": version,
        "service_load_state": service["load_state"],
        "service_active_state": service["active_state"],
        "package_status": package_status,
        "user_exists": svxlink_user_exists(),
        "config_directory_exists": config_path.is_dir(),
        "main_config_exists": main_config.is_file(),
        "default_file_exists": default_path.is_file(),
        "config_directory": str(config_path),
        "main_config": str(main_config),
        "default_file": str(default_path),
    }

    evidence["present"] = any([
        bool(evidence["executable"]),
        evidence["service_load_state"] == "loaded",
        bool(evidence["package_status"]),
        evidence["user_exists"],
        evidence["config_directory_exists"],
        evidence["default_file_exists"],
    ])

    evidence["supported_version"] = (
        evidence["present"]
        and version_is_supported(
            evidence["version"]
        )
    )

    return evidence
