#!/usr/bin/env python3
"""
Control the SvxLink systemd service during package conversion.
"""
import shutil
import subprocess


class ServiceControlError(RuntimeError):
    """Raised when the SvxLink service cannot be controlled."""


def stop_svxlink_service_if_active(installation):
    """Stop an active SvxLink service and report whether it was stopped."""

    if installation.get("service_active_state") != "active":
        return False

    systemctl = shutil.which("systemctl")

    if not systemctl:
        raise ServiceControlError(
            "systemctl was not found while stopping SvxLink."
        )

    try:
        result = subprocess.run(
            [
                systemctl,
                "stop",
                "svxlink.service",
            ],
            check=False,
        )
    except OSError as exc:
        raise ServiceControlError(
            f"Could not start systemctl: {exc}"
        ) from exc

    if result.returncode != 0:
        raise ServiceControlError(
            "Could not stop svxlink.service "
            f"(exit status {result.returncode})."
        )

    return True
