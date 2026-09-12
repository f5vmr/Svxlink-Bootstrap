#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch

from web_installation import (
    INSTALLATION_STAGES,
    InstallationAlreadyStartedError,
    InstallationState,
    InstallationStateError,
    run_installation_job,
    start_installation_job,
)


class InstallationStateTests(unittest.TestCase):

    def test_initial_state_is_idle(self):
        state = InstallationState()
        snapshot = state.snapshot()

        self.assertFalse(snapshot["started"])
        self.assertEqual(snapshot["status"], "idle")
        self.assertEqual(
            snapshot["stages"],
            {
                stage: "pending"
                for stage in INSTALLATION_STAGES
            },
        )

    def test_installation_can_start_only_once(self):
        state = InstallationState()
        state.start()

        with self.assertRaisesRegex(
            InstallationAlreadyStartedError,
            "already been started",
        ):
            state.start()

    def test_stage_progress_is_recorded(self):
        state = InstallationState()
        state.start()
        state.update_stage(
            "download",
            "running",
            "Downloading the selected package.",
        )
        state.update_stage(
            "download",
            "completed",
            "Package download verified.",
        )

        snapshot = state.snapshot()

        self.assertEqual(
            snapshot["stages"]["download"],
            "completed",
        )
        self.assertEqual(snapshot["sequence"], 3)
        self.assertIn(
            "Package download verified.",
            snapshot["log"],
        )

    def test_unknown_stage_is_rejected(self):
        state = InstallationState()
        state.start()

        with self.assertRaisesRegex(
            InstallationStateError,
            "Unknown installation stage",
        ):
            state.update_stage(
                "unknown",
                "running",
            )

    def test_installation_can_fail(self):
        state = InstallationState()
        state.start()
        state.fail(
            "package",
            "APT installation failed.",
        )

        snapshot = state.snapshot()

        self.assertEqual(snapshot["status"], "failed")
        self.assertEqual(
            snapshot["current_stage"],
            "package",
        )
        self.assertEqual(
            snapshot["stages"]["package"],
            "failed",
        )

    def test_installation_can_complete(self):
        state = InstallationState()
        state.start()
        state.update_stage(
            "handover",
            "running",
            "Preparing Dashboard handover.",
        )
        state.complete(
            "http://192.0.2.10:5000/start"
        )

        snapshot = state.snapshot()

        self.assertEqual(
            snapshot["status"],
            "completed",
        )
        self.assertEqual(
            snapshot["redirect_url"],
            "http://192.0.2.10:5000/start",
        )
        self.assertEqual(
            snapshot["stages"]["handover"],
            "completed",
        )

    def test_snapshot_cannot_modify_internal_state(self):
        state = InstallationState()
        snapshot = state.snapshot()
        snapshot["stages"]["backup"] = "completed"

        self.assertEqual(
            state.snapshot()["stages"]["backup"],
            "pending",
        )

    def test_runner_completes_successful_installation(self):
        state = InstallationState()
        package = object()
        installation = object()
        dashboard_url = "http://192.0.2.10:5000/start"

        def perform(
            received_package,
            received_installation,
            progress,
        ):
            self.assertIs(received_package, package)
            self.assertIs(
                received_installation,
                installation,
            )
            progress(
                "package",
                "running",
                "Installing SvxLink.",
            )
            progress(
                "package",
                "completed",
                "SvxLink installed.",
            )
            progress(
                "dashboard",
                "completed",
                "Dashboard installed.",
            )
            return 0

        state.start()

        with patch(
            "web_installation.bootstrap.perform_installation",
            side_effect=perform,
        ):
            run_installation_job(
                state,
                package,
                installation,
                dashboard_url,
            )

        snapshot = state.snapshot()
        self.assertEqual(snapshot["status"], "completed")
        self.assertEqual(
            snapshot["redirect_url"],
            dashboard_url,
        )
        self.assertEqual(
            snapshot["stages"]["handover"],
            "completed",
        )

    def test_runner_records_reported_failure(self):
        state = InstallationState()

        def perform(package, installation, progress):
            progress(
                "package",
                "running",
                "Installing SvxLink.",
            )
            progress(
                "package",
                "failed",
                "APT installation failed.",
            )
            return 7

        state.start()

        with patch(
            "web_installation.bootstrap.perform_installation",
            side_effect=perform,
        ):
            run_installation_job(
                state,
                object(),
                object(),
                "http://192.0.2.10:5000/start",
            )

        snapshot = state.snapshot()
        self.assertEqual(snapshot["status"], "failed")
        self.assertEqual(
            snapshot["current_stage"],
            "package",
        )
        self.assertEqual(
            snapshot["message"],
            "APT installation failed.",
        )

    def test_runner_maps_unreported_failure(self):
        state = InstallationState()
        state.start()

        with patch(
            "web_installation.bootstrap.perform_installation",
            return_value=9,
        ):
            run_installation_job(
                state,
                object(),
                object(),
                "http://192.0.2.10:5000/start",
            )

        snapshot = state.snapshot()
        self.assertEqual(snapshot["status"], "failed")
        self.assertEqual(
            snapshot["current_stage"],
            "service",
        )
        self.assertEqual(
            snapshot["stages"]["service"],
            "failed",
        )

    def test_start_creates_one_daemon_worker(self):
        state = InstallationState()
        package = object()
        installation = object()
        dashboard_url = "http://192.0.2.10:5000/start"
        worker = Mock()

        with patch(
            "web_installation.threading.Thread",
            return_value=worker,
        ) as thread_mock:
            result = start_installation_job(
                state,
                package,
                installation,
                dashboard_url,
            )

        self.assertIs(result, worker)
        self.assertEqual(
            state.snapshot()["status"],
            "running",
        )
        thread_mock.assert_called_once_with(
            target=run_installation_job,
            args=(
                state,
                package,
                installation,
                dashboard_url,
            ),
            daemon=True,
        )
        worker.start.assert_called_once_with()

if __name__ == "__main__":
    unittest.main()
