#!/usr/bin/env python3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from service_control import (
    ServiceControlError,
    stop_svxlink_service_if_active,
)


class ServiceControlTests(unittest.TestCase):

    @patch("service_control.subprocess.run")
    @patch("service_control.shutil.which")
    def test_inactive_service_is_left_unchanged(
        self,
        which_mock,
        run_mock,
    ):
        stopped = stop_svxlink_service_if_active({
            "service_active_state": "inactive",
        })

        self.assertFalse(stopped)
        which_mock.assert_not_called()
        run_mock.assert_not_called()

    @patch(
        "service_control.shutil.which",
        return_value=None,
    )
    def test_missing_systemctl_is_reported(
        self,
        which_mock,
    ):
        with self.assertRaisesRegex(
            ServiceControlError,
            "systemctl was not found",
        ):
            stop_svxlink_service_if_active({
                "service_active_state": "active",
            })

        which_mock.assert_called_once_with("systemctl")

    @patch(
        "service_control.subprocess.run",
        return_value=SimpleNamespace(returncode=1),
    )
    @patch(
        "service_control.shutil.which",
        return_value="/usr/bin/systemctl",
    )
    def test_service_stop_failure_is_reported(
        self,
        which_mock,
        run_mock,
    ):
        with self.assertRaisesRegex(
            ServiceControlError,
            "exit status 1",
        ):
            stop_svxlink_service_if_active({
                "service_active_state": "active",
            })

        which_mock.assert_called_once_with("systemctl")
        run_mock.assert_called_once_with(
            [
                "/usr/bin/systemctl",
                "stop",
                "svxlink.service",
            ],
            check=False,
        )

    @patch(
        "service_control.subprocess.run",
        return_value=SimpleNamespace(returncode=0),
    )
    @patch(
        "service_control.shutil.which",
        return_value="/usr/bin/systemctl",
    )
    def test_active_service_is_stopped(
        self,
        which_mock,
        run_mock,
    ):
        stopped = stop_svxlink_service_if_active({
            "service_active_state": "active",
        })

        self.assertTrue(stopped)
        which_mock.assert_called_once_with("systemctl")
        run_mock.assert_called_once_with(
            [
                "/usr/bin/systemctl",
                "stop",
                "svxlink.service",
            ],
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
