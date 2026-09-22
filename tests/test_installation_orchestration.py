#!/usr/bin/env python3

import unittest

from contextlib import (
    redirect_stderr,
    redirect_stdout,
)
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, call, patch

import bootstrap

from configuration_backup import ConfigurationBackupError
from dashboard_installation import DashboardInstallationError
from package_download import PackageDownloadError
from package_installation import PackageInstallationError
from system_access import RootAccessRequiredError

HOST = {
    "platform": "debian",
}

RASPBERRY_PI_HOST = {
    "platform": "raspberry_pi",
}

PACKAGE = {
    "id": "debian_bookworm_amd64",
    "asset": "svxlink_26.05.1_amd64.deb",
}

EXISTING_SUPPORTED = {
    "present": True,
    "supported_version": True,
    "package_managed": True,
    "conversion_candidate": False,
}

NOT_INSTALLED = {
    "present": False,
    "supported_version": False,
    "package_managed": False,
    "conversion_candidate": False,
}

COMPILER_INSTALLATION = {
    "present": True,
    "version": "1.10.1@26.05.1",
    "supported_version": True,
    "package_managed": False,
    "conversion_candidate": True,
}

FAULTY_PACKAGE_INSTALLATION = {
    "present": True,
    "version": "1.10.1@V26.05_Trixie",
    "package_status": "ii  svxlink 26.05.1",
    "supported_version": False,
    "package_managed": True,
    "conversion_candidate": False,
    "service_load_state": "loaded",
    "service_active_state": "active",
}

UPGRADEABLE_PACKAGE_INSTALLATION = {
    "present": True,
    "version": "1.10.0@V26.05",
    "package_status": "ii  svxlink 26.05",
    "supported_version": False,
    "package_managed": True,
    "conversion_candidate": False,
    "service_load_state": "loaded",
    "service_active_state": "active",
}


