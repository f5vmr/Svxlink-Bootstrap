#!/usr/bin/env python3

import unittest
from contextlib import (
    redirect_stderr,
    redirect_stdout,
)
from io import StringIO
from unittest.mock import patch

import bootstrap
from host_detection import HostDetectionError
from package_download import PackageDownloadError
from package_selector import NoMatchingPackageError
from pathlib import Path
from service_control import ServiceControlError

HOST = {
    "platform": "raspberry_pi",
    "pretty_name": "Debian GNU/Linux 13 (trixie)",
    "os_id": "debian",
    "codename": "trixie",
    "architecture": "arm64",
    "device_model": "Raspberry Pi 5 Model B Rev 1.0",
}

PACKAGE = {
    "id": "raspberry_pi_trixie_arm64",
    "tag": "V26.05.1_arm64_Trixie",
    "asset": "svxlink_26.05.1_arm64.deb",
    "size": 5238768,
    "sha256": (
        "e9775c769aed7485b95e3a0165c8eadd"
        "6be94162f82a09fd0b925ab3f1f0de43"
    ),
    "url": (
        "https://github.com/f5vmr/svxlink/releases/"
        "download/V26.05.1_arm64_Trixie/"
        "svxlink_26.05.1_arm64.deb"
    ),
}

COMPILER_INSTALLATION = {
    "present": True,
    "installation_type": "compiler",
    "version": "1.10.1@26.05.1",
    "version_source": "executable",
    "runtime_healthy": True,
    "runtime_error": "",
    "executable": "/usr/bin/svxlink",
    "canonical_executable": "/usr/bin/svxlink",
    "service_load_state": "loaded",
    "service_active_state": "active",
    "package_status": "",
    "supported_version": True,
    "package_managed": False,
    "conversion_candidate": True,
}


