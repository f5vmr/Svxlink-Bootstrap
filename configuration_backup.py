#!/usr/bin/env python3

"""
Create a timestamped backup of an existing SvxLink configuration.
"""

import shutil
import tempfile

from datetime import datetime
from pathlib import Path


DEFAULT_BACKUP_ROOT = Path(
    "/var/backups/svxlink-bootstrap"
)

DEFAULT_CONFIG_DIRECTORY = Path("/etc/svxlink")

DEFAULT_ENVIRONMENT_FILE = Path(
    "/etc/default/svxlink"
)


class ConfigurationBackupError(RuntimeError):
    """Raised when the SvxLink configuration cannot be backed up."""


def create_backup_timestamp():
    """Return a timestamp suitable for a backup directory name."""

    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup_existing_configuration(
    backup_root=DEFAULT_BACKUP_ROOT,
    config_directory=DEFAULT_CONFIG_DIRECTORY,
    environment_file=DEFAULT_ENVIRONMENT_FILE,
    timestamp=None,
):
    """
    Back up existing SvxLink configuration using its original layout.

    The completed backup contains paths such as:

        etc/svxlink/svxlink.conf
        etc/default/svxlink
    """

    backup_root = Path(backup_root)
    config_directory = Path(config_directory)
    environment_file = Path(environment_file)

    if timestamp is None:
        timestamp = create_backup_timestamp()

    timestamp = str(timestamp).strip()

    if not timestamp:
        raise ConfigurationBackupError(
            "The backup timestamp is empty."
        )

    if "/" in timestamp or "\\" in timestamp:
        raise ConfigurationBackupError(
            "The backup timestamp contains a path separator."
        )

    sources_present = (
        config_directory.is_dir()
        or environment_file.is_file()
    )

    if not sources_present:
        raise ConfigurationBackupError(
            "No existing SvxLink configuration was found "
            "to back up."
        )

    destination = backup_root / timestamp

    if destination.exists():
        raise ConfigurationBackupError(
            f"Backup destination already exists: {destination}"
        )

    try:
        backup_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        staging_path = Path(
            tempfile.mkdtemp(
                prefix=f".{timestamp}-",
                dir=backup_root,
            )
        )

    except OSError as exc:
        raise ConfigurationBackupError(
            f"Could not prepare the backup directory: {exc}"
        ) from exc

    try:
        staged_etc = staging_path / "etc"
        staged_etc.mkdir()

        if config_directory.is_dir():
            shutil.copytree(
                config_directory,
                staged_etc / "svxlink",
                symlinks=True,
                copy_function=shutil.copy2,
            )

        if environment_file.is_file():
            staged_default = staged_etc / "default"
            staged_default.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                environment_file,
                staged_default / "svxlink",
            )

        staging_path.rename(destination)

    except (OSError, shutil.Error) as exc:
        shutil.rmtree(
            staging_path,
            ignore_errors=True,
        )
        raise ConfigurationBackupError(
            f"SvxLink configuration backup failed: {exc}"
        ) from exc

    return destination
