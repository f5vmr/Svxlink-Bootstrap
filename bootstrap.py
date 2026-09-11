#!/usr/bin/env python3

"""
Detect the host and report or download its matching SvxLink package.
"""

import argparse
import sys
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


def main(download_directory=None):
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

    if download_directory is None:
        print(
            "No files were downloaded and no system "
            "changes were made."
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
    parser.add_argument(
        "--download",
        metavar="DIRECTORY",
        help=(
            "Download and verify the selected package "
            "in DIRECTORY without installing it."
        ),
    )

    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()

    raise SystemExit(
        main(
            download_directory=arguments.download,
        )
    )
