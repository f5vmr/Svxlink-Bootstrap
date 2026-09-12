#!/usr/bin/env python3

"""
Install a previously downloaded and verified SvxLink Debian package.
"""

import os
import shutil
import subprocess

from pathlib import Path

from existing_installation import (
    detect_existing_installation,
    svxlink_package_owns_file,
)
from system_access import require_root


class PackageInstallationError(RuntimeError):
    """Raised when the SvxLink Debian package cannot be installed."""

def reload_systemd_manager():
    """Reload systemd unit files after package installation."""

    systemctl = shutil.which("systemctl")

    if not systemctl:
        raise PackageInstallationError(
            "systemctl was not found after package installation."
        )

    try:
        result = subprocess.run(
            [
                systemctl,
                "daemon-reload",
            ],
            check=False,
        )
    except OSError as exc:
        raise PackageInstallationError(
            f"Could not start systemctl: {exc}"
        ) from exc

    if result.returncode != 0:
        raise PackageInstallationError(
            "systemctl daemon-reload failed "
            f"(exit status {result.returncode})."
        )

def install_package(package_path):
    """
    Install a verified local Debian package using APT.

    Downloading and checksum verification must have completed before
    this function is called.
    """

    require_root()

    package_path = Path(package_path).resolve()

    if not package_path.is_file():
        raise PackageInstallationError(
            f"Package file does not exist: {package_path}"
        )

    if package_path.suffix.lower() != ".deb":
        raise PackageInstallationError(
            f"Package is not a Debian archive: {package_path}"
        )

    apt_get = shutil.which("apt-get")

    if not apt_get:
        raise PackageInstallationError(
            "apt-get was not found on this system."
        )

    environment = os.environ.copy()
    environment["DEBIAN_FRONTEND"] = "noninteractive"

    try:
        result = subprocess.run(
            [
                apt_get,
                "install",
                "--yes",
                "-o",
                "Dpkg::Options::=--force-confold",
                str(package_path),
            ],
            check=False,
            env=environment,
        )
    except OSError as exc:
        raise PackageInstallationError(
            f"Could not start apt-get: {exc}"
        ) from exc

    if result.returncode != 0:
        raise PackageInstallationError(
            "APT could not install the SvxLink package "
            f"(exit status {result.returncode})."
        )

    reload_systemd_manager()

    if not svxlink_package_owns_file(
        "/usr/bin/svxlink"
    ):
        raise PackageInstallationError(
            "APT completed, but /usr/bin/svxlink is not "
            "owned by the svxlink Debian package."
        )

    installation = detect_existing_installation()

    if not installation["supported_version"]:
        raise PackageInstallationError(
            "APT completed, but SvxLink 26.05.1 could not "
            "be verified after installation."
        )

    return package_path
