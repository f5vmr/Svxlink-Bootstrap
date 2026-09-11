#!/usr/bin/env python3

import hashlib
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from package_download import (
    PackageDownloadError,
    download_package,
    validate_package_metadata,
)


class PackageDownloadTests(unittest.TestCase):

    def make_package(self, payload):
        return {
            "id": "test_package",
            "asset": "svxlink_test_amd64.deb",
            "url": (
                "https://github.com/f5vmr/svxlink/"
                "releases/download/test/"
                "svxlink_test_amd64.deb"
            ),
            "size": len(payload),
            "sha256": hashlib.sha256(
                payload
            ).hexdigest(),
        }

    @patch("package_download.urllib.request.urlopen")
    def test_valid_download_is_retained(
        self,
        urlopen_mock,
    ):
        payload = b"verified package contents"
        package = self.make_package(payload)
        urlopen_mock.return_value = BytesIO(payload)

        with tempfile.TemporaryDirectory() as directory:
            result = download_package(
                package,
                directory,
            )

            self.assertEqual(
                result,
                (
                    Path(directory)
                    / "svxlink_test_amd64.deb"
                ),
            )
            self.assertEqual(
                result.read_bytes(),
                payload,
            )
            self.assertFalse(
                (
                    Path(directory)
                    / "svxlink_test_amd64.deb.part"
                ).exists()
            )

        urlopen_mock.assert_called_once()

    @patch("package_download.urllib.request.urlopen")
    def test_wrong_digest_is_rejected_and_removed(
        self,
        urlopen_mock,
    ):
        payload = b"incorrect package contents"
        package = self.make_package(payload)
        package["sha256"] = "0" * 64
        urlopen_mock.return_value = BytesIO(payload)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(
                PackageDownloadError
            ):
                download_package(
                    package,
                    directory,
                )

            self.assertFalse(
                (
                    Path(directory)
                    / package["asset"]
                ).exists()
            )
            self.assertFalse(
                (
                    Path(directory)
                    / f"{package['asset']}.part"
                ).exists()
            )

    @patch("package_download.urllib.request.urlopen")
    def test_wrong_size_is_rejected_and_removed(
        self,
        urlopen_mock,
    ):
        payload = b"package"
        package = self.make_package(payload)
        package["size"] += 1
        urlopen_mock.return_value = BytesIO(payload)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(
                PackageDownloadError
            ):
                download_package(
                    package,
                    directory,
                )

            self.assertFalse(
                (
                    Path(directory)
                    / package["asset"]
                ).exists()
            )

    def test_untrusted_url_is_rejected(self):
        package = self.make_package(b"package")
        package["url"] = (
            "https://example.invalid/package.deb"
        )

        with self.assertRaises(
            PackageDownloadError
        ):
            validate_package_metadata(package)

    def test_asset_path_is_rejected(self):
        package = self.make_package(b"package")
        package["asset"] = "../package.deb"

        with self.assertRaises(
            PackageDownloadError
        ):
            validate_package_metadata(package)

    def test_invalid_digest_is_rejected(self):
        package = self.make_package(b"package")
        package["sha256"] = "not-a-digest"

        with self.assertRaises(
            PackageDownloadError
        ):
            validate_package_metadata(package)


if __name__ == "__main__":
    unittest.main()
    