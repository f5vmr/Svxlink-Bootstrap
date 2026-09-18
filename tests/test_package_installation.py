#!/usr/bin/env python3

import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from package_installation import (
    PackageInstallationError,
    install_package,
    verify_installed_package,
)
from system_access import RootAccessRequiredError


SUPPORTED_INSTALLATION = {
    "supported_version": True,
    "package_managed": True,
    "canonical_executable": "/usr/bin/svxlink",
    "runtime_healthy": True,
    "runtime_error": "",
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

    def test_package_managed_installation_is_required(self):
        installation = dict(SUPPORTED_INSTALLATION)
        installation["package_managed"] = False

        with self.assertRaisesRegex(
            PackageInstallationError,
            "not recorded as a package-managed installation",
        ):
            verify_installed_package(installation)

    def test_canonical_package_executable_is_required(self):
        installation = dict(SUPPORTED_INSTALLATION)
        installation["canonical_executable"] = (
            "/usr/local/bin/svxlink"
        )

        with self.assertRaisesRegex(
            PackageInstallationError,
            "canonical SvxLink executable is not",
        ):
            verify_installed_package(installation)

    def test_healthy_package_executable_is_required(self):
        installation = dict(SUPPORTED_INSTALLATION)
        installation["runtime_healthy"] = False
        installation["runtime_error"] = (
            "libexample.so: cannot open shared object file"
        )

        with self.assertRaisesRegex(
            PackageInstallationError,
            "libexample.so",
        ):
            verify_installed_package(installation)

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
        side_effect=[
            "/usr/bin/apt-get",
            "/usr/bin/systemctl",
        ],
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
        "package_installation.svxlink_package_owns_file",
        return_value=True,
    )
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
        side_effect=[
            "/usr/bin/apt-get",
            "/usr/bin/systemctl",
        ],
    )
    @patch("package_installation.require_root")
    def test_verified_package_is_installed(
        self,
        require_root_mock,
        which_mock,
        run_mock,
        detection_mock,
        ownership_mock,
    ):
        result = install_package(self.package_path)

        self.assertEqual(
            result,
            self.package_path.resolve(),
        )
        require_root_mock.assert_called_once_with()
        self.assertEqual(
            which_mock.call_args_list,
            [
                call("apt-get"),
                call("systemctl"),
            ],
        )
        self.assertEqual(run_mock.call_count, 2)
        detection_mock.assert_called_once_with()
        ownership_mock.assert_called_once_with(
            "/usr/bin/svxlink"
        )
        command = run_mock.call_args_list[0].args[0]
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

        environment = (
            run_mock.call_args_list[0].kwargs["env"]
        )
        self.assertEqual(
            environment["DEBIAN_FRONTEND"],
            "noninteractive",
        )
        self.assertEqual(
            run_mock.call_args_list[1].args[0],
            [
                "/usr/bin/systemctl",
                "daemon-reload",
            ],
        )
        self.assertEqual(
            run_mock.call_args_list[1].kwargs,
            {
                "check": False,
            },
        )
    @patch(
        "package_installation.svxlink_package_owns_file",
        return_value=True,
    )
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
        side_effect=[
            "/usr/bin/apt-get",
            "/usr/bin/systemctl",
        ],
    )
    @patch("package_installation.require_root")
    def test_verified_package_can_be_reinstalled(
        self,
        require_root_mock,
        which_mock,
        run_mock,
        detection_mock,
        ownership_mock,
    ):
        result = install_package(
            self.package_path,
            reinstall=True,
        )

        self.assertEqual(
            result,
            self.package_path.resolve(),
        )
        require_root_mock.assert_called_once_with()
        self.assertEqual(
            which_mock.call_args_list,
            [
                call("apt-get"),
                call("systemctl"),
            ],
        )
        self.assertEqual(run_mock.call_count, 2)
        detection_mock.assert_called_once_with()
        ownership_mock.assert_called_once_with(
            "/usr/bin/svxlink"
        )

        command = run_mock.call_args_list[0].args[0]
        self.assertEqual(
            command,
            [
                "/usr/bin/apt-get",
                "install",
                "--yes",
                "--reinstall",
                "-o",
                "Dpkg::Options::=--force-confold",
                str(self.package_path.resolve()),
            ],
        )
    @patch(
        "package_installation.svxlink_package_owns_file",
        return_value=False,
    )
    @patch(
        "package_installation.detect_existing_installation"
    )
    @patch(
        "package_installation.subprocess.run",
        return_value=SimpleNamespace(returncode=0),
    )
    @patch(
        "package_installation.shutil.which",
        side_effect=[
            "/usr/bin/apt-get",
            "/usr/bin/systemctl",
        ],
    )
    @patch("package_installation.require_root")
    def test_package_ownership_is_required(
        self,
        require_root_mock,
        which_mock,
        run_mock,
        detection_mock,
        ownership_mock,
    ):
        with self.assertRaisesRegex(
            PackageInstallationError,
            "not owned by the svxlink Debian package",
        ):
            install_package(self.package_path)

        require_root_mock.assert_called_once_with()
        self.assertEqual(
            which_mock.call_args_list,
            [
                call("apt-get"),
                call("systemctl"),
            ],
        )
        self.assertEqual(run_mock.call_count, 2)
        ownership_mock.assert_called_once_with(
            "/usr/bin/svxlink"
        )
        detection_mock.assert_not_called()

    @patch(
        "package_installation.svxlink_package_owns_file",
        return_value=True,
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
        side_effect=[
            "/usr/bin/apt-get",
            "/usr/bin/systemctl",
        ],
    )
    @patch("package_installation.require_root")
    def test_post_installation_verification_is_required(
        self,
        require_root_mock,
        which_mock,
        run_mock,
        detection_mock,
        ownership_mock,
    ):
        with self.assertRaisesRegex(
            PackageInstallationError,
            "could not be verified",
        ):
            install_package(self.package_path)

        require_root_mock.assert_called_once_with()
        self.assertEqual(
            which_mock.call_args_list,
            [
                call("apt-get"),
                call("systemctl"),
            ],
        )
        self.assertEqual(run_mock.call_count, 2)
        detection_mock.assert_called_once_with()
        ownership_mock.assert_called_once_with(
            "/usr/bin/svxlink"
        )


if __name__ == "__main__":
    unittest.main()