class BootstrapTests(unittest.TestCase):
    @patch(
        "bootstrap.resolve_host_package",
        return_value=(HOST, PACKAGE),
    )
    def test_supported_host_reports_package(
        self,
        resolve_mock,
    ):
        stdout = StringIO()
        stderr = StringIO()
        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = bootstrap.main()
        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn(
            "raspberry_pi_trixie_arm64",
            stdout.getvalue(),
        )
        self.assertIn(
            "No files were downloaded",
            stdout.getvalue(),
        )
        resolve_mock.assert_called_once_with()

    @patch(
        "bootstrap.resolve_host_package",
        side_effect=HostDetectionError(
            "Cannot determine architecture."
        ),
    )
    def test_host_detection_failure_returns_one(
        self,
        resolve_mock,
    ):
        stdout = StringIO()
        stderr = StringIO()

        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = bootstrap.main()

        self.assertEqual(result, 1)
        self.assertIn(
            "Host detection failed",
            stderr.getvalue(),
        )
        resolve_mock.assert_called_once_with()

    @patch(
        "bootstrap.resolve_host_package",
        side_effect=NoMatchingPackageError(
            "No supported package."
        ),
    )
    def test_unsupported_host_returns_two(
        self,
        resolve_mock,
    ):
        stdout = StringIO()
        stderr = StringIO()
        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = bootstrap.main()
        self.assertEqual(result, 2)
        self.assertIn(
            "Unsupported system",
            stderr.getvalue(),
        )
        resolve_mock.assert_called_once_with()

    @patch(
        "bootstrap.download_package",
        return_value=Path(
            "/tmp/packages/svxlink_26.05.1_arm64.deb"
        ),
    )
    @patch(
        "bootstrap.resolve_host_package",
        return_value=(HOST, PACKAGE),
    )
    def test_download_option_verifies_selected_package(
        self,
        resolve_mock,
        download_mock,
    ):
        stdout = StringIO()
        stderr = StringIO()

        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = bootstrap.main(
                download_directory="/tmp/packages"
            )
        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn(
            "Package downloaded and verified",
            stdout.getvalue(),
        )
        self.assertIn(
            "has not been installed",
            stdout.getvalue(),
        )
        download_mock.assert_called_once_with(
            PACKAGE,
            "/tmp/packages",
        )
        resolve_mock.assert_called_once_with()

    @patch(
        "bootstrap.download_package",
        side_effect=PackageDownloadError(
            "Checksum mismatch."
        ),
    )
    @patch(
        "bootstrap.resolve_host_package",
        return_value=(HOST, PACKAGE),
    )
    def test_download_failure_returns_three(
        self,
        resolve_mock,
        download_mock,
    ):
        stdout = StringIO()
        stderr = StringIO()

        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = bootstrap.main(
                download_directory="/tmp/packages"
            )
        self.assertEqual(result, 3)
        self.assertIn(
            "Package download failed",
            stderr.getvalue(),
        )
        download_mock.assert_called_once_with(
            PACKAGE,
            "/tmp/packages",
        )
        resolve_mock.assert_called_once_with()

    @patch("bootstrap.select_package")
    @patch("bootstrap.load_manifest")
    @patch("bootstrap.detect_host")
    def test_resolution_passes_detected_values(
        self,
        detect_mock,
        load_mock,
        select_mock,
    ):
        detect_mock.return_value = HOST
        load_mock.return_value = {
            "schema_version": 1,
            "packages": [],
        }
        select_mock.return_value = PACKAGE
        host, package = bootstrap.resolve_host_package(
            "test-manifest.json"
        )
        self.assertEqual(host, HOST)
        self.assertEqual(package, PACKAGE)
        load_mock.assert_called_once_with(
            "test-manifest.json"
        )
        select_mock.assert_called_once_with(
            load_mock.return_value,
            platform="raspberry_pi",
            os_id="debian",
            codename="trixie",
            architecture="arm64",
        )

    def test_existing_installation_report_when_absent(self):
        report = bootstrap.describe_existing_installation({
            "present": False,
        })

        self.assertIn(
            "Existing SvxLink installation: not detected",
            report,
        )
        self.assertIn(
            "selected package will be required",
            report,
        )

    def test_supported_existing_installation_report(self):
        report = bootstrap.describe_existing_installation({
            "present": True,
            "installation_type": "package",
            "version": "1.10.1@26.05.1",
            "version_source": "executable",
            "runtime_healthy": True,
            "runtime_error": "",
            "executable": "/usr/bin/svxlink",
            "service_load_state": "loaded",
            "service_active_state": "active",
            "package_status": "ii  svxlink 26.05.1",
            "supported_version": True,
            "package_managed": True,
            "conversion_candidate": False,
        })
        self.assertIn(
            "supported SvxLink 26.05.1",
            report,
        )
        self.assertIn(
            "package-managed installation will be retained",
            report,
        )
        self.assertIn(
            "configuration will be backed up",
            report,
        )

    def test_known_faulty_package_repair_report(self):
        report = bootstrap.describe_existing_installation({
            "present": True,
            "installation_type": "package",
            "version": "1.10.1@V26.05_Trixie",
            "version_source": "executable",
            "runtime_healthy": True,
            "runtime_error": "",
            "executable": "/usr/bin/svxlink",
            "service_load_state": "loaded",
            "service_active_state": "active",
            "package_status": "ii  svxlink 26.05.1",
            "supported_version": False,
            "package_managed": True,
            "conversion_candidate": False,
        })

        self.assertIn(
            "repair required for faulty version string",
            report,
        )
        self.assertIn(
            "configuration will be backed up",
            report,
        )
        self.assertIn(
            "verified package will be forcibly reinstalled",
            report,
        )

    def test_unknown_existing_installation_report(self):
        report = bootstrap.describe_existing_installation({
            "present": True,
            "installation_type": "remnants",
            "version": "",
            "version_source": "",
            "runtime_healthy": False,
            "runtime_error": "",
            "executable": "",
            "service_load_state": "loaded",
            "service_active_state": "inactive",
            "package_status": "",
            "supported_version": False,
            "package_managed": False,
            "conversion_candidate": False,
        })
        self.assertIn(
            "Reported version: unknown",
            report,
        )
        self.assertIn(
            "unsupported or unknown",
            report,
        )
        self.assertIn(
            "stop for manual review",
            report,
        )

    @patch("bootstrap.download_package")
    @patch(
        "bootstrap.detect_existing_installation",
        return_value={
            "present": True,
            "version": "1.10.1@26.05.1",
            "executable": "/usr/bin/svxlink",
            "service_load_state": "loaded",
            "service_active_state": "active",
            "package_status": "",
            "supported_version": True,
            "package_managed": True,
            "conversion_candidate": False,
        },
    )
    @patch(
        "bootstrap.resolve_host_package",
        return_value=(HOST, PACKAGE),
    )
    def test_supported_existing_installation_skips_download(
        self,
        resolve_mock,
        installation_mock,
        download_mock,
    ):
        stdout = StringIO()
        stderr = StringIO()

        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = bootstrap.main(
                download_directory="/tmp/packages"
            )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn(
            "package download was skipped",
            stdout.getvalue(),
        )
        download_mock.assert_not_called()
        installation_mock.assert_called_once_with()
        resolve_mock.assert_called_once_with()

    @patch("bootstrap.download_package")
    @patch(
        "bootstrap.detect_existing_installation",
        return_value={
            "present": True,
            "installation_type": "compiler",
            "version": "1.8.0@19.09",
            "version_source": "executable",
            "runtime_healthy": True,
            "runtime_error": "",
            "executable": "/usr/local/bin/svxlink",
            "service_load_state": "loaded",
            "service_active_state": "active",
            "package_status": "",
            "supported_version": False,
            "package_managed": False,
            "conversion_candidate": False,
        },
    )
    @patch(
        "bootstrap.resolve_host_package",
        return_value=(HOST, PACKAGE),
    )
    def test_unsupported_existing_installation_stops(
        self,
        resolve_mock,
        installation_mock,
        download_mock,
    ):
        stdout = StringIO()
        stderr = StringIO()

        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = bootstrap.main(
                download_directory="/tmp/packages"
            )

        self.assertEqual(result, 4)
        self.assertIn(
            "Automatic processing stopped",
            stderr.getvalue(),
        )
        download_mock.assert_not_called()
        installation_mock.assert_called_once_with()
        resolve_mock.assert_called_once_with()

    def test_conversion_stops_active_service_before_install(self):
        stdout = StringIO()
        stderr = StringIO()

        with (
            patch("bootstrap.require_root") as root_mock,
            patch(
                "bootstrap.prepare_raspberry_pi",
                return_value={
                    "changed": [],
                    "reboot_required": False,
                },
            ) as prepare_mock,
            patch(
                "bootstrap.backup_existing_configuration",
                return_value=Path("/var/backups/test"),
            ) as backup_mock,
            patch(
                "bootstrap.download_package",
                return_value=Path("/tmp/svxlink.deb"),
            ) as download_mock,
            patch(
                "bootstrap.stop_svxlink_service_if_active",
                return_value=True,
            ) as stop_mock,
            patch(
                "bootstrap.install_package"
            ) as install_mock,
            patch(
                "bootstrap.install_dashboard",
                return_value=Path("/opt/dashboard"),
            ) as dashboard_mock,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = bootstrap.perform_installation(
                HOST,
                PACKAGE,
                COMPILER_INSTALLATION,
            )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn(
            "active SvxLink service has been stopped",
            stdout.getvalue(),
        )
        root_mock.assert_called_once_with()
        prepare_mock.assert_called_once_with()
        backup_mock.assert_called_once_with()
        download_mock.assert_called_once()
        stop_mock.assert_called_once_with(
            COMPILER_INSTALLATION
        )
        install_mock.assert_called_once_with(
            Path("/tmp/svxlink.deb")
        )
        dashboard_mock.assert_called_once_with()

    def test_conversion_stops_when_service_cannot_be_stopped(
        self,
    ):
        stdout = StringIO()
        stderr = StringIO()

        with (
            patch("bootstrap.require_root"),
            patch(
                "bootstrap.prepare_raspberry_pi",
                return_value={
                    "changed": [],
                    "reboot_required": False,
                },
            ) as prepare_mock,
            patch(
                "bootstrap.backup_existing_configuration",
                return_value=Path("/var/backups/test"),
            ),
            patch(
                "bootstrap.download_package",
                return_value=Path("/tmp/svxlink.deb"),
            ),
            patch(
                "bootstrap.stop_svxlink_service_if_active",
                side_effect=ServiceControlError(
                    "Could not stop svxlink.service."
                ),
            ) as stop_mock,
            patch(
                "bootstrap.install_package"
            ) as install_mock,
            patch(
                "bootstrap.install_dashboard"
            ) as dashboard_mock,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = bootstrap.perform_installation(
                HOST,
                PACKAGE,
                COMPILER_INSTALLATION,
            )

        self.assertEqual(result, 9)
        self.assertIn(
            "Service control failed",
            stderr.getvalue(),
        )
        stop_mock.assert_called_once_with(
            COMPILER_INSTALLATION
        )
        install_mock.assert_not_called()
        dashboard_mock.assert_not_called()
        prepare_mock.assert_called_once_with()

if __name__ == "__main__":
    unittest.main()
