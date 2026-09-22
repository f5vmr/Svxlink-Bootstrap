#!/usr/bin/env python3

"""
Detect the host and report or download its matching SvxLink package.
"""

import argparse
import sys
import tempfile

from pathlib import Path

from host_detection import (
    HostDetectionError,
    detect_host,
)

from package_download import (
    PackageDownloadError,
    download_package,
)

from package_selector import (
    PackageSelectionError,
    load_manifest,
    select_package,
)

from existing_installation import (
    detect_existing_installation,
    determine_installation_action,
)

from configuration_backup import (
    ConfigurationBackupError,
    backup_existing_configuration,
)

from dashboard_installation import (
    DashboardInstallationError,
    install_dashboard,
)

from package_installation import (
    PackageInstallationError,
    install_package,
)

from service_control import (
    ServiceControlError,
    stop_svxlink_service_if_active,
)

from raspberry_pi_preparation import (
    RaspberryPiPreparationError,
    prepare_raspberry_pi,
)

from system_access import (
    RootAccessRequiredError,
    require_root,
)

BASE_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = (
    BASE_DIR
    / "manifests"
    / "svxlink-packages.json"
)


def describe_host(host):
    """Return a concise printable host description."""

    details = [
        f"Platform:     {host['platform']}",
        f"Operating OS: {host['pretty_name']}",
        f"OS ID:        {host['os_id']}",
        f"Codename:     {host['codename']}",
        f"Architecture: {host['architecture']}",
    ]

    if host.get("device_model"):
        details.append(
            f"Device model: {host['device_model']}"
        )

    return "\n".join(details)


def describe_package(package):
    """Return the selected package details."""

    return "\n".join([
        f"Package ID:   {package['id']}",
        f"Release tag: {package['tag']}",
        f"Asset:       {package['asset']}",
        f"Size:        {package['size']} bytes",
        f"SHA-256:     {package['sha256']}",
        f"Download:    {package['url']}",
    ])


def resolve_host_package(
    manifest_path=MANIFEST_PATH,
):
    """Detect the host and select its exact package."""

    host = detect_host()
    manifest = load_manifest(manifest_path)

    package = select_package(
        manifest,
        platform=host["platform"],
        os_id=host["os_id"],
        codename=host["codename"],
        architecture=host["architecture"],
    )

    return host, package


def describe_existing_installation(installation):
    """Return a concise existing-installation report."""

    action = determine_installation_action(
        installation
    )

    if action == "install":
        return (
            "Existing SvxLink installation: not detected\n"
            "The selected package will be required."
        )

    details = [
        "Existing SvxLink installation: detected",
        (
            "Installation type: "
            f"{installation.get('installation_type', 'unknown')}"
        ),
    ]

    if installation["version"]:
        details.append(
            f"Reported version: {installation['version']}"
        )
    else:
        details.append("Reported version: unknown")

    if installation.get("version_source"):
        details.append(
            "Version source:   "
            f"{installation['version_source']}"
        )

    if installation["executable"]:
        details.append(
            f"Executable:       {installation['executable']}"
        )

    if installation["service_load_state"]:
        details.append(
            "Service:          "
            f"{installation['service_load_state']}"
            "/"
            f"{installation['service_active_state'] or 'unknown'}"
        )

    if installation["package_status"]:
        details.append(
            f"Debian package:   {installation['package_status']}"
        )
    else:
        details.append(
            "Debian package:   not detected"
        )

    if not installation.get("runtime_healthy", True):
        details.append("Runtime state:    unable to start")

        runtime_error = installation.get(
            "runtime_error",
            "",
        )

        if runtime_error:
            details.append(
                "Runtime error:    "
                f"{runtime_error.splitlines()[0]}"
            )

    if action == "retain":
        details.extend([
            "Compatibility:    supported SvxLink 26.05.1",
            (
                "The existing package-managed installation "
                "will be retained."
            ),
            (
                "Its configuration will be backed up before "
                "dashboard installation."
            ),
        ])

    elif action == "repair":
        details.extend([
            (
                "Compatibility:    repair required for "
                "faulty version string"
            ),
            (
                "The existing configuration will be backed up "
                "before package repair."
            ),
            (
                "The correct verified package will be forcibly "
                "reinstalled."
            ),
        ])

    elif action == "upgrade":
        details.extend([
            (
                "Compatibility:    upgrade available from "
                "SvxLink 26.05"
            ),
            (
                "The existing configuration will be backed up "
                "before package upgrade."
            ),
            (
                "The verified SvxLink 26.05.1 package will "
                "be installed."
            ),
        ])

    elif action == "convert":
        details.extend([
            "Compatibility:    compiler installation",
            (
                "The existing configuration will be backed "
                "up before package conversion."
            ),
            (
                "The verified SvxLink 26.05.1 package will "
                "replace the compiler-installed program."
            ),
        ])

    else:
        details.extend([
            "Compatibility:    unsupported or unknown",
            (
                "Automatic installation must stop for manual "
                "review."
            ),
        ])

    return "\n".join(details)


