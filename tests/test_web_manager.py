#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch

from web_manager import (
    create_app,
    determine_local_address,
    main as web_manager_main,
    stop_server_after_handover,
)
from web_installation import (
    InstallationAlreadyStartedError,
    InstallationState,
)


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

OLDER_COMPILER_INSTALLATION = {
    "present": True,
    "installation_type": "compiler",
    "version": "1.9.0@25.05.1",
    "executable": "/usr/bin/svxlink",
    "canonical_executable": "/usr/bin/svxlink",
    "service_load_state": "loaded",
    "service_active_state": "active",
    "package_status": "",
    "supported_version": False,
    "package_managed": False,
    "conversion_candidate": True,
}


class WebManagerTests(unittest.TestCase):

    def setUp(self):
        self.installation_state = InstallationState()
        self.dashboard_url = (
            "http:"
            "//192.0.2.10:5000/start"
        )
        self.app = create_app(
            access_token="test-access-token",
            confirmation_token="test-confirmation-token",
            installation_state=self.installation_state,
            dashboard_url=self.dashboard_url,
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

    @patch(
        "web_manager.detect_existing_installation",
        return_value=OLDER_COMPILER_INSTALLATION,
    )
    @patch(
        "web_manager.resolve_host_package",
        return_value=(HOST, PACKAGE),
    )
    def test_older_compiler_upgrade_is_offered(
        self,
        resolve_mock,
        installation_mock,
    ):
        response = self.client.get(
            "/?token=test-access-token"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"recognised older compiler-installed SvxLink",
            response.data,
        )
        self.assertIn(
            b"1.9.0@25.05.1",
            response.data,
        )
        self.assertIn(
            b"upgraded to the verified SvxLink 26.05.1",
            response.data,
        )
        self.assertIn(
            b"Install SvxLink-Dash V4.0",
            response.data,
        )
        resolve_mock.assert_called_once_with()
        installation_mock.assert_called_once_with()

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

    @patch("web_manager.start_installation_job")
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
    def test_authorised_installation_is_started(
        self,
        resolve_mock,
        installation_mock,
        action_mock,
        start_mock,
    ):
        response = self.client.post(
            "/install?token=test-access-token",
            data={
                "confirmation_token": (
                    "test-confirmation-token"
                ),
            },
        )

        self.assertEqual(response.status_code, 202)
        start_mock.assert_called_once_with(
            self.installation_state,
            PACKAGE,
            INSTALLATION,
            self.dashboard_url,
        )
        resolve_mock.assert_called_once_with()
        installation_mock.assert_called_once_with()
        action_mock.assert_called_once_with(
            INSTALLATION
        )

    @patch("web_manager.resolve_host_package")
    def test_installation_requires_confirmation_token(
        self,
        resolve_mock,
    ):
        response = self.client.post(
            "/install?token=test-access-token",
            data={
                "confirmation_token": "incorrect-token",
            },
        )

        self.assertEqual(response.status_code, 403)
        resolve_mock.assert_not_called()

    @patch("web_manager.start_installation_job")
    @patch(
        "web_manager.determine_installation_action",
        return_value="block",
    )
    @patch(
        "web_manager.detect_existing_installation",
        return_value=INSTALLATION,
    )
    @patch(
        "web_manager.resolve_host_package",
        return_value=(HOST, PACKAGE),
    )
    def test_blocked_installation_is_not_started(
        self,
        resolve_mock,
        installation_mock,
        action_mock,
        start_mock,
    ):
        response = self.client.post(
            "/install?token=test-access-token",
            data={
                "confirmation_token": (
                    "test-confirmation-token"
                ),
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["status"],
            "blocked",
        )
        start_mock.assert_not_called()
        resolve_mock.assert_called_once_with()
        installation_mock.assert_called_once_with()
        action_mock.assert_called_once_with(
            INSTALLATION
        )

    @patch(
        "web_manager.start_installation_job",
        side_effect=InstallationAlreadyStartedError(
            "The installation has already been started."
        ),
    )
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
    def test_second_installation_start_is_rejected(
        self,
        resolve_mock,
        installation_mock,
        action_mock,
        start_mock,
    ):
        response = self.client.post(
            "/install?token=test-access-token",
            data={
                "confirmation_token": (
                    "test-confirmation-token"
                ),
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["status"],
            "conflict",
        )
        start_mock.assert_called_once_with(
            self.installation_state,
            PACKAGE,
            INSTALLATION,
            self.dashboard_url,
        )

    @patch("web_manager.socket.socket")
    def test_local_address_uses_default_route(
        self,
        socket_mock,
    ):
        probe = Mock()
        probe.getsockname.return_value = (
            "192.0.2.25",
            49152,
        )
        socket_mock.return_value.__enter__.return_value = (
            probe
        )

        address = determine_local_address()

        self.assertEqual(address, "192.0.2.25")
        probe.connect.assert_called_once_with(
            ("192.0.2.1", 9)
        )

    @patch("web_manager.threading.Thread")
    @patch("web_manager.make_server")
    @patch("web_manager.create_app")
    @patch(
        "web_manager.determine_local_address",
        return_value="192.0.2.25",
    )
    @patch(
        "web_manager.secrets.token_urlsafe",
        side_effect=[
            "access-token",
            "confirmation-token",
        ],
    )
    def test_main_starts_temporary_manager(
        self,
        token_mock,
        address_mock,
        create_app_mock,
        make_server_mock,
        thread_mock,
    ):
        app = Mock()
        server = Mock()
        shutdown_monitor = Mock()
        create_app_mock.return_value = app
        make_server_mock.return_value = server
        thread_mock.return_value = shutdown_monitor

        result = web_manager_main(
            bind_address="0.0.0.0",
            port=8765,
        )

        self.assertEqual(result, 0)

        create_arguments = (
            create_app_mock.call_args.kwargs
        )
        installation_state = create_arguments[
            "installation_state"
        ]

        self.assertIsInstance(
            installation_state,
            InstallationState,
        )
        self.assertEqual(
            create_arguments["access_token"],
            "access-token",
        )
        self.assertEqual(
            create_arguments["confirmation_token"],
            "confirmation-token",
        )
        self.assertEqual(
            create_arguments["dashboard_url"],
            (
                "http:"
                "//192.0.2.25:5000/start"
            ),
        )

        make_server_mock.assert_called_once_with(
            "0.0.0.0",
            8765,
            app,
            threaded=True,
        )
        thread_mock.assert_called_once_with(
            target=stop_server_after_handover,
            args=(
                installation_state,
                server,
            ),
            daemon=True,
        )
        shutdown_monitor.start.assert_called_once_with()
        server.serve_forever.assert_called_once_with()
        server.server_close.assert_called_once_with()
        self.assertEqual(token_mock.call_count, 2)
        address_mock.assert_called_once_with()


    @patch("web_manager.time.sleep")
    def test_completed_handover_stops_server(
        self,
        sleep_mock,
    ):
        state = InstallationState()
        server = Mock()

        state.start()
        state.complete(
            "http:"
            "//192.0.2.25:5000/start"
        )

        stop_server_after_handover(
            state,
            server,
            poll_interval=0.01,
            handover_delay=5.0,
        )

        sleep_mock.assert_called_once_with(5.0)
        server.shutdown.assert_called_once_with()

    @patch("web_manager.time.sleep")
    def test_failed_installation_keeps_server_available(
        self,
        sleep_mock,
    ):
        state = InstallationState()
        server = Mock()

        state.start()
        state.fail(
            "package",
            "APT installation failed.",
        )

        stop_server_after_handover(
            state,
            server,
            poll_interval=0.01,
            handover_delay=5.0,
        )

        sleep_mock.assert_not_called()
        server.shutdown.assert_not_called()


if __name__ == "__main__":
    unittest.main()
