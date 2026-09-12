#!/usr/bin/env python3
"""
Temporary web manager for SvxLink Bootstrap.
"""
import secrets

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
)

from bootstrap import resolve_host_package
from existing_installation import (
    detect_existing_installation,
    determine_installation_action,
)
from web_installation import (
    InstallationAlreadyStartedError,
    InstallationState,
    start_installation_job,
)


def token_matches(candidate, expected):
    """Compare a supplied access token safely."""

    if not candidate or not expected:
        return False

    return secrets.compare_digest(
        str(candidate),
        str(expected),
    )


def create_app(
    access_token=None,
    confirmation_token=None,
    installation_state=None,
    dashboard_url=None,
):
    """Create the temporary Bootstrap web application."""

    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    app.config.update({
        "BOOTSTRAP_ACCESS_TOKEN": (
            access_token or secrets.token_urlsafe(32)
        ),
        "BOOTSTRAP_CONFIRMATION_TOKEN": (
            confirmation_token or secrets.token_urlsafe(32)
        ),
        "BOOTSTRAP_DASHBOARD_URL": (
            dashboard_url
            or (
                "http:"
                "//127.0.0.1:5000/start"
            )
        ),
    })
    if installation_state is None:
        installation_state = InstallationState()

    app.extensions[
        "bootstrap_installation_state"
    ] = installation_state

    def require_access_token():
        supplied_token = request.args.get("token", "")

        if not token_matches(
            supplied_token,
            app.config["BOOTSTRAP_ACCESS_TOKEN"],
        ):
            abort(403)

    @app.get("/")
    def inspection():
        require_access_token()

        host, package = resolve_host_package()
        installation = detect_existing_installation()
        action = determine_installation_action(
            installation
        )

        return render_template(
            "bootstrap.html",
            host=host,
            package=package,
            installation=installation,
            action=action,
            access_token=(
                app.config["BOOTSTRAP_ACCESS_TOKEN"]
            ),
            confirmation_token=(
                app.config[
                    "BOOTSTRAP_CONFIRMATION_TOKEN"
                ]
            ),
        )

    @app.get("/status")
    def installation_status():
        require_access_token()

        state = app.extensions[
            "bootstrap_installation_state"
        ]

        return jsonify(state.snapshot())

    @app.post("/install")
    def start_installation():
        require_access_token()

        supplied_confirmation = request.form.get(
            "confirmation_token",
            "",
        )

        if not token_matches(
            supplied_confirmation,
            app.config[
                "BOOTSTRAP_CONFIRMATION_TOKEN"
            ],
        ):
            abort(403)

        _, package = resolve_host_package()
        installation = detect_existing_installation()
        action = determine_installation_action(
            installation
        )

        if action == "block":
            return (
                jsonify({
                    "status": "blocked",
                    "message": (
                        "The existing SvxLink installation "
                        "requires manual review."
                    ),
                }),
                409,
            )

        state = app.extensions[
            "bootstrap_installation_state"
        ]

        try:
            start_installation_job(
                state,
                package,
                installation,
                app.config["BOOTSTRAP_DASHBOARD_URL"],
            )
        except InstallationAlreadyStartedError as exc:
            return (
                jsonify({
                    "status": "conflict",
                    "message": str(exc),
                }),
                409,
            )

        return jsonify(state.snapshot()), 202

    return app