def report_installation_progress(
    progress,
    stage,
    status,
    message,
):
    """Send an installation progress event when requested."""

    if progress is not None:
        progress(
            stage,
            status,
            message,
        )


def perform_installation(
    host,
    package,
    installation,
    progress=None,
):
    """Install or convert SvxLink, then install the dashboard."""

    action = determine_installation_action(
        installation
    )

    if action == "block":
        print(
            "Automatic installation is blocked for this "
            "existing SvxLink installation.",
            file=sys.stderr,
        )
        return 4

    try:
        require_root()
    except RootAccessRequiredError as exc:
        print(str(exc), file=sys.stderr)
        return 5

    raspberry_pi_report = None

    if host.get("platform") == "raspberry_pi":
        print(
            "Preparing the Raspberry Pi operating-system "
            "baseline."
        )

        try:
            raspberry_pi_report = prepare_raspberry_pi()
        except RaspberryPiPreparationError as exc:
            report_installation_progress(
                progress,
                "service",
                "failed",
                str(exc),
            )
            print(
                f"Raspberry Pi preparation failed: {exc}",
                file=sys.stderr,
            )
            return 10

        changed = raspberry_pi_report.get(
            "changed",
            [],
        )

        if changed:
            print(
                "Raspberry Pi preparation completed: "
                + ", ".join(changed)
            )
        else:
            print(
                "The Raspberry Pi operating-system baseline "
                "is already configured."
            )

        if raspberry_pi_report.get(
            "reboot_required",
            False,
        ):
            print(
                "A reboot will be required after installation "
                "for the audio settings to take effect."
            )

        print()

    if action in {
        "retain",
        "convert",
        "repair",
        "upgrade",
    }:
        report_installation_progress(
            progress,
            "backup",
            "running",
            "Backing up the existing SvxLink configuration.",
        )
        print(
            "WARNING: An existing SvxLink installation "
            "was detected."
        )
        print(
            "Its configuration will be backed up before "
            "installation continues."
        )
        print()

        try:
            backup_path = backup_existing_configuration()
        except ConfigurationBackupError as exc:
            report_installation_progress(
                progress,
                "backup",
                "failed",
                str(exc),
            )
            print(
                f"Configuration backup failed: {exc}",
                file=sys.stderr,
            )
            return 6

        print("Existing SvxLink configuration backed up:")
        print(backup_path)
        print()
        report_installation_progress(
            progress,
            "backup",
            "completed",
            (
                "Existing configuration backed up to "
                f"{backup_path}."
            ),
        )
    else:
        report_installation_progress(
            progress,
            "backup",
            "skipped",
            "No existing configuration requires backup.",
        )
    if action in {
        "install",
        "convert",
        "repair",
        "upgrade",
    }:
        if action == "convert":
            print(
                "The compiler-installed SvxLink will be "
                "converted to the verified Debian package."
            )
            print()

        elif action == "repair":
            print(
                "Repairing a previous SvxLink 26.05.1 "
                "installation with a faulty version string."
            )
            print()

        elif action == "upgrade":
            print(
                "Upgrading the package-managed SvxLink "
                "installation to version 26.05.1."
            )
            print()

        try:
            with tempfile.TemporaryDirectory(
                prefix="svxlink-bootstrap-package-"
            ) as download_directory:
                report_installation_progress(
                    progress,
                    "download",
                    "running",
                    "Downloading and verifying the SvxLink package.",
                )
                package_path = download_package(
                    package,
                    download_directory,
                )
                report_installation_progress(
                    progress,
                    "download",
                    "completed",
                    (
                        "SvxLink package downloaded and "
                        "verified."
                    ),
                )
                print(package_path)
                print()

                if action in {
                    "convert",
                    "repair",
                    "upgrade",
                }:
                    report_installation_progress(
                        progress,
                        "service",
                        "running",
                        "Preparing the existing SvxLink service.",
                    )

                    service_stopped = (
                        stop_svxlink_service_if_active(
                            installation
                        )
                    )

                    if service_stopped:
                        print(
                            "The active SvxLink service "
                            "has been stopped."
                        )
                        print()
                        report_installation_progress(
                            progress,
                            "service",
                            "completed",
                            (
                                "The active SvxLink service "
                                "was stopped."
                            ),
                        )
                    else:
                        report_installation_progress(
                            progress,
                            "service",
                            "skipped",
                            (
                                "The SvxLink service was not "
                                "active."
                            ),
                        )
                else:
                    report_installation_progress(
                        progress,
                        "service",
                        "skipped",
                        (
                            "No compiler-installed SvxLink "
                            "service requires preparation."
                        ),
                    )

                report_installation_progress(
                    progress,
                    "package",
                    "running",
                    "Installing and verifying SvxLink 26.05.1.",
                )

                if action == "repair":
                    install_package(
                        package_path,
                        reinstall=True,
                    )
                else:
                    install_package(package_path)

                report_installation_progress(
                    progress,
                    "package",
                    "completed",
                    (
                        "SvxLink 26.05.1 was installed and "
                        "verified successfully."
                    ),
                )

        except PackageDownloadError as exc:
            report_installation_progress(
                progress,
                "download",
                "failed",
                str(exc),
            )
            print(
                f"Package download failed: {exc}",
                file=sys.stderr,
            )
            return 3

        except ServiceControlError as exc:
            report_installation_progress(
                progress,
                "service",
                "failed",
                str(exc),
            )
            print(
                f"Service control failed: {exc}",
                file=sys.stderr,
            )
            return 9

        except PackageInstallationError as exc:
            report_installation_progress(
                progress,
                "package",
                "failed",
                str(exc),
            )
            print(
                f"Package installation failed: {exc}",
                file=sys.stderr,
            )
            return 7

        print("SvxLink 26.05.1 installed successfully.")
        print()

    else:
        report_installation_progress(
            progress,
            "download",
            "skipped",
            (
                "The installed SvxLink package is already "
                "current."
            ),
        )
        report_installation_progress(
            progress,
            "service",
            "skipped",
            (
                "The retained SvxLink service requires no "
                "package-conversion preparation."
            ),
        )
        report_installation_progress(
            progress,
            "package",
            "skipped",
            (
                "The verified package-managed SvxLink "
                "installation will be retained."
            ),
        )
        print(
            "The package-managed SvxLink 26.05.1 "
            "installation will be retained."
        )
        print()

    report_installation_progress(
        progress,
        "dashboard",
        "running",
        "Installing SvxLink-Dash V4.0.",
    )

    try:
        dashboard_path = install_dashboard()
    except DashboardInstallationError as exc:
        report_installation_progress(
            progress,
            "dashboard",
            "failed",
            str(exc),
        )
        print(
            f"Dashboard installation failed: {exc}",
            file=sys.stderr,
        )
        return 8

    report_installation_progress(
        progress,
        "dashboard",
        "completed",
        "SvxLink-Dash V4.0 was installed successfully.",
    )

    print("SvxLink-Dash V4.0 installed successfully:")
    print(dashboard_path)
    return 0


def main(download_directory=None, install=False):
    """Detect the host and optionally download its package."""

    print("SvxLink Bootstrap — compatibility check")
    print()

    try:
        host, package = resolve_host_package()
    except HostDetectionError as exc:
        print(
            f"Host detection failed: {exc}",
            file=sys.stderr,
        )
        return 1
    except PackageSelectionError as exc:
        print(
            f"Unsupported system: {exc}",
            file=sys.stderr,
        )
        return 2

    print(describe_host(host))
    print()
    print("Compatible SvxLink package found:")
    print(describe_package(package))
    print()

    installation = detect_existing_installation()

    action = determine_installation_action(
        installation
    )

    print(describe_existing_installation(installation))
    print()

    if action == "block":
        print(
            "Automatic processing stopped because the "
            "existing SvxLink installation is not eligible "
            "for retention, repair, package upgrade, or "
            "package conversion.",
            file=sys.stderr,
        )
        return 4

    if install:
        return perform_installation(
            host,
            package,
            installation,
        )

    if download_directory is None:
        print(
            "No files were downloaded and no system "
            "changes were made."
        )
        return 0

    if action == "retain":
        print(
            "Package-managed SvxLink 26.05.1 is already "
            "installed. The package download was skipped."
        )
        print(
            "No system configuration was changed."
        )
        return 0

    try:
        package_path = download_package(
            package,
            download_directory,
        )
    except PackageDownloadError as exc:
        print(
            f"Package download failed: {exc}",
            file=sys.stderr,
        )
        return 3

    print("Package downloaded and verified:")
    print(package_path)
    print()
    print(
        "The package has not been installed and no "
        "system configuration was changed."
    )

    return 0


def parse_arguments():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Detect a supported host and select its "
            "SvxLink package."
        )
    )
    operation = parser.add_mutually_exclusive_group()

    operation.add_argument(
        "--download",
        metavar="DIRECTORY",
        help=(
            "Download and verify the selected package "
            "in DIRECTORY without installing it."
        ),
    )

    operation.add_argument(
        "--install",
        action="store_true",
        help=(
            "Install SvxLink when required, back up any "
            "existing supported configuration, and install "
            "SvxLink-Dash V4.0."
        ),
    )

    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()

    raise SystemExit(
        main(
            download_directory=arguments.download,
            install=arguments.install,
        )
    )
