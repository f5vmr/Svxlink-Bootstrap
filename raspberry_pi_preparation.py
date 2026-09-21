#!/usr/bin/env python3

"""
Prepare Raspberry Pi OS for the standard SvxLink installation.
"""

import os
import pwd
import re
import shutil
import subprocess
import tempfile

from pathlib import Path

from system_access import require_root


BOOT_CONFIG_PATH = Path(
    "/boot/firmware/config.txt"
)

BLACKLIST_PATH = Path(
    "/etc/modprobe.d/raspberry-blacklist.conf"
)

USB_AUDIO_PATH = Path(
    "/etc/modprobe.d/asound.conf"
)

HIDRAW_RULE_PATH = Path(
    "/etc/udev/rules.d/90-svxlink-cmedia-hidraw.rules"
)

SUDOERS_PATH = Path(
    "/etc/sudoers.d/010_pi-nopasswd"
)

BOOT_AUDIO_SETTING = "dtparam=audio=off"

BLACKLIST_SETTING = "blacklist snd_bcm2835"

USB_AUDIO_SETTING = (
    "options snd_usb_audio index=0,1"
)

HIDRAW_RULE = (
    'SUBSYSTEM=="hidraw", '
    'ATTRS{idVendor}=="0d8c", '
    'GROUP="plugdev", MODE="0660"'
)

PI_SUDOERS_SETTING = (
    "pi ALL=(ALL) NOPASSWD: ALL"
)


class RaspberryPiPreparationError(RuntimeError):
    """Raised when Raspberry Pi preparation cannot be completed."""


def replace_managed_line(
    content,
    pattern,
    replacement,
):
    """
    Replace matching active lines with one canonical setting.

    Comments and unrelated settings are preserved. Duplicate active
    settings are reduced to one line.
    """

    expression = re.compile(pattern)
    lines = content.splitlines()
    result = []
    replaced = False

    for line in lines:
        if expression.match(line):
            if not replaced:
                result.append(replacement)
                replaced = True
            continue

        result.append(line)

    if not replaced:
        if result and result[-1] != "":
            result.append("")

        result.append(replacement)

    return "\n".join(result) + "\n"


def disable_vc4_hdmi_audio(content):
    """
    Add noaudio to active VC4 KMS overlay declarations.

    Existing overlay parameters are preserved. Commented lines and
    unrelated overlays remain unchanged.
    """

    expression = re.compile(
        r"^("
        r"\s*dtoverlay\s*=\s*"
        r"vc4-kms-v3d"
        r"(?:-[A-Za-z0-9_-]+)?"
        r")"
        r"([^#]*)"
        r"(#.*)?$"
    )

    result = []

    for line in content.splitlines():
        match = expression.match(line)

        if not match:
            result.append(line)
            continue

        declaration = match.group(1)
        parameter_text = match.group(2) or ""
        comment = match.group(3) or ""

        parameters = [
            parameter.strip().lower()
            for parameter in parameter_text.split(",")
            if parameter.strip()
        ]

        if "noaudio" in parameters:
            result.append(line)
            continue

        updated_line = (
            declaration
            + parameter_text.rstrip()
            + ",noaudio"
        )

        if comment:
            updated_line += " " + comment

        result.append(updated_line)

    return "\n".join(result) + "\n"


def write_if_changed(
    path,
    content,
    mode=None,
):
    """Write content only when the destination differs."""

    path = Path(path)

    try:
        existing = (
            path.read_text(encoding="utf-8")
            if path.exists()
            else None
        )

        if existing == content:
            if mode is not None:
                os.chmod(path, mode)
            return False

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            content,
            encoding="utf-8",
        )

        if mode is not None:
            os.chmod(path, mode)

    except OSError as exc:
        raise RaspberryPiPreparationError(
            f"Could not write {path}: {exc}"
        ) from exc

    return True


def configure_boot_audio(path=BOOT_CONFIG_PATH):
    """Disable Raspberry Pi onboard and HDMI audio."""

    path = Path(path)

    try:
        content = path.read_text(
            encoding="utf-8",
        )
    except OSError as exc:
        raise RaspberryPiPreparationError(
            f"Could not read Raspberry Pi boot configuration "
            f"{path}: {exc}"
        ) from exc

    updated = replace_managed_line(
        content,
        r"^\s*dtparam\s*=\s*audio\s*=",
        BOOT_AUDIO_SETTING,
    )

    updated = disable_vc4_hdmi_audio(
        updated
    )

    return write_if_changed(
        path,
        updated,
    )


def configure_module_blacklist(
    path=BLACKLIST_PATH,
):
    """Blacklist the Raspberry Pi onboard audio module."""

    path = Path(path)

    try:
        content = (
            path.read_text(encoding="utf-8")
            if path.exists()
            else ""
        )
    except OSError as exc:
        raise RaspberryPiPreparationError(
            f"Could not read {path}: {exc}"
        ) from exc

    updated = replace_managed_line(
        content,
        r"^\s*blacklist\s+snd_bcm2835(?:\s|$)",
        BLACKLIST_SETTING,
    )

    return write_if_changed(
        path,
        updated,
    )


def configure_usb_audio(
    path=USB_AUDIO_PATH,
):
    """Reserve ALSA indices zero and one for USB audio."""

    path = Path(path)

    try:
        content = (
            path.read_text(encoding="utf-8")
            if path.exists()
            else ""
        )
    except OSError as exc:
        raise RaspberryPiPreparationError(
            f"Could not read {path}: {exc}"
        ) from exc

    updated = replace_managed_line(
        content,
        r"^\s*options\s+snd_usb_audio(?:\s|$)",
        USB_AUDIO_SETTING,
    )

    return write_if_changed(
        path,
        updated,
    )


def configure_hidraw_rule(
    path=HIDRAW_RULE_PATH,
):
    """Grant plugdev access to C-Media HIDRAW interfaces."""

    return write_if_changed(
        path,
        HIDRAW_RULE + "\n",
    )


def validate_pi_user():
    """Require the standard Raspberry Pi installation user."""

    try:
        pwd.getpwnam("pi")
    except KeyError as exc:
        raise RaspberryPiPreparationError(
            "The standard Raspberry Pi user 'pi' does not "
            "exist. Write the SD card with Raspberry Pi "
            "Imager and create the user as 'pi'."
        ) from exc


def configure_pi_sudoers(
    path=SUDOERS_PATH,
):
    """Install and validate the passwordless sudo rule for pi."""

    validate_pi_user()

    path = Path(path)
    content = PI_SUDOERS_SETTING + "\n"

    try:
        if path.exists():
            existing = path.read_text(
                encoding="utf-8",
            )

            if existing == content:
                os.chmod(path, 0o440)
                return False

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError as exc:
        raise RaspberryPiPreparationError(
            f"Could not inspect {path}: {exc}"
        ) from exc

    visudo = shutil.which("visudo")

    if not visudo:
        raise RaspberryPiPreparationError(
            "visudo was not found; the pi sudo rule "
            "cannot be validated safely."
        )

    temporary_path = None

    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".010_pi-nopasswd.",
            dir=str(path.parent),
            text=True,
        )
        temporary_path = Path(temporary_name)

        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(content)

        os.chmod(temporary_path, 0o440)

        result = subprocess.run(
            [
                visudo,
                "-cf",
                str(temporary_path),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            message = (
                result.stderr.strip()
                or result.stdout.strip()
                or "unknown validation error"
            )
            raise RaspberryPiPreparationError(
                f"The pi sudo rule failed validation: {message}"
            )

        os.replace(
            temporary_path,
            path,
        )
        temporary_path = None

    except RaspberryPiPreparationError:
        raise
    except OSError as exc:
        raise RaspberryPiPreparationError(
            f"Could not install {path}: {exc}"
        ) from exc
    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            try:
                temporary_path.unlink()
            except OSError:
                pass

    return True


def run_udevadm(arguments):
    """Run one udevadm operation."""

    udevadm = shutil.which("udevadm")

    if not udevadm:
        raise RaspberryPiPreparationError(
            "udevadm was not found."
        )

    try:
        result = subprocess.run(
            [
                udevadm,
                *arguments,
            ],
            check=False,
        )
    except OSError as exc:
        raise RaspberryPiPreparationError(
            f"Could not start udevadm: {exc}"
        ) from exc

    if result.returncode != 0:
        raise RaspberryPiPreparationError(
            "udevadm "
            f"{' '.join(arguments)} failed "
            f"(exit status {result.returncode})."
        )


def reload_udev_rules():
    """Reload udev rules and apply them to existing devices."""

    run_udevadm([
        "control",
        "--reload-rules",
    ])
    run_udevadm([
        "trigger",
    ])


def prepare_raspberry_pi(
    boot_config_path=BOOT_CONFIG_PATH,
    blacklist_path=BLACKLIST_PATH,
    usb_audio_path=USB_AUDIO_PATH,
    hidraw_rule_path=HIDRAW_RULE_PATH,
    sudoers_path=SUDOERS_PATH,
):
    """
    Apply the standard Raspberry Pi SvxLink baseline.

    Returns a report containing the changed settings and whether a
    reboot is required for boot and module settings to take effect.
    """

    require_root()

    changed = []

    if configure_pi_sudoers(sudoers_path):
        changed.append("pi_sudoers")

    if configure_boot_audio(boot_config_path):
        changed.append("boot_audio")

    if configure_module_blacklist(blacklist_path):
        changed.append("module_blacklist")

    if configure_usb_audio(usb_audio_path):
        changed.append("usb_audio")

    hidraw_changed = configure_hidraw_rule(
        hidraw_rule_path
    )

    if hidraw_changed:
        changed.append("hidraw_rule")

    reload_udev_rules()

    reboot_required = any(
        item in changed
        for item in (
            "boot_audio",
            "module_blacklist",
            "usb_audio",
        )
    )

    return {
        "changed": changed,
        "reboot_required": reboot_required,
    }
