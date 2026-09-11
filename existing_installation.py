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


def run_command(command):
    """Return stripped command output, or an empty string."""

    try:
        result = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        return ""

    if result.returncode != 0:
        return ""

    return result.stdout.strip()


def detect_svxlink_version(executable):
    """Return the version text reported by an executable."""

    if not executable:
        return ""

    output = run_command([
        executable,
        "--version",
    ])

    if not output:
        return ""

    return output.splitlines()[0].strip()


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