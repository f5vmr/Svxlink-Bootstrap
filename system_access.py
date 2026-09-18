#!/usr/bin/env python3

"""
Check whether privileged bootstrap operations may proceed.
"""

import os


class RootAccessRequiredError(PermissionError):
    """Raised when a privileged operation is attempted as non-root."""


def running_as_root():
    """Return True when the current effective user is root."""

    return os.geteuid() == 0


def require_root():
    """Reject a system-changing operation unless running as root."""

    if not running_as_root():
        raise RootAccessRequiredError(
            "Installation requires root privileges. "
            "Run the bootstrap with sudo."
        )
