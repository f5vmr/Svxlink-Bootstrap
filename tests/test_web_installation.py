#!/usr/bin/env python3
import unittest

from web_installation import (
    INSTALLATION_STAGES,
    InstallationAlreadyStartedError,
    InstallationState,
    InstallationStateError,
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


if __name__ == "__main__":
    unittest.main()
