#!/usr/bin/env python3

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from host_detection import (
    HostDetectionError,
    classify_platform,
    detect_architecture,
    detect_host,
    parse_os_release,
)


class HostDetectionTests(unittest.TestCase):

    def write_os_release(self, directory, contents):
        path = Path(directory) / "os-release"
        path.write_text(
            contents,
            encoding="utf-8",
        )
        return path

    def test_parse_debian_os_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_os_release(
                directory,
                (
                    'PRETTY_NAME="Debian GNU/Linux 12 '
                    '(bookworm)"\n'
                    "ID=debian\n"
                    "VERSION_CODENAME=bookworm\n"
                ),
            )

            result = parse_os_release(path)

        self.assertEqual(result["os_id"], "debian")
        self.assertEqual(
            result["codename"],
            "bookworm",
        )
        self.assertEqual(
            result["pretty_name"],
            "Debian GNU/Linux 12 (bookworm)",
        )

    def test_debian_codename_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_os_release(
                directory,
                (
                    "ID=raspbian\n"
                    "DEBIAN_CODENAME=bookworm\n"
                ),
            )

            result = parse_os_release(path)

        self.assertEqual(result["os_id"], "raspbian")
        self.assertEqual(
            result["codename"],
            "bookworm",
        )

    def test_missing_codename_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_os_release(
                directory,
                "ID=debian\n",
            )

            with self.assertRaises(
                HostDetectionError
            ):
                parse_os_release(path)

    def test_platform_classification(self):
        cases = [
            (
                "debian",
                "Raspberry Pi 5 Model B Rev 1.0",
                "raspberry_pi",
            ),
            (
                "debian",
                "FriendlyElec NanoPi NEO",
                "nanopi_neo",
            ),
            (
                "debian",
                "",
                "debian",
            ),
            (
                "ubuntu",
                "",
                "ubuntu",
            ),
        ]

        for os_id, device_model, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    classify_platform(
                        os_id,
                        device_model,
                    ),
                    expected,
                )

    @patch("host_detection.subprocess.run")
    def test_detect_architecture_uses_dpkg(self, run_mock):
        run_mock.return_value = Mock(
            stdout="arm64\n"
        )

        architecture = detect_architecture()

        self.assertEqual(architecture, "arm64")
        run_mock.assert_called_once_with(
            [
                "/usr/bin/dpkg",
                "--print-architecture",
            ],
            check=True,
            text=True,
            capture_output=True,
        )

    @patch("host_detection.subprocess.run")
    def test_dpkg_failure_is_reported(self, run_mock):
        run_mock.side_effect = (
            subprocess.CalledProcessError(
                1,
                [
                    "/usr/bin/dpkg",
                    "--print-architecture",
                ],
            )
        )

        with self.assertRaises(
            HostDetectionError
        ):
            detect_architecture()

    @patch(
        "host_detection.detect_architecture",
        return_value="arm64",
    )
    def test_detect_raspberry_pi_host(
        self,
        architecture_mock,
    ):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)

            os_release = self.write_os_release(
                directory,
                (
                    'PRETTY_NAME="Debian GNU/Linux 13 '
                    '(trixie)"\n'
                    "ID=debian\n"
                    "VERSION_CODENAME=trixie\n"
                ),
            )

            model_path = (
                directory_path / "device-model"
            )
            model_path.write_bytes(
                b"Raspberry Pi 5 Model B Rev 1.0\x00"
            )

            result = detect_host(
                os_release_path=os_release,
                device_model_path=model_path,
            )

        self.assertEqual(
            result["platform"],
            "raspberry_pi",
        )
        self.assertEqual(result["os_id"], "debian")
        self.assertEqual(result["codename"], "trixie")
        self.assertEqual(
            result["architecture"],
            "arm64",
        )
        architecture_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()