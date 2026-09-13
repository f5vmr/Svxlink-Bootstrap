#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path

from package_selector import (
    AmbiguousPackageError,
    NoMatchingPackageError,
    PackageSelectionError,
    load_manifest,
    select_package,
)


MANIFEST_PATH = Path(
    "manifests/svxlink-packages.json"
)


class PackageSelectorTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.manifest = load_manifest(MANIFEST_PATH)

    def test_all_supported_hosts_select_expected_package(self):
        cases = [
            (
                "raspberry_pi",
                "debian",
                "bookworm",
                "arm64",
                "raspberry_pi_bookworm_arm64",
            ),
            (
                "raspberry_pi",
                "debian",
                "trixie",
                "arm64",
                "raspberry_pi_trixie_arm64",
            ),
            (
                "raspberry_pi",
                "raspbian",
                "bookworm",
                "armhf",
                "raspberry_pi_bookworm_armhf",
            ),
            (
                "nanopi_neo",
                "debian",
                "trixie",
                "armhf",
                "nanopi_neo_trixie_armhf",
            ),
            (
                "debian",
                "debian",
                "bookworm",
                "amd64",
                "debian_bookworm_amd64",
            ),
            (
                "debian",
                "debian",
                "trixie",
                "amd64",
                "debian_trixie_amd64",
            ),
            (
                "debian",
                "debian",
                "bookworm",
                "i386",
                "debian_bookworm_i386",
            ),
        ]

        for (
            platform,
            os_id,
            codename,
            architecture,
            expected_id,
        ) in cases:
            with self.subTest(expected_id=expected_id):
                package = select_package(
                    self.manifest,
                    platform,
                    os_id,
                    codename,
                    architecture,
                )
                self.assertEqual(
                    package["id"],
                    expected_id,
                )

    def test_unsupported_hosts_are_rejected(self):
        cases = [
            (
                "debian",
                "ubuntu",
                "jammy",
                "amd64",
            ),
            (
                "debian",
                "debian",
                "trixie",
                "i386",
            ),
            (
                "debian",
                "debian",
                "bookworm",
                "arm64",
            ),
            (
                "raspberry_pi",
                "debian",
                "trixie",
                "armhf",
            ),
        ]

        for host in cases:
            with self.subTest(host=host):
                with self.assertRaises(
                    NoMatchingPackageError
                ):
                    select_package(
                        self.manifest,
                        *host,
                    )

    def test_matching_is_case_insensitive(self):
        package = select_package(
            self.manifest,
            "RASPBERRY_PI",
            "DEBIAN",
            "TRIXIE",
            "ARM64",
        )

        self.assertEqual(
            package["id"],
            "raspberry_pi_trixie_arm64",
        )

    def test_ambiguous_matches_are_rejected(self):
        package = dict(
            self.manifest["packages"][0]
        )
        duplicate = dict(package)
        duplicate["id"] = "duplicate_package"

        manifest = {
            "schema_version": 1,
            "packages": [
                package,
                duplicate,
            ],
        }

        with self.assertRaises(
            AmbiguousPackageError
        ):
            select_package(
                manifest,
                "raspberry_pi",
                "debian",
                "bookworm",
                "arm64",
            )

    def test_invalid_schema_is_rejected(self):
        manifest = {
            "schema_version": 2,
            "packages": [],
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            with self.assertRaises(
                PackageSelectionError
            ):
                load_manifest(path)

    def test_missing_package_list_is_rejected(self):
        manifest = {
            "schema_version": 1,
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            with self.assertRaises(
                PackageSelectionError
            ):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
