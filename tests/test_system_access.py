#!/usr/bin/env python3

import unittest

from unittest.mock import patch

from system_access import (
    RootAccessRequiredError,
    require_root,
    running_as_root,
)


class SystemAccessTests(unittest.TestCase):
    @patch(
        "system_access.os.geteuid",
        return_value=0,
    )
    def test_running_as_root(self, geteuid_mock):
        self.assertTrue(running_as_root())
        geteuid_mock.assert_called_once_with()

    @patch(
        "system_access.os.geteuid",
        return_value=1000,
    )
    def test_not_running_as_root(self, geteuid_mock):
        self.assertFalse(running_as_root())
        geteuid_mock.assert_called_once_with()

    @patch(
        "system_access.os.geteuid",
        return_value=0,
    )
    def test_require_root_accepts_root(self, geteuid_mock):
        self.assertIsNone(require_root())
        geteuid_mock.assert_called_once_with()

    @patch(
        "system_access.os.geteuid",
        return_value=1000,
    )
    def test_require_root_rejects_non_root(
        self,
        geteuid_mock,
    ):
        with self.assertRaisesRegex(
            RootAccessRequiredError,
            "requires root privileges",
        ):
            require_root()

        geteuid_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
    