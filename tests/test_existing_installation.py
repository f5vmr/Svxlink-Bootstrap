#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import existing_installation
from existing_installation import (
    detect_existing_installation,
    detect_service,
    version_is_supported,
    detect_embedded_version,
    inspect_svxlink_executable,
    classify_installation,
    package_status_is_installed,
    svxlink_package_owns_file,
    determine_installation_action,
    compiler_version_is_replaceable,
)


class ExistingInstallationTests(unittest.TestCase):

    def test_supported_version_is_recognised(self):
        self.assertTrue(
            version_is_supported(
                "1.10.1@26.05.1"
            )
        )

    def test_replaceable_compiler_release_years_are_recognised(self):
        versions = [
            "1.9.0@24.02",
            "1.9.0@25.05.1",
            "1.10.1@26.05.1",
        ]
        for version in versions:
            with self.subTest(version=version):
                self.assertTrue(
                    compiler_version_is_replaceable(version)
                )

    def test_other_compiler_release_years_are_rejected(self):
        versions = [
            "",
            "1.10.1",
            "1.5.0@17.12.2",
            "1.8.0@19.09",
            "1.9.99.36@13.12.1-1903-g8515694c",
            "1.9.99@14.08",
            "1.9.99@15.11",
            "1.10.1@27.01",
            "1.10.1@260.05.1",
        ]
        for version in versions:
            with self.subTest(version=version):
                self.assertFalse(
                    compiler_version_is_replaceable(version)
                )

    def test_installed_package_status_is_recognised(self):
        self.assertTrue(
            package_status_is_installed(
                "ii  svxlink 26.05.1"
            )
        )
        self.assertFalse(
            package_status_is_installed("")
        )
        self.assertFalse(
            package_status_is_installed(
                "rc  svxlink 25.05.1"
            )
        )

    @patch(
        "existing_installation.run_command",
        return_value="svxlink: /usr/bin/svxlink",
    )
    @patch(
        "existing_installation.shutil.which",
        return_value="/usr/bin/dpkg-query",
    )
    def test_svxlink_package_ownership_is_recognised(
        self,
        which_mock,
        command_mock,
    ):
        self.assertTrue(
            svxlink_package_owns_file(
                "/usr/bin/svxlink"
            )
        )
        which_mock.assert_called_once_with("dpkg-query")
        command_mock.assert_called_once_with([
            "/usr/bin/dpkg-query",
            "--search",
            "/usr/bin/svxlink",
        ])

    @patch(
        "existing_installation.run_command",
        return_value=(
            "svxlink:amd64: /usr/bin/svxlink"
        ),
    )
    @patch(
        "existing_installation.shutil.which",
        return_value="/usr/bin/dpkg-query",
    )
    def test_architecture_qualified_ownership_is_recognised(
        self,
        which_mock,
        command_mock,
    ):
        self.assertTrue(
            svxlink_package_owns_file(
                "/usr/bin/svxlink"
            )
        )
        which_mock.assert_called_once_with("dpkg-query")
        command_mock.assert_called_once_with([
            "/usr/bin/dpkg-query",
            "--search",
            "/usr/bin/svxlink",
        ])

    @patch(
        "existing_installation.run_command",
        return_value=(
            "another-package: /usr/bin/svxlink"
        ),
    )
    @patch(
        "existing_installation.shutil.which",
        return_value="/usr/bin/dpkg-query",
    )
    def test_other_package_ownership_is_rejected(
        self,
        which_mock,
        command_mock,
    ):
        self.assertFalse(
            svxlink_package_owns_file(
                "/usr/bin/svxlink"
            )
        )
        which_mock.assert_called_once_with("dpkg-query")
        command_mock.assert_called_once_with([
            "/usr/bin/dpkg-query",
            "--search",
            "/usr/bin/svxlink",
        ])

    def test_package_installation_is_classified(self):
        result = classify_installation({
            "present": True,
            "package_status": "ii  svxlink 26.05.1",
            "executable": "/usr/bin/svxlink",
            "canonical_executable": "/usr/bin/svxlink",
            "service_load_state": "loaded",
        })

        self.assertEqual(
            result["installation_type"],
            "package",
        )
        self.assertTrue(result["package_managed"])
        self.assertFalse(
            result["conversion_candidate"]
        )

    def test_absent_installation_requires_package(self):
        action = determine_installation_action({
            "present": False,
            "package_managed": False,
            "supported_version": False,
            "conversion_candidate": False,
        })

        self.assertEqual(action, "install")

    def test_current_package_installation_is_retained(self):
        action = determine_installation_action({
            "present": True,
            "package_managed": True,
            "supported_version": True,
            "conversion_candidate": False,
        })

        self.assertEqual(action, "retain")

    def test_catalogued_older_compiler_installation_is_converted(self):
        action = determine_installation_action({
            "present": True,
            "package_managed": False,
            "supported_version": False,
            "conversion_candidate": True,
            "version": "1.9.0@25.05.1",
        })
        self.assertEqual(action, "convert")

    def test_current_compiler_installation_is_converted(self):
        action = determine_installation_action({
            "present": True,
            "package_managed": False,
            "supported_version": True,
            "conversion_candidate": True,
            "version": "1.10.1@26.05.1",
        })

        self.assertEqual(action, "convert")

    def test_unknown_compiler_installation_is_blocked(self):
        action = determine_installation_action({
            "present": True,
            "package_managed": False,
            "supported_version": False,
            "conversion_candidate": True,
        })
        self.assertEqual(action, "block")

    def test_unrecognised_installation_is_blocked(self):
        action = determine_installation_action({
            "present": True,
            "package_managed": False,
            "supported_version": False,
            "conversion_candidate": False,
        })

        self.assertEqual(action, "block")

    def test_standard_compiler_installation_is_convertible(self):
        result = classify_installation({
            "present": True,
            "package_status": "",
            "executable": "/usr/bin/svxlink",
            "canonical_executable": "/usr/bin/svxlink",
            "service_load_state": "loaded",
        })

        self.assertEqual(
            result["installation_type"],
            "compiler",
        )
        self.assertFalse(result["package_managed"])
        self.assertTrue(
            result["conversion_candidate"]
        )

    def test_nonstandard_compiler_installation_is_blocked(self):
        result = classify_installation({
            "present": True,
            "package_status": "",
            "executable": "/usr/local/bin/svxlink",
            "canonical_executable": (
                "/usr/local/bin/svxlink"
            ),
            "service_load_state": "loaded",
        })

        self.assertEqual(
            result["installation_type"],
            "compiler",
        )
        self.assertFalse(
            result["conversion_candidate"]
        )

    def test_other_versions_are_rejected(self):
        versions = [
            "",
            "1.9.0@25.05.1",
            "26.05",
            "26.05.10",
            "126.05.1",
        ]

        for version in versions:
            with self.subTest(version=version):
                self.assertFalse(
                    version_is_supported(version)
                )

    @patch(
        "existing_installation.svxlink_user_exists",
        return_value=False,
    )
    @patch(
        "existing_installation.detect_package_status",
        return_value="",
    )
    @patch(
        "existing_installation.detect_service",
        return_value={
            "load_state": "not-found",
            "active_state": "inactive",
        },
    )
    @patch(
        "existing_installation.shutil.which",
        return_value=None,
    )
    def test_clean_machine_is_not_present(
        self,
        which_mock,
        service_mock,
        package_mock,
        user_mock,
    ):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)

            result = detect_existing_installation(
                config_directory=base / "svxlink",
                default_file=base / "default-svxlink",
            )

        self.assertFalse(result["present"])
        self.assertFalse(
            result["supported_version"]
        )
        self.assertEqual(
            result["installation_type"],
            "absent",
        )

    @patch(
        "existing_installation.svxlink_user_exists",
        return_value=True,
    )
    @patch(
        "existing_installation.detect_package_status",
        return_value="",
    )
    @patch(
        "existing_installation.detect_service",
        return_value={
            "load_state": "not-found",
            "active_state": "inactive",
        },
    )
    @patch(
        "existing_installation.shutil.which",
        return_value=None,
    )
    def test_user_account_alone_is_not_an_installation(
        self,
        which_mock,
        service_mock,
        package_mock,
        user_mock,
    ):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            result = detect_existing_installation(
                config_directory=base / "svxlink",
                default_file=base / "default-svxlink",
            )

        self.assertTrue(result["user_exists"])
        self.assertFalse(result["present"])
        self.assertEqual(
            result["installation_type"],
            "absent",
        )

    @patch(
        "existing_installation.svxlink_user_exists",
        return_value=True,
    )
    @patch(
        "existing_installation.detect_package_status",
        return_value="",
    )
    @patch(
        "existing_installation.detect_service",
        return_value={
            "load_state": "loaded",
            "active_state": "active",
        },
    )
    @patch(
        "existing_installation.inspect_svxlink_executable",
        return_value={
            "version": "1.10.1@26.05.1",
            "version_source": "executable",
            "runtime_healthy": True,
            "runtime_error": "",
        },
    )
    @patch(
        "existing_installation.shutil.which",
        return_value="/usr/bin/svxlink",
    )
    def test_manual_supported_installation_is_detected(
        self,
        which_mock,
        inspection_mock,
        service_mock,
        package_mock,
        user_mock,
    ):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            config_directory = base / "svxlink"
            config_directory.mkdir()
            (
                config_directory / "svxlink.conf"
            ).write_text(
                "[GLOBAL]\n",
                encoding="utf-8",
            )
            default_file = base / "default-svxlink"
            default_file.write_text(
                "RUNASUSER=svxlink\n",
                encoding="utf-8",
            )

            result = detect_existing_installation(
                config_directory=config_directory,
                default_file=default_file,
            )

        self.assertTrue(result["present"])
        self.assertTrue(
            result["supported_version"]
        )
        self.assertEqual(
            result["service_active_state"],
            "active",
        )
        self.assertEqual(
            result["package_status"],
            "",
        )
        self.assertEqual(
            result["version_source"],
            "executable",
        )
        self.assertTrue(result["runtime_healthy"])
        self.assertEqual(result["runtime_error"], "")
        inspection_mock.assert_called_once_with(
            "/usr/bin/svxlink"
        )
        self.assertEqual(
            result["installation_type"],
            "compiler",
        )
        self.assertFalse(result["package_managed"])
        self.assertTrue(
            result["conversion_candidate"]
        )

    @patch(
        "existing_installation.svxlink_user_exists",
        return_value=True,
    )
    @patch(
        "existing_installation.detect_package_status",
        return_value="ii  svxlink 25.05.1",
    )
    @patch(
        "existing_installation.detect_service",
        return_value={
            "load_state": "loaded",
            "active_state": "inactive",
        },
    )
    @patch(
        "existing_installation.inspect_svxlink_executable",
        return_value={
            "version": (
                "1.9.99.36@13.12.1-1903-g8515694c"
            ),
            "version_source": "embedded",
            "runtime_healthy": False,
            "runtime_error": (
                "error while loading shared libraries: "
                "libsigc-2.0.so.0: cannot open shared "
                "object file"
            ),
        },
    )
    @patch(
        "existing_installation.shutil.which",
        return_value="/usr/bin/svxlink",
    )
    def test_older_installation_is_unsupported(
        self,
        which_mock,
        inspection_mock,
        service_mock,
        package_mock,
        user_mock,
    ):
        result = detect_existing_installation(
            config_directory="/missing/config",
            default_file="/missing/default",
        )

        self.assertTrue(result["present"])
        self.assertFalse(
            result["supported_version"]
        )
        self.assertEqual(
            result["version_source"],
            "embedded",
        )
        self.assertFalse(result["runtime_healthy"])
        self.assertIn(
            "libsigc-2.0.so.0",
            result["runtime_error"],
        )
        inspection_mock.assert_called_once_with(
            "/usr/bin/svxlink"
        )

    @patch(
        "existing_installation.svxlink_user_exists",
        return_value=False,
    )
    @patch(
        "existing_installation.detect_package_status",
        return_value="",
    )
    @patch(
        "existing_installation.detect_service",
        return_value={
            "load_state": "not-found",
            "active_state": "inactive",
        },
    )
    @patch(
        "existing_installation.shutil.which",
        return_value=None,
    )
    def test_configuration_remnants_are_detected(
        self,
        which_mock,
        service_mock,
        package_mock,
        user_mock,
    ):
        with tempfile.TemporaryDirectory() as directory:
            config_directory = (
                Path(directory) / "svxlink"
            )
            config_directory.mkdir()

            result = detect_existing_installation(
                config_directory=config_directory,
                default_file=(
                    Path(directory) / "missing-default"
                ),
            )

        self.assertTrue(result["present"])
        self.assertFalse(
            result["supported_version"]
        )
        self.assertEqual(
            result["installation_type"],
            "remnants",
        )

    @patch(
        "existing_installation.shutil.which",
        return_value=None,
    )
    def test_service_detection_without_systemd(
        self,
        which_mock,
    ):
        self.assertEqual(
            detect_service(),
            {
                "load_state": "",
                "active_state": "",
            },
        )

    def test_embedded_version_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "svxlink"
            executable.write_bytes(
                b"\x00unrelated\x00"
                b"SvxLink v1.9.99.36@13.12.1-1903-g8515694c "
                b"Copyright\x00"
            )

            version = detect_embedded_version(
                executable
            )

        self.assertEqual(
            version,
            "1.9.99.36@13.12.1-1903-g8515694c",
        )

    def test_missing_embedded_version_returns_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "svxlink"
            executable.write_bytes(
                b"\x00no version information\x00"
            )

            version = detect_embedded_version(
                executable
            )

        self.assertEqual(version, "")

    @patch(
        "existing_installation.run_command_result",
        return_value={
            "returncode": 0,
            "stdout": "1.10.1@26.05.1",
            "stderr": "",
        },
    )
    def test_healthy_executable_reports_version(
        self,
        command_mock,
    ):
        result = inspect_svxlink_executable(
            "/usr/bin/svxlink"
        )

        self.assertEqual(
            result["version"],
            "1.10.1@26.05.1",
        )
        self.assertEqual(
            result["version_source"],
            "executable",
        )
        self.assertTrue(result["runtime_healthy"])
        self.assertEqual(result["runtime_error"], "")
        command_mock.assert_called_once_with([
            "/usr/bin/svxlink",
            "--version",
        ])

    @patch(
        "existing_installation.detect_embedded_version",
        return_value=(
            "1.9.99.36@13.12.1-1903-g8515694c"
        ),
    )
    @patch(
        "existing_installation.run_command_result",
        return_value={
            "returncode": 127,
            "stdout": "",
            "stderr": (
                "error while loading shared libraries: "
                "libsigc-2.0.so.0: cannot open shared "
                "object file"
            ),
        },
    )
    def test_broken_executable_uses_embedded_version(
        self,
        command_mock,
        embedded_mock,
    ):
        result = inspect_svxlink_executable(
            "/usr/bin/svxlink"
        )

        self.assertEqual(
            result["version"],
            "1.9.99.36@13.12.1-1903-g8515694c",
        )
        self.assertEqual(
            result["version_source"],
            "embedded",
        )
        self.assertFalse(result["runtime_healthy"])
        self.assertIn(
            "libsigc-2.0.so.0",
            result["runtime_error"],
        )
        command_mock.assert_called_once_with([
            "/usr/bin/svxlink",
            "--version",
        ])
        embedded_mock.assert_called_once_with(
            "/usr/bin/svxlink"
        )


if __name__ == "__main__":
    unittest.main()
