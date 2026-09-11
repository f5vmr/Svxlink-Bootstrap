#!/usr/bin/env python3

import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from dashboard_installation import (
    DASHBOARD_INSTALL_DIRECTORY,
    DASHBOARD_REPOSITORY,
    DashboardInstallationError,
    install_dashboard,
)
from system_access import RootAccessRequiredError


class DashboardInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

        self.work_directory = Path(
            self.temporary.name
        )
        self.checkout = (
            self.work_directory
            / "SvxLink-Dash-V4.0"
        )
        self.installer = (
            self.checkout
            / "install"
            / "install-dashboard.sh"
        )

    def create_installer(self, executable=True):
        self.installer.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.installer.write_text(
            "#!/bin/bash\nexit 0\n",
            encoding="utf-8",
        )

        if executable:
            self.installer.chmod(0o755)
        else:
            self.installer.chmod(0o644)

    @patch("dashboard_installation.run_command")
    @patch(
        "dashboard_installation.require_root",
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
            install_dashboard(self.work_directory)

        require_root_mock.assert_called_once_with()
        run_mock.assert_not_called()

    @patch(
        "dashboard_installation.shutil.which",
        return_value=None,
    )
    @patch("dashboard_installation.require_root")
    def test_missing_git_is_rejected(
        self,
        require_root_mock,
        which_mock,
    ):
        with self.assertRaisesRegex(
            DashboardInstallationError,
            "git was not found",
        ):
            install_dashboard(self.work_directory)

        require_root_mock.assert_called_once_with()
        which_mock.assert_called_once_with("git")

    @patch(
        "dashboard_installation.run_command",
        return_value=128,
    )
    @patch(
        "dashboard_installation.shutil.which",
        return_value="/usr/bin/git",
    )
    @patch("dashboard_installation.require_root")
    def test_clone_failure_is_reported(
        self,
        require_root_mock,
        which_mock,
        run_mock,
    ):
        with self.assertRaisesRegex(
            DashboardInstallationError,
            "could not be cloned",
        ):
            install_dashboard(self.work_directory)

        run_mock.assert_called_once()

    @patch(
        "dashboard_installation.run_command",
        return_value=0,
    )
    @patch(
        "dashboard_installation.shutil.which",
        return_value="/usr/bin/git",
    )
    @patch("dashboard_installation.require_root")
    def test_missing_installer_is_rejected(
        self,
        require_root_mock,
        which_mock,
        run_mock,
    ):
        with self.assertRaisesRegex(
            DashboardInstallationError,
            "installer was not found",
        ):
            install_dashboard(self.work_directory)

        run_mock.assert_called_once()

    @patch(
        "dashboard_installation.run_command",
        return_value=0,
    )
    @patch(
        "dashboard_installation.shutil.which",
        return_value="/usr/bin/git",
    )
    @patch("dashboard_installation.require_root")
    def test_non_executable_installer_is_rejected(
        self,
        require_root_mock,
        which_mock,
        run_mock,
    ):
        self.create_installer(executable=False)

        with self.assertRaisesRegex(
            DashboardInstallationError,
            "not executable",
        ):
            install_dashboard(self.work_directory)

        run_mock.assert_called_once()

    @patch(
        "dashboard_installation.run_command",
        side_effect=[0, 7],
    )
    @patch(
        "dashboard_installation.shutil.which",
        return_value="/usr/bin/git",
    )
    @patch("dashboard_installation.require_root")
    def test_installer_failure_is_reported(
        self,
        require_root_mock,
        which_mock,
        run_mock,
    ):
        self.create_installer()

        with self.assertRaisesRegex(
            DashboardInstallationError,
            "exit status 7",
        ):
            install_dashboard(self.work_directory)

        self.assertEqual(run_mock.call_count, 2)

    @patch(
        "dashboard_installation.run_command",
        side_effect=[0, 0],
    )
    @patch(
        "dashboard_installation.shutil.which",
        return_value="/usr/bin/git",
    )
    @patch("dashboard_installation.require_root")
    def test_dashboard_installer_is_run(
        self,
        require_root_mock,
        which_mock,
        run_mock,
    ):
        self.create_installer()

        result = install_dashboard(
            self.work_directory
        )

        self.assertEqual(
            result,
            DASHBOARD_INSTALL_DIRECTORY,
        )
        self.assertEqual(run_mock.call_count, 2)

        clone_command = (
            run_mock.call_args_list[0].args[0]
        )
        self.assertEqual(
            clone_command,
            [
                "/usr/bin/git",
                "clone",
                "--depth",
                "1",
                "--branch",
                "main",
                "--single-branch",
                DASHBOARD_REPOSITORY,
                str(self.checkout),
            ],
        )

        installer_call = (
            run_mock.call_args_list[1]
        )
        self.assertEqual(
            installer_call.args[0],
            [str(self.installer)],
        )
        self.assertEqual(
            installer_call.kwargs[
                "working_directory"
            ],
            self.checkout,
        )


if __name__ == "__main__":
    unittest.main()
