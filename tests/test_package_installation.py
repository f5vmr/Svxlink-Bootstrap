#!/usr/bin/env python3

import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from package_installation import (
    PackageInstallationError,
    install_package,
)
from system_access import RootAccessRequiredError


SUPPORTED_INSTALLATION = {
    "supported_version": True,
}

UNSUPPORTED_INSTALLATION = {
    "supported_version": False,
}


class PackageInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

        self.package_path = (
            Path(self.temporary.name)
            / "svxlink_26.05.1_amd64.deb"
        )
        self.package_path.write_bytes(b"test package")

    @patch("package_installation.subprocess.run")
    @patch(
        "package_installation.require_root",
        side_effect=RootAccessRequiredError(
            "Installation requires root privileges."
        ),
    )
    def test_non_root_is_rejected(
        self,
        require_root_mock,
        run_mock,
    ):
        with self.assertRaisesRegex(
            RootAccessRequiredError,
            "requires root privileges",
        ):
            install_package(self.package_path)

        require_root_mock.assert_called_once_with()
        run_mock.assert_not_called()

    @patch("package_installation.require_root")
    def test_missing_package_is_rejected(
        self,
        require_root_mock,
    ):
        missing_path = (
            Path(self.temporary.name) / "missing.deb"
        )

        with self.assertRaisesRegex(
            PackageInstallationError,
            "does not exist",
        ):
            install_package(missing_path)

        require_root_mock.assert_called_once_with()

    @patch("package_installation.require_root")
    def test_non_debian_archive_is_rejected(
        self,
        require_root_mock,
    ):
        archive = (
            Path(self.temporary.name) / "svxlink.tar.gz"
        )
        archive.write_bytes(b"not a deb")

        with self.assertRaisesRegex(
            PackageInstallationError,
            "not a Debian archive",
        ):
            install_package(archive)

        require_root_mock.assert_called_once_with()

    @patch(
        "package_installation.shutil.which",
        return_value=None,
    )
    @patch("package_installation.require_root")
    def test_missing_apt_get_is_rejected(
        self,
        require_root_mock,
        which_mock,
    ):
        with self.assertRaisesRegex(
            PackageInstallationError,
            "apt-get was not found",
        ):
            install_package(self.package_path)

        require_root_mock.assert_called_once_with()
        which_mock.assert_called_once_with("apt-get")

    @patch(
        "package_installation.subprocess.run",
        return_value=SimpleNamespace(returncode=100),
    )
    @patch(
        "package_installation.shutil.which",
        return_value="/usr/bin/apt-get",
    )
    @patch("package_installation.require_root")
    def test_apt_failure_is_reported(
        self,
        require_root_mock,
        which_mock,
        run_mock,
    ):
        with self.assertRaisesRegex(
            PackageInstallationError,
            "exit status 100",
        ):
            install_package(self.package_path)

        require_root_mock.assert_called_once_with()
        which_mock.assert_called_once_with("apt-get")
        run_mock.assert_called_once()

    @patch(
        "package_installation.detect_existing_installation",
        return_value=SUPPORTED_INSTALLATION,
    )
    @patch(
        "package_installation.subprocess.run",
        return_value=SimpleNamespace(returncode=0),
    )
    @patch(
        "package_installation.shutil.which",
        return_value="/usr/bin/apt-get",
    )
    @patch("package_installation.require_root")
    def test_verified_package_is_installed(
        self,
        require_root_mock,
        which_mock,
        run_mock,
        detection_mock,
    ):
        result = install_package(self.package_path)

        self.assertEqual(
            result,
            self.package_path.resolve(),
        )
        require_root_mock.assert_called_once_with()
        which_mock.assert_called_once_with("apt-get")
        run_mock.assert_called_once()
        detection_mock.assert_called_once_with()

        command = run_mock.call_args.args[0]
        self.assertEqual(
            command,
            [
                "/usr/bin/apt-get",
                "install",
                "--yes",
                "-o",
                "Dpkg::Options::=--force-confold",
                str(self.package_path.resolve()),
            ],
        )

        environment = run_mock.call_args.kwargs["env"]
        self.assertEqual(
            environment["DEBIAN_FRONTEND"],
            "noninteractive",
        )

    @patch(
        "package_installation.detect_existing_installation",
        return_value=UNSUPPORTED_INSTALLATION,
    )
    @patch(
        "package_installation.subprocess.run",
        return_value=SimpleNamespace(returncode=0),
    )
    @patch(
        "package_installation.shutil.which",
        return_value="/usr/bin/apt-get",
    )
    @patch("package_installation.require_root")
    def test_post_installation_verification_is_required(
        self,
        require_root_mock,
        which_mock,
        run_mock,
        detection_mock,
    ):
        with self.assertRaisesRegex(
            PackageInstallationError,
            "could not be verified",
        ):
            install_package(self.package_path)

        require_root_mock.assert_called_once_with()
        which_mock.assert_called_once_with("apt-get")
        run_mock.assert_called_once()
        detection_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
