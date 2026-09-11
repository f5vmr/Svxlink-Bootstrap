#!/usr/bin/env python3

"""
Obtain and run the SvxLink-Dash V4.0 installation script.
"""

import os
import shutil
import subprocess
import tempfile

from pathlib import Path

from system_access import require_root


DASHBOARD_REPOSITORY = (
    "https://github.com/f5vmr/"
    "SvxLink-Dash-V4.0.git"
)

DASHBOARD_BRANCH = "main"

DASHBOARD_CHECKOUT_NAME = "SvxLink-Dash-V4.0"

DASHBOARD_INSTALLER = Path(
    "install/install-dashboard.sh"
)

DASHBOARD_INSTALL_DIRECTORY = Path(
    "/opt/dashboard"
)


class DashboardInstallationError(RuntimeError):
    """Raised when the dashboard cannot be installed."""


def run_command(command, working_directory=None):
    """Run an installation command and return its exit status."""

    try:
        result = subprocess.run(
            command,
            check=False,
            cwd=working_directory,
        )
    except OSError as exc:
        raise DashboardInstallationError(
            f"Could not run {command[0]}: {exc}"
        ) from exc

    return result.returncode


def install_dashboard(work_directory=None):
    """
    Clone the dashboard and run its existing installation script.

    The dashboard repository remains responsible for its own package
    dependencies, permissions, services and runtime directories.
    """

    require_root()

    git = shutil.which("git")

    if not git:
        raise DashboardInstallationError(
            "git was not found on this system."
        )

    temporary = None

    if work_directory is None:
        try:
            temporary = tempfile.TemporaryDirectory(
                prefix="svxlink-bootstrap-"
            )
            work_directory = temporary.name
        except OSError as exc:
            raise DashboardInstallationError(
                f"Could not create a temporary directory: {exc}"
            ) from exc

    work_directory = Path(work_directory)
    checkout = (
        work_directory / DASHBOARD_CHECKOUT_NAME
    )

    try:
        clone_status = run_command([
            git,
            "clone",
            "--depth",
            "1",
            "--branch",
            DASHBOARD_BRANCH,
            "--single-branch",
            DASHBOARD_REPOSITORY,
            str(checkout),
        ])

        if clone_status != 0:
            raise DashboardInstallationError(
                "The SvxLink-Dash V4.0 repository could "
                f"not be cloned (exit status {clone_status})."
            )

        installer = checkout / DASHBOARD_INSTALLER

        if not installer.is_file():
            raise DashboardInstallationError(
                f"Dashboard installer was not found: {installer}"
            )

        if not os.access(installer, os.X_OK):
            raise DashboardInstallationError(
                f"Dashboard installer is not executable: {installer}"
            )

        install_status = run_command(
            [str(installer)],
            working_directory=checkout,
        )

        if install_status != 0:
            raise DashboardInstallationError(
                "The dashboard installer failed "
                f"(exit status {install_status})."
            )

        return DASHBOARD_INSTALL_DIRECTORY

    finally:
        if temporary is not None:
            temporary.cleanup()
