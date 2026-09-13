#!/usr/bin/env python3

import unittest

from contextlib import (
    redirect_stderr,
    redirect_stdout,
)
from io import StringIO
from unittest.mock import patch

import bootstrap


HOST = {
    "platform": "debian",
    "pretty_name": "Debian GNU/Linux 12 (bookworm)",
    "os_id": "debian",
    "codename": "bookworm",
    "architecture": "amd64",
    "device_model": "",
}

PACKAGE = {
    "id": "debian_bookworm_amd64",
    "tag": "V26.05.1_amd64_bookworm",
    "asset": "svxlink_26.05.1_amd64.deb",
    "size": 5645706,
    "sha256": (
        "8ff3cb32ebc4f214b3f0d6a3693f6e20"
        "bf645d6d994714001f0c29dda693c422"
    ),
    "url": (
        "https://github.com/f5vmr/svxlink/releases/"
        "download/V26.05.1_amd64_bookworm/"
        "svxlink_26.05.1_amd64.deb"
    ),
}

NOT_INSTALLED = {
    "present": False,
    "supported_version": False,
    "package_managed": False,
    "conversion_candidate": False,
}


UNSUPPORTED_COMPILER_INSTALLATION = {
    "present": True,
    "supported_version": False,
    "package_managed": False,
    "conversion_candidate": True,
    "installation_type": "compiler",
    "version": "1.9.99.36@13.12.1-1903-g8515694c",
    "version_source": "embedded",
    "runtime_healthy": False,
    "runtime_error": (
        "error while loading shared libraries: "
        "libsigc-2.0.so.0"
    ),
    "executable": "/usr/bin/svxlink",
    "service_load_state": "loaded",
    "service_active_state": "failed",
    "package_status": "",
}

class CommandLineTests(unittest.TestCase):
    def test_install_argument_is_parsed(self):
        with patch.object(
            bootstrap.sys,
            "argv",
            ["bootstrap.py", "--install"],
        ):
            arguments = bootstrap.parse_arguments()

        self.assertTrue(arguments.install)
        self.assertIsNone(arguments.download)

    def test_download_argument_is_parsed(self):
        with patch.object(
            bootstrap.sys,
            "argv",
            [
                "bootstrap.py",
                "--download",
                "/tmp/packages",
            ],
        ):
            arguments = bootstrap.parse_arguments()

        self.assertFalse(arguments.install)
        self.assertEqual(
            arguments.download,
            "/tmp/packages",
        )

    def test_install_and_download_are_mutually_exclusive(self):
        stderr = StringIO()

        with (
            patch.object(
                bootstrap.sys,
                "argv",
                [
                    "bootstrap.py",
                    "--install",
                    "--download",
                    "/tmp/packages",
                ],
            ),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as context,
        ):
            bootstrap.parse_arguments()

        self.assertEqual(context.exception.code, 2)
        self.assertIn(
            "not allowed with argument",
            stderr.getvalue(),
        )

    @patch(
        "bootstrap.perform_installation",
        return_value=0,
    )
    @patch(
        "bootstrap.detect_existing_installation",
        return_value=NOT_INSTALLED,
    )
    @patch(
        "bootstrap.resolve_host_package",
        return_value=(HOST, PACKAGE),
    )
    def test_install_mode_routes_to_orchestration(
        self,
        resolve_mock,
        installation_mock,
        perform_mock,
    ):
        stdout = StringIO()

        with redirect_stdout(stdout):
            result = bootstrap.main(install=True)

        self.assertEqual(result, 0)
        resolve_mock.assert_called_once_with()
        installation_mock.assert_called_once_with()
        perform_mock.assert_called_once_with(
            PACKAGE,
            NOT_INSTALLED,
        )

    @patch(
        "bootstrap.perform_installation",
        return_value=0,
    )
    @patch(
        "bootstrap.detect_existing_installation",
        return_value=UNSUPPORTED_COMPILER_INSTALLATION,
    )
    @patch(
        "bootstrap.resolve_host_package",
        return_value=(HOST, PACKAGE),
    )
    def test_unsupported_compiler_installation_is_blocked(
        self,
        resolve_mock,
        installation_mock,
        perform_mock,
    ):
        stdout = StringIO()

        with redirect_stdout(stdout):
            result = bootstrap.main(install=True)

        self.assertEqual(result, 4)
        self.assertIn(
            "Installation type: compiler",
            stdout.getvalue(),
        )
        self.assertIn(
            "libsigc-2.0.so.0",
            stdout.getvalue(),
        )
        perform_mock.assert_not_called()

        installation_mock.assert_called_once_with()
        resolve_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
