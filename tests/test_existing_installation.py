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
)


class ExistingInstallationTests(unittest.TestCase):

    def test_supported_version_is_recognised(self):
        self.assertTrue(
            version_is_supported(
                "1.10.1@26.05.1"
            )
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
        "existing_installation.detect_svxlink_version",
        return_value="1.10.1@26.05.1",
    )
    @patch(
        "existing_installation.shutil.which",
        return_value="/usr/bin/svxlink",
    )
    def test_manual_supported_installation_is_detected(
        self,
        which_mock,
        version_mock,
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
        "existing_installation.detect_svxlink_version",
        return_value="1.9.0@25.05.1",
    )
    @patch(
        "existing_installation.shutil.which",
        return_value="/usr/bin/svxlink",
    )
    def test_older_installation_is_unsupported(
        self,
        which_mock,
        version_mock,
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


if __name__ == "__main__":
    unittest.main()