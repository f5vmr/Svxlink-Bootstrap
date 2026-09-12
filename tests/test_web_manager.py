#!/usr/bin/env python3
import unittest
from unittest.mock import patch

from web_manager import create_app
from web_installation import InstallationState


HOST = {
    "platform": "raspberry_pi",
    "pretty_name": "Debian GNU/Linux 13 (trixie)",
    "architecture": "arm64",
    "device_model": "Raspberry Pi 5 Model B Rev 1.0",
}

PACKAGE = {
    "asset": "svxlink_26.05.1_arm64.deb",
    "tag": "V26.05.1_arm64_Trixie",
    "size": 5238768,
    "sha256": (
        "e9775c769aed7485b95e3a0165c8eadd"
        "6be94162f82a09fd0b925ab3f1f0de43"
    ),
}

INSTALLATION = {
    "present": False,
    "installation_type": "absent",
    "version": "",
    "executable": "",
    "service_load_state": "",
    "service_active_state": "",
    "package_status": "",
    "supported_version": False,
    "package_managed": False,
    "conversion_candidate": False,
}


class WebManagerTests(unittest.TestCase):

    def setUp(self):
        self.installation_state = InstallationState()
        self.app = create_app(
            access_token="test-access-token",
            confirmation_token="test-confirmation-token",
            installation_state=self.installation_state,
        )
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    @patch(
        "web_manager.determine_installation_action",
        return_value="install",
    )
    @patch(
        "web_manager.detect_existing_installation",
        return_value=INSTALLATION,
    )
    @patch(
        "web_manager.resolve_host_package",
        return_value=(HOST, PACKAGE),
    )
    def test_authorised_inspection_is_rendered(
        self,
        resolve_mock,
        installation_mock,
        action_mock,
    ):
        response = self.client.get(
            "/?token=test-access-token"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"SvxLink Bootstrap",
            response.data,
        )
        self.assertIn(
            b"Debian GNU/Linux 13",
            response.data,
        )
        self.assertIn(
            b"svxlink_26.05.1_arm64.deb",
            response.data,
        )
        self.assertIn(
            b"Install SvxLink-Dash V4.0",
            response.data,
        )
        self.assertIn(
            b"bootstrap.js",
            response.data,
        )
        self.assertIn(
            b"/status?token=test-access-token",
            response.data,
        )
        resolve_mock.assert_called_once_with()
        installation_mock.assert_called_once_with()
        action_mock.assert_called_once_with(
            INSTALLATION
        )

    @patch("web_manager.resolve_host_package")
    def test_invalid_access_token_is_rejected(
        self,
        resolve_mock,
    ):
        response = self.client.get(
            "/?token=incorrect-token"
        )

        self.assertEqual(response.status_code, 403)
        resolve_mock.assert_not_called()

    def test_authorised_status_is_returned(self):
        response = self.client.get(
            "/status?token=test-access-token"
        )

        self.assertEqual(response.status_code, 200)

        status = response.get_json()

        self.assertFalse(status["started"])
        self.assertEqual(status["status"], "idle")
        self.assertEqual(status["sequence"], 0)

    def test_status_requires_access_token(self):
        response = self.client.get(
            "/status?token=incorrect-token"
        )

        self.assertEqual(response.status_code, 403)

    def test_installation_endpoint_remains_disabled(self):
        response = self.client.post(
            "/install?token=test-access-token",
            data={
                "confirmation_token": (
                    "test-confirmation-token"
                ),
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn(
            b"not enabled yet",
            response.data,
        )


if __name__ == "__main__":
    unittest.main()
