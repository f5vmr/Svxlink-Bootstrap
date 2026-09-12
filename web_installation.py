#!/usr/bin/env python3
"""
Thread-safe progress state for the Bootstrap web manager.
"""
import copy
import threading


INSTALLATION_STAGES = (
    "backup",
    "download",
    "service",
    "package",
    "dashboard",
    "handover",
)

VALID_STAGE_STATES = {
    "pending",
    "running",
    "completed",
    "skipped",
    "failed",
}


class InstallationStateError(RuntimeError):
    """Raised when an invalid progress transition is requested."""


class InstallationAlreadyStartedError(
    InstallationStateError
):
    """Raised when a second installation start is requested."""


class InstallationState:
    """Store a single installation job and its progress."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sequence = 0
        self._started = False
        self._status = "idle"
        self._current_stage = ""
        self._message = ""
        self._redirect_url = ""
        self._stages = {
            stage: "pending"
            for stage in INSTALLATION_STAGES
        }
        self._events = []
        self._log = []

    def _record_event(
        self,
        stage,
        status,
        message,
    ):
        self._sequence += 1
        self._events.append({
            "sequence": self._sequence,
            "stage": stage,
            "status": status,
            "message": message,
        })

    def start(self):
        """Mark the one permitted installation job as started."""

        with self._lock:
            if self._started:
                raise InstallationAlreadyStartedError(
                    "The installation has already been started."
                )

            self._started = True
            self._status = "running"
            self._message = "Installation started."
            self._record_event(
                "",
                "running",
                self._message,
            )

    def update_stage(
        self,
        stage,
        status,
        message="",
    ):
        """Update one named installation stage."""

        if stage not in INSTALLATION_STAGES:
            raise InstallationStateError(
                f"Unknown installation stage: {stage}"
            )

        if status not in VALID_STAGE_STATES:
            raise InstallationStateError(
                f"Unknown stage status: {status}"
            )

        with self._lock:
            if not self._started:
                raise InstallationStateError(
                    "The installation has not been started."
                )

            if self._status in {"completed", "failed"}:
                raise InstallationStateError(
                    "The installation has already finished."
                )

            self._stages[stage] = status

            if status == "running":
                self._current_stage = stage

            if message:
                self._message = message
                self._log.append(message)

            self._record_event(
                stage,
                status,
                message,
            )

    def complete(self, redirect_url):
        """Mark installation complete and record its handover URL."""

        with self._lock:
            if not self._started:
                raise InstallationStateError(
                    "The installation has not been started."
                )

            if self._status == "failed":
                raise InstallationStateError(
                    "A failed installation cannot be completed."
                )

            self._stages["handover"] = "completed"
            self._status = "completed"
            self._current_stage = ""
            self._message = "Installation completed successfully."
            self._redirect_url = str(redirect_url)
            self._record_event(
                "handover",
                "completed",
                self._message,
            )

    def fail(self, stage, message):
        """Mark an installation stage and the job as failed."""

        if stage not in INSTALLATION_STAGES:
            raise InstallationStateError(
                f"Unknown installation stage: {stage}"
            )

        with self._lock:
            if not self._started:
                raise InstallationStateError(
                    "The installation has not been started."
                )

            self._stages[stage] = "failed"
            self._status = "failed"
            self._current_stage = stage
            self._message = str(message)
            self._log.append(str(message))
            self._record_event(
                stage,
                "failed",
                str(message),
            )

    def append_log(self, message):
        """Append a line of installation detail."""

        with self._lock:
            self._log.append(str(message))

    def snapshot(self):
        """Return an independent serialisable state snapshot."""

        with self._lock:
            return copy.deepcopy({
                "sequence": self._sequence,
                "started": self._started,
                "status": self._status,
                "current_stage": self._current_stage,
                "message": self._message,
                "redirect_url": self._redirect_url,
                "stages": self._stages,
                "events": self._events,
                "log": self._log,
            })
