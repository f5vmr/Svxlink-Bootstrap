#!/usr/bin/env python3

"""
Select one SvxLink package from the bootstrap package manifest.
"""

import json
from pathlib import Path


class PackageSelectionError(RuntimeError):
    """Base error for package-manifest selection selection."""


class NoMatchingPackageError(PackageSelectionError):
    """Raised when the manifest has no exact compatible package."""


class AmbiguousPackageError(PackageSelectionError):
    """Raised when more than one package matches the host."""


def normalise(value):
    """Return a stripped, lowercase comparison value."""

    return str(value or "").strip().lower()


def load_manifest(path):
    """Load and minimally validate a package manifest."""

    manifest_path = Path(path)

    with manifest_path.open(
        "r",
        encoding="utf-8",
    ) as manifest_file:
        manifest = json.load(manifest_file)

    if manifest.get("schema_version") != 1:
        raise PackageSelectionError(
            "Unsupported package manifest schema."
        )

    packages = manifest.get("packages")

    if not isinstance(packages, list):
        raise PackageSelectionError(
            "Package manifest does not contain a package list."
        )

    return manifest


def package_matches(
    package,
    platform,
    os_id,
    codename,
    architecture,
):
    """Return True only when every compatibility field matches."""

    supported_os_ids = {
        normalise(value)
        for value in package.get("os_ids", [])
    }

    return (
        normalise(package.get("platform"))
        == normalise(platform)
        and normalise(os_id) in supported_os_ids
        and normalise(package.get("codename"))
        == normalise(codename)
        and normalise(package.get("architecture"))
        == normalise(architecture)
    )


def select_package(
    manifest,
    platform,
    os_id,
    codename,
    architecture,
):
    """Return the one exact package matching the supplied host."""

    matches = [
        package
        for package in manifest["packages"]
        if package_matches(
            package,
            platform=platform,
            os_id=os_id,
            codename=codename,
            architecture=architecture,
        )
    ]

    host_description = (
        f"platform={platform}, "
        f"os={os_id}, "
        f"codename={codename}, "
        f"architecture={architecture}"
    )

    if not matches:
        raise NoMatchingPackageError(
            "No supported SvxLink package matches "
            + host_description
        )

    if len(matches) > 1:
        matching_ids = ", ".join(
            package.get("id", "<unnamed>")
            for package in matches
        )
        raise AmbiguousPackageError(
            "Multiple SvxLink packages match "
            + host_description
            + f": {matching_ids}"
        )

    return matches[0]