#!/usr/bin/env python3

"""
Download and verify a package selected from the manifest.
"""

import hashlib
import os
import re
import urllib.request
from pathlib import Path


DOWNLOAD_CHUNK_SIZE = 1024 * 1024


class PackageDownloadError(RuntimeError):
    """Raised when a package cannot be safely downloaded."""


def validate_package_metadata(package):
    """Validate download-related fields from one manifest entry."""

    asset = str(package.get("asset") or "").strip()
    url = str(package.get("url") or "").strip()
    sha256 = str(package.get("sha256") or "").strip().lower()

    try:
        expected_size = int(package.get("size"))
    except (TypeError, ValueError) as exc:
        raise PackageDownloadError(
            "Package size is invalid."
        ) from exc

    if not asset or Path(asset).name != asset:
        raise PackageDownloadError(
            "Package asset name is invalid."
        )

    if not url.startswith(
        "https://github.com/f5vmr/svxlink/releases/"
    ):
        raise PackageDownloadError(
            "Package download URL is not trusted."
        )

    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise PackageDownloadError(
            "Package SHA-256 digest is invalid."
        )

    if expected_size < 1:
        raise PackageDownloadError(
            "Package size must be positive."
        )

    return {
        "asset": asset,
        "url": url,
        "sha256": sha256,
        "size": expected_size,
    }


def verify_file(path, expected_size, expected_sha256):
    """Verify the exact size and SHA-256 digest of a file."""

    package_path = Path(path)

    try:
        actual_size = package_path.stat().st_size
    except OSError as exc:
        raise PackageDownloadError(
            f"Cannot inspect downloaded package: {exc}"
        ) from exc

    if actual_size != expected_size:
        raise PackageDownloadError(
            "Downloaded package size does not match "
            f"the manifest: expected {expected_size}, "
            f"received {actual_size}."
        )

    digest = hashlib.sha256()

    try:
        with package_path.open("rb") as package_file:
            for chunk in iter(
                lambda: package_file.read(
                    DOWNLOAD_CHUNK_SIZE
                ),
                b"",
            ):
                digest.update(chunk)
    except OSError as exc:
        raise PackageDownloadError(
            f"Cannot read downloaded package: {exc}"
        ) from exc

    actual_sha256 = digest.hexdigest()

    if actual_sha256 != expected_sha256:
        raise PackageDownloadError(
            "Downloaded package SHA-256 digest "
            "does not match the manifest."
        )


def download_package(package, destination_directory):
    """Download, verify and atomically retain one package."""

    metadata = validate_package_metadata(package)
    destination = Path(destination_directory)
    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_path = destination / metadata["asset"]
    partial_path = destination / (
        metadata["asset"] + ".part"
    )

    try:
        partial_path.unlink(missing_ok=True)

        request = urllib.request.Request(
            metadata["url"],
            headers={
                "User-Agent": "SvxLink-Bootstrap/1.0",
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=60,
        ) as response:
            with partial_path.open("wb") as output:
                while True:
                    chunk = response.read(
                        DOWNLOAD_CHUNK_SIZE
                    )

                    if not chunk:
                        break

                    output.write(chunk)

        verify_file(
            partial_path,
            expected_size=metadata["size"],
            expected_sha256=metadata["sha256"],
        )

        os.replace(
            partial_path,
            final_path,
        )
    except PackageDownloadError:
        partial_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        partial_path.unlink(missing_ok=True)
        raise PackageDownloadError(
            f"Package download failed: {exc}"
        ) from exc

    return final_path