class InstallationOrchestrationTests(unittest.TestCase):
    def run_installation(
        self,
        installation,
        progress=None,
    ):
        stdout = StringIO()
        stderr = StringIO()

        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = bootstrap.perform_installation(
                HOST,
                PACKAGE,
                installation,
                progress=progress,
            )

        return result, stdout.getvalue(), stderr.getvalue()

    def test_non_root_installation_is_rejected(self):
        with (
            patch(
                "bootstrap.require_root",
                side_effect=RootAccessRequiredError(
                    "Installation requires root privileges."
                ),
            ),
            patch(
                "bootstrap.backup_existing_configuration"
            ) as backup_mock,
            patch(
                "bootstrap.download_package"
            ) as download_mock,
            patch(
                "bootstrap.install_dashboard"
            ) as dashboard_mock,
        ):
            result, stdout, stderr = self.run_installation(
                EXISTING_SUPPORTED
            )

        self.assertEqual(result, 5)
        self.assertEqual(stdout, "")
        self.assertIn(
            "requires root privileges",
            stderr,
        )
        backup_mock.assert_not_called()
        download_mock.assert_not_called()
        dashboard_mock.assert_not_called()

    def test_raspberry_pi_preparation_runs_before_installation(
        self,
    ):
        preparation_report = {
            "changed": [
                "boot_audio",
                "hidraw_rule",
            ],
            "reboot_required": True,
        }

        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.prepare_raspberry_pi",
                return_value=preparation_report,
            ) as prepare_mock,
            patch(
                "bootstrap.download_package",
                side_effect=PackageDownloadError(
                    "Stop after preparation."
                ),
            ),
            patch(
                "bootstrap.install_dashboard"
            ) as dashboard_mock,
        ):
            stdout = StringIO()
            stderr = StringIO()

            with (
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                result = bootstrap.perform_installation(
                    RASPBERRY_PI_HOST,
                    PACKAGE,
                    NOT_INSTALLED,
                )

        self.assertEqual(result, 3)
        prepare_mock.assert_called_once_with()
        self.assertIn(
            "Raspberry Pi preparation completed",
            stdout.getvalue(),
        )
        self.assertIn(
            "reboot will be required",
            stdout.getvalue(),
        )
        dashboard_mock.assert_not_called()

    def test_raspberry_pi_preparation_failure_stops_installation(
        self,
    ):
        progress_mock = Mock()

        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.prepare_raspberry_pi",
                side_effect=(
                    bootstrap.RaspberryPiPreparationError(
                        "Could not configure Raspberry Pi."
                    )
                ),
            ),
            patch(
                "bootstrap.download_package"
            ) as download_mock,
            patch(
                "bootstrap.install_dashboard"
            ) as dashboard_mock,
        ):
            stdout = StringIO()
            stderr = StringIO()

            with (
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                result = bootstrap.perform_installation(
                    RASPBERRY_PI_HOST,
                    PACKAGE,
                    NOT_INSTALLED,
                    progress=progress_mock,
                )

        self.assertEqual(result, 10)
        self.assertIn(
            "Raspberry Pi preparation failed",
            stderr.getvalue(),
        )
        progress_mock.assert_called_once_with(
            "service",
            "failed",
            "Could not configure Raspberry Pi.",
        )
        download_mock.assert_not_called()
        dashboard_mock.assert_not_called()

    def test_existing_supported_installation_is_backed_up(self):
        backup_path = Path(
            "/var/backups/svxlink-bootstrap/20260911-220000"
        )
        progress_mock = Mock()

        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.backup_existing_configuration",
                return_value=backup_path,
            ) as backup_mock,
            patch(
                "bootstrap.download_package"
            ) as download_mock,
            patch(
                "bootstrap.install_package"
            ) as package_install_mock,
            patch(
                "bootstrap.install_dashboard",
                return_value=Path("/opt/dashboard"),
            ) as dashboard_mock,
        ):
            result, stdout, stderr = self.run_installation(
                EXISTING_SUPPORTED,
                progress=progress_mock,
            )

        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertIn(
            str(backup_path),
            stdout,
        )
        self.assertIn(
            "SvxLink-Dash V4.0 installed successfully",
            stdout,
        )
        backup_mock.assert_called_once_with()
        self.assertEqual(
            progress_mock.call_args_list[:2],
            [
                call(
                    "backup",
                    "running",
                    (
                        "Backing up the existing SvxLink "
                        "configuration."
                    ),
                ),
                call(
                    "backup",
                    "completed",
                    (
                        "Existing configuration backed up to "
                        f"{backup_path}."
                    ),
                ),
            ],
        )
        progress_mock.assert_any_call(
            "download",
            "skipped",
            (
                "The installed SvxLink package is already "
                "current."
            ),
        )
        progress_mock.assert_any_call(
            "service",
            "skipped",
            (
                "The retained SvxLink service requires no "
                "package-conversion preparation."
            ),
        )
        progress_mock.assert_any_call(
            "package",
            "skipped",
            (
                "The verified package-managed SvxLink "
                "installation will be retained."
            ),
        )
        download_mock.assert_not_called()
        package_install_mock.assert_not_called()
        progress_mock.assert_any_call(
            "dashboard",
            "running",
            "Installing SvxLink-Dash V4.0.",
        )
        progress_mock.assert_any_call(
            "dashboard",
            "completed",
            (
                "SvxLink-Dash V4.0 was installed "
                "successfully."
            ),
        )
        dashboard_mock.assert_called_once_with()

    def test_compiler_installation_is_backed_up_and_converted(self):
        backup_path = Path(
            "/var/backups/svxlink-bootstrap/20260912-090000"
        )
        package_path = Path(
            "/tmp/download/svxlink_26.05.1_amd64.deb"
        )
        progress_mock = Mock()
        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.backup_existing_configuration",
                return_value=backup_path,
            ) as backup_mock,
            patch(
                "bootstrap.download_package",
                return_value=package_path,
            ) as download_mock,
            patch(
                "bootstrap.install_package"
            ) as package_install_mock,
            patch(
                "bootstrap.install_dashboard",
                return_value=Path("/opt/dashboard"),
            ) as dashboard_mock,
        ):
            result, stdout, stderr = self.run_installation(
                COMPILER_INSTALLATION,
                progress=progress_mock,
            )

        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertIn(str(backup_path), stdout)
        self.assertIn(
            "compiler-installed SvxLink",
            stdout,
        )
        self.assertIn(
            "SvxLink 26.05.1 installed successfully",
            stdout,
        )
        backup_mock.assert_called_once_with()
        progress_mock.assert_any_call(
            "service",
            "running",
            "Preparing the existing SvxLink service.",
        )
        progress_mock.assert_any_call(
            "service",
            "skipped",
            "The SvxLink service was not active.",
        )
        progress_mock.assert_any_call(
            "package",
            "running",
            "Installing and verifying SvxLink 26.05.1.",
        )
        progress_mock.assert_any_call(
            "package",
            "completed",
            (
                "SvxLink 26.05.1 was installed and "
                "verified successfully."
            ),
        )
        download_mock.assert_called_once()
        self.assertEqual(
            download_mock.call_args.args[0],
            PACKAGE,
        )
        package_install_mock.assert_called_once_with(
            package_path
        )
        dashboard_mock.assert_called_once_with()

    def test_known_faulty_package_is_backed_up_and_repaired(self):
        backup_path = Path(
            "/var/backups/svxlink-bootstrap/20260918-190000"
        )
        package_path = Path(
            "/tmp/download/svxlink_26.05.1_amd64.deb"
        )
        progress_mock = Mock()

        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.backup_existing_configuration",
                return_value=backup_path,
            ) as backup_mock,
            patch(
                "bootstrap.download_package",
                return_value=package_path,
            ) as download_mock,
            patch(
                "bootstrap.stop_svxlink_service_if_active",
                return_value=True,
            ) as stop_mock,
            patch(
                "bootstrap.install_package"
            ) as package_install_mock,
            patch(
                "bootstrap.install_dashboard",
                return_value=Path("/opt/dashboard"),
            ) as dashboard_mock,
        ):
            result, stdout, stderr = self.run_installation(
                FAULTY_PACKAGE_INSTALLATION,
                progress=progress_mock,
            )

        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertIn(str(backup_path), stdout)
        self.assertIn(
            (
                "Repairing a previous SvxLink 26.05.1 "
                "installation with a faulty version string."
            ),
            stdout,
        )
        self.assertNotIn(
            "compiler-installed SvxLink",
            stdout,
        )
        backup_mock.assert_called_once_with()
        download_mock.assert_called_once()
        self.assertEqual(
            download_mock.call_args.args[0],
            PACKAGE,
        )
        stop_mock.assert_called_once_with(
            FAULTY_PACKAGE_INSTALLATION
        )
        package_install_mock.assert_called_once_with(
            package_path,
            reinstall=True,
        )
        dashboard_mock.assert_called_once_with()

    def test_older_package_is_backed_up_and_upgraded(self):
        backup_path = Path(
            "/var/backups/svxlink-bootstrap/20260922-180000"
        )
        package_path = Path(
            "/tmp/download/svxlink_26.05.1_amd64.deb"
        )
        progress_mock = Mock()

        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.backup_existing_configuration",
                return_value=backup_path,
            ) as backup_mock,
            patch(
                "bootstrap.download_package",
                return_value=package_path,
            ) as download_mock,
            patch(
                "bootstrap.stop_svxlink_service_if_active",
                return_value=True,
            ) as stop_mock,
            patch(
                "bootstrap.install_package"
            ) as package_install_mock,
            patch(
                "bootstrap.install_dashboard",
                return_value=Path("/opt/dashboard"),
            ) as dashboard_mock,
        ):
            result, stdout, stderr = self.run_installation(
                UPGRADEABLE_PACKAGE_INSTALLATION,
                progress=progress_mock,
            )

        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertIn(str(backup_path), stdout)
        self.assertIn(
            (
                "Upgrading the package-managed SvxLink "
                "installation to version 26.05.1."
            ),
            stdout,
        )
        self.assertNotIn(
            "faulty version string",
            stdout,
        )
        self.assertNotIn(
            "compiler-installed SvxLink",
            stdout,
        )
        backup_mock.assert_called_once_with()
        download_mock.assert_called_once()
        self.assertEqual(
            download_mock.call_args.args[0],
            PACKAGE,
        )
        stop_mock.assert_called_once_with(
            UPGRADEABLE_PACKAGE_INSTALLATION
        )
        package_install_mock.assert_called_once_with(
            package_path
        )
        dashboard_mock.assert_called_once_with()

    def test_backup_failure_stops_installation(self):
        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.backup_existing_configuration",
                side_effect=ConfigurationBackupError(
                    "Permission denied."
                ),
            ),
            patch(
                "bootstrap.install_dashboard"
            ) as dashboard_mock,
        ):
            result, stdout, stderr = self.run_installation(
                EXISTING_SUPPORTED
            )

        self.assertEqual(result, 6)
        self.assertIn(
            "Configuration backup failed",
            stderr,
        )
        dashboard_mock.assert_not_called()

    def test_new_installation_downloads_and_installs_package(self):
        package_path = Path(
            "/tmp/download/svxlink_26.05.1_amd64.deb"
        )
        progress_mock = Mock()

        def download_to_temporary_directory(
            received_package,
            destination_directory,
        ):
            self.assertIs(received_package, PACKAGE)
            directory_mode = (
                Path(destination_directory).stat().st_mode
                & 0o777
            )
            self.assertEqual(directory_mode, 0o755)
            return package_path

        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.download_package",
                side_effect=download_to_temporary_directory,
            ) as download_mock,
            patch(
                "bootstrap.install_package"
            ) as package_install_mock,
            patch(
                "bootstrap.install_dashboard",
                return_value=Path("/opt/dashboard"),
            ) as dashboard_mock,
        ):
            result, stdout, stderr = self.run_installation(
                NOT_INSTALLED,
                progress=progress_mock,
            )

        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertIn(
            "SvxLink 26.05.1 installed successfully",
            stdout,
        )
        self.assertEqual(
            progress_mock.call_args_list[:3],
            [
                call(
                    "backup",
                    "skipped",
                    (
                        "No existing configuration requires "
                        "backup."
                    ),
                ),
                call(
                    "download",
                    "running",
                    (
                        "Downloading and verifying the "
                        "SvxLink package."
                    ),
                ),
                call(
                    "download",
                    "completed",
                    (
                        "SvxLink package downloaded and "
                        "verified."
                    ),
                ),
            ],
        )
        progress_mock.assert_any_call(
            "service",
            "skipped",
            (
                "No compiler-installed SvxLink service "
                "requires preparation."
            ),
        )
        progress_mock.assert_any_call(
            "package",
            "running",
            "Installing and verifying SvxLink 26.05.1.",
        )
        progress_mock.assert_any_call(
            "package",
            "completed",
            (
                "SvxLink 26.05.1 was installed and "
                "verified successfully."
            ),
        )
        download_mock.assert_called_once()
        self.assertEqual(
            download_mock.call_args.args[0],
            PACKAGE,
        )
        package_install_mock.assert_called_once_with(
            package_path
        )
        dashboard_mock.assert_called_once_with()

    def test_package_download_failure_stops_installation(self):
        progress_mock = Mock()
        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.download_package",
                side_effect=PackageDownloadError(
                    "Checksum mismatch."
                ),
            ),
            patch(
                "bootstrap.install_package"
            ) as package_install_mock,
            patch(
                "bootstrap.install_dashboard"
            ) as dashboard_mock,
        ):
            result, stdout, stderr = self.run_installation(
                NOT_INSTALLED,
                progress=progress_mock,
            )

        self.assertEqual(result, 3)
        self.assertIn(
            "Package download failed",
            stderr,
        )
        self.assertEqual(
            progress_mock.call_args_list[-2:],
            [
                call(
                    "download",
                    "running",
                    (
                        "Downloading and verifying the "
                        "SvxLink package."
                    ),
                ),
                call(
                    "download",
                    "failed",
                    "Checksum mismatch.",
                ),
            ],
        )
        package_install_mock.assert_not_called()
        dashboard_mock.assert_not_called()

    def test_package_installation_failure_stops_dashboard(self):
        package_path = Path(
            "/tmp/download/svxlink_26.05.1_amd64.deb"
        )
        progress_mock = Mock()
        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.download_package",
                return_value=package_path,
            ),
            patch(
                "bootstrap.install_package",
                side_effect=PackageInstallationError(
                    "APT failed."
                ),
            ),
            patch(
                "bootstrap.install_dashboard"
            ) as dashboard_mock,
        ):
            result, stdout, stderr = self.run_installation(
                NOT_INSTALLED,
                progress=progress_mock,
            )

        self.assertEqual(result, 7)
        self.assertEqual(
            progress_mock.call_args_list[-2:],
            [
                call(
                    "package",
                    "running",
                    (
                        "Installing and verifying "
                        "SvxLink 26.05.1."
                    ),
                ),
                call(
                    "package",
                    "failed",
                    "APT failed.",
                ),
            ],
        )
        self.assertIn(
            "Package installation failed",
            stderr,
        )
        dashboard_mock.assert_not_called()

    def test_dashboard_failure_is_reported(self):
        progress_mock = Mock()
        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.backup_existing_configuration",
                return_value=Path(
                    "/var/backups/svxlink-bootstrap/"
                    "20260911-220001"
                ),
            ),
            patch(
                "bootstrap.install_dashboard",
                side_effect=DashboardInstallationError(
                    "Installer failed."
                ),
            ),
        ):
            result, stdout, stderr = self.run_installation(
                EXISTING_SUPPORTED,
                progress=progress_mock,
            )

        self.assertEqual(result, 8)
        self.assertEqual(
            progress_mock.call_args_list[-2:],
            [
                call(
                    "dashboard",
                    "running",
                    "Installing SvxLink-Dash V4.0.",
                ),
                call(
                    "dashboard",
                    "failed",
                    "Installer failed.",
                ),
            ],
        )
        self.assertIn(
            "Dashboard installation failed",
            stderr,
        )


if __name__ == "__main__":
    unittest.main()
