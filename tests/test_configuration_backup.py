#!/usr/bin/env python3

import tempfile
import unittest

from pathlib import Path

from configuration_backup import (
    ConfigurationBackupError,
    backup_existing_configuration,
)


class ConfigurationBackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

        self.base = Path(self.temporary.name)
        self.backup_root = self.base / "backups"
        self.config_directory = (
            self.base / "source" / "etc" / "svxlink"
        )
        self.environment_file = (
            self.base / "source" / "etc" / "default" / "svxlink"
        )

    def create_config_directory(self):
        self.config_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        (self.config_directory / "svxlink.conf").write_text(
            "[GLOBAL]\nLOGICS=SimplexLogic\n",
            encoding="utf-8",
        )

        module_directory = (
            self.config_directory / "svxlink.d"
        )
        module_directory.mkdir()
        (module_directory / "ModuleEchoLink.conf").write_text(
            "[ModuleEchoLink]\nNAME=EchoLink\n",
            encoding="utf-8",
        )

    def create_environment_file(self):
        self.environment_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.environment_file.write_text(
            "RUNASUSER=svxlink\n",
            encoding="utf-8",
        )

    def test_complete_configuration_is_backed_up(self):
        self.create_config_directory()
        self.create_environment_file()

        destination = backup_existing_configuration(
            backup_root=self.backup_root,
            config_directory=self.config_directory,
            environment_file=self.environment_file,
            timestamp="20260911-210000",
        )

        self.assertEqual(
            destination,
            self.backup_root / "20260911-210000",
        )
        self.assertEqual(
            (
                destination
                / "etc"
                / "svxlink"
                / "svxlink.conf"
            ).read_text(encoding="utf-8"),
            "[GLOBAL]\nLOGICS=SimplexLogic\n",
        )
        self.assertTrue(
            (
                destination
                / "etc"
                / "svxlink"
                / "svxlink.d"
                / "ModuleEchoLink.conf"
            ).is_file()
        )
        self.assertEqual(
            (
                destination
                / "etc"
                / "default"
                / "svxlink"
            ).read_text(encoding="utf-8"),
            "RUNASUSER=svxlink\n",
        )

    def test_config_directory_can_be_backed_up_alone(self):
        self.create_config_directory()

        destination = backup_existing_configuration(
            backup_root=self.backup_root,
            config_directory=self.config_directory,
            environment_file=self.environment_file,
            timestamp="20260911-210001",
        )

        self.assertTrue(
            (
                destination
                / "etc"
                / "svxlink"
                / "svxlink.conf"
            ).is_file()
        )
        self.assertFalse(
            (
                destination
                / "etc"
                / "default"
                / "svxlink"
            ).exists()
        )

    def test_environment_file_can_be_backed_up_alone(self):
        self.create_environment_file()

        destination = backup_existing_configuration(
            backup_root=self.backup_root,
            config_directory=self.config_directory,
            environment_file=self.environment_file,
            timestamp="20260911-210002",
        )

        self.assertTrue(
            (
                destination
                / "etc"
                / "default"
                / "svxlink"
            ).is_file()
        )
        self.assertFalse(
            (
                destination
                / "etc"
                / "svxlink"
            ).exists()
        )

    def test_missing_configuration_is_rejected(self):
        with self.assertRaisesRegex(
            ConfigurationBackupError,
            "No existing SvxLink configuration",
        ):
            backup_existing_configuration(
                backup_root=self.backup_root,
                config_directory=self.config_directory,
                environment_file=self.environment_file,
                timestamp="20260911-210003",
            )

    def test_existing_destination_is_not_overwritten(self):
        self.create_config_directory()

        destination = (
            self.backup_root / "20260911-210004"
        )
        destination.mkdir(parents=True)

        marker = destination / "existing.txt"
        marker.write_text(
            "preserve me",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ConfigurationBackupError,
            "already exists",
        ):
            backup_existing_configuration(
                backup_root=self.backup_root,
                config_directory=self.config_directory,
                environment_file=self.environment_file,
                timestamp="20260911-210004",
            )

        self.assertEqual(
            marker.read_text(encoding="utf-8"),
            "preserve me",
        )

    def test_empty_timestamp_is_rejected(self):
        self.create_config_directory()

        with self.assertRaisesRegex(
            ConfigurationBackupError,
            "timestamp is empty",
        ):
            backup_existing_configuration(
                backup_root=self.backup_root,
                config_directory=self.config_directory,
                environment_file=self.environment_file,
                timestamp="",
            )

    def test_timestamp_path_separator_is_rejected(self):
        self.create_config_directory()

        with self.assertRaisesRegex(
            ConfigurationBackupError,
            "path separator",
        ):
            backup_existing_configuration(
                backup_root=self.backup_root,
                config_directory=self.config_directory,
                environment_file=self.environment_file,
                timestamp="../unsafe",
            )


if __name__ == "__main__":
    unittest.main()
