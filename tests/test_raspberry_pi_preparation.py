#!/usr/bin/env python3

import stat
import tempfile
import unittest

from pathlib import Path
from unittest.mock import Mock, call, patch

import raspberry_pi_preparation as preparation


class RaspberryPiPreparationTests(unittest.TestCase):

    def test_replace_managed_line_preserves_unrelated_content(self):
        content = (
            "# Raspberry Pi configuration\n"
            "enable_uart=1\n"
            "dtparam=audio=on\n"
            "dtparam=audio=off\n"
        )

        result = preparation.replace_managed_line(
            content,
            r"^\s*dtparam\s*=\s*audio\s*=",
            "dtparam=audio=off",
        )

        self.assertEqual(
            result,
            (
                "# Raspberry Pi configuration\n"
                "enable_uart=1\n"
                "dtparam=audio=off\n"
            ),
        )

    def test_configure_boot_audio_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.txt"
            path.write_text(
                (
                    "# Existing setting\n"
                    "dtparam=audio=on\n"
                    "enable_uart=1\n"
                ),
                encoding="utf-8",
            )

            first_result = (
                preparation.configure_boot_audio(path)
            )
            second_result = (
                preparation.configure_boot_audio(path)
            )

            self.assertTrue(first_result)
            self.assertFalse(second_result)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                (
                    "# Existing setting\n"
                    "dtparam=audio=off\n"
                    "enable_uart=1\n"
                ),
            )

    def test_configure_boot_audio_disables_hdmi_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.txt"
            path.write_text(
                (
                    "dtparam=audio=on\n"
                    "dtoverlay=vc4-kms-v3d\n"
                ),
                encoding="utf-8",
            )

            result = preparation.configure_boot_audio(
                path
            )

            self.assertTrue(result)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                (
                    "dtparam=audio=off\n"
                    "dtoverlay=vc4-kms-v3d,noaudio\n"
                ),
            )

    def test_configure_boot_audio_preserves_vc4_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.txt"
            path.write_text(
                (
                    "#dtoverlay=vc4-kms-v3d\n"
                    "dtoverlay=vc4-kms-v3d,cma-256\n"
                ),
                encoding="utf-8",
            )

            result = preparation.configure_boot_audio(
                path
            )

            self.assertTrue(result)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                (
                    "#dtoverlay=vc4-kms-v3d\n"
                    "dtoverlay=vc4-kms-v3d,cma-256,noaudio\n"
                    "\n"
                    "dtparam=audio=off\n"
                ),
            )

    def test_configure_boot_audio_noaudio_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.txt"
            path.write_text(
                (
                    "dtparam=audio=off\n"
                    "dtoverlay=vc4-kms-v3d,noaudio\n"
                ),
                encoding="utf-8",
            )

            first_result = (
                preparation.configure_boot_audio(path)
            )
            second_result = (
                preparation.configure_boot_audio(path)
            )

            self.assertFalse(first_result)
            self.assertFalse(second_result)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                (
                    "dtparam=audio=off\n"
                    "dtoverlay=vc4-kms-v3d,noaudio\n"
                ),
            )

    def test_module_blacklist_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blacklist.conf"
            path.write_text(
                "blacklist unrelated_module\n",
                encoding="utf-8",
            )

            result = (
                preparation.configure_module_blacklist(
                    path
                )
            )

            self.assertTrue(result)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                (
                    "blacklist unrelated_module\n"
                    "\n"
                    "blacklist snd_bcm2835\n"
                ),
            )

    def test_usb_audio_reserves_two_indices(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asound.conf"
            path.write_text(
                (
                    "# Existing USB audio setting\n"
                    "options snd_usb_audio index=3\n"
                ),
                encoding="utf-8",
            )

            result = preparation.configure_usb_audio(
                path
            )

            self.assertTrue(result)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                (
                    "# Existing USB audio setting\n"
                    "options snd_usb_audio index=0,1\n"
                ),
            )

    def test_hidraw_rule_is_vendor_specific(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hidraw.rules"

            first_result = (
                preparation.configure_hidraw_rule(path)
            )
            second_result = (
                preparation.configure_hidraw_rule(path)
            )

            self.assertTrue(first_result)
            self.assertFalse(second_result)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                preparation.HIDRAW_RULE + "\n",
            )
            self.assertIn(
                'ATTRS{idVendor}=="0d8c"',
                path.read_text(encoding="utf-8"),
            )
            self.assertNotIn(
                'MODE="0666"',
                path.read_text(encoding="utf-8"),
            )

    @patch(
        "raspberry_pi_preparation.pwd.getpwnam",
        side_effect=KeyError("pi"),
    )
    def test_missing_pi_user_is_rejected(
        self,
        getpwnam_mock,
    ):
        with self.assertRaises(
            preparation.RaspberryPiPreparationError
        ) as context:
            preparation.validate_pi_user()

        self.assertIn(
            "user 'pi' does not exist",
            str(context.exception),
        )
        getpwnam_mock.assert_called_once_with("pi")

    @patch(
        "raspberry_pi_preparation.subprocess.run"
    )
    @patch(
        "raspberry_pi_preparation.shutil.which",
        return_value="/usr/sbin/visudo",
    )
    @patch(
        "raspberry_pi_preparation.pwd.getpwnam",
        return_value=object(),
    )
    def test_sudoers_rule_is_validated_before_install(
        self,
        getpwnam_mock,
        which_mock,
        run_mock,
    ):
        run_mock.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        with tempfile.TemporaryDirectory() as directory:
            path = (
                Path(directory)
                / "sudoers.d"
                / "010_pi-nopasswd"
            )

            result = (
                preparation.configure_pi_sudoers(path)
            )

            self.assertTrue(result)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "pi ALL=(ALL) NOPASSWD: ALL\n",
            )
            self.assertEqual(
                stat.S_IMODE(path.stat().st_mode),
                0o440,
            )

        getpwnam_mock.assert_called_once_with("pi")
        which_mock.assert_called_once_with("visudo")
        self.assertEqual(
            run_mock.call_args.args[0][0:2],
            [
                "/usr/sbin/visudo",
                "-cf",
            ],
        )

    @patch(
        "raspberry_pi_preparation.run_udevadm"
    )
    def test_reload_udev_rules_reloads_and_triggers(
        self,
        run_mock,
    ):
        preparation.reload_udev_rules()

        self.assertEqual(
            run_mock.call_args_list,
            [
                call([
                    "control",
                    "--reload-rules",
                ]),
                call([
                    "trigger",
                ]),
            ],
        )

    @patch(
        "raspberry_pi_preparation.reload_udev_rules"
    )
    @patch(
        "raspberry_pi_preparation.configure_hidraw_rule",
        return_value=True,
    )
    @patch(
        "raspberry_pi_preparation.configure_usb_audio",
        return_value=True,
    )
    @patch(
        "raspberry_pi_preparation.configure_module_blacklist",
        return_value=False,
    )
    @patch(
        "raspberry_pi_preparation.configure_boot_audio",
        return_value=True,
    )
    @patch(
        "raspberry_pi_preparation.configure_pi_sudoers",
        return_value=False,
    )
    @patch(
        "raspberry_pi_preparation.require_root"
    )
    def test_prepare_reports_changes_and_reboot(
        self,
        root_mock,
        sudoers_mock,
        boot_mock,
        blacklist_mock,
        usb_mock,
        hidraw_mock,
        reload_mock,
    ):
        paths = [
            Path("/test/boot"),
            Path("/test/blacklist"),
            Path("/test/asound"),
            Path("/test/hidraw"),
            Path("/test/sudoers"),
        ]

        result = preparation.prepare_raspberry_pi(
            boot_config_path=paths[0],
            blacklist_path=paths[1],
            usb_audio_path=paths[2],
            hidraw_rule_path=paths[3],
            sudoers_path=paths[4],
        )

        self.assertEqual(
            result,
            {
                "changed": [
                    "boot_audio",
                    "usb_audio",
                    "hidraw_rule",
                ],
                "reboot_required": True,
            },
        )
        root_mock.assert_called_once_with()
        sudoers_mock.assert_called_once_with(paths[4])
        boot_mock.assert_called_once_with(paths[0])
        blacklist_mock.assert_called_once_with(
            paths[1]
        )
        usb_mock.assert_called_once_with(paths[2])
        hidraw_mock.assert_called_once_with(paths[3])
        reload_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
