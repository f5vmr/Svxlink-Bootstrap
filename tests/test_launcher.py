#!/usr/bin/env python3

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = REPOSITORY_ROOT / "launch-bootstrap.sh"


class LauncherTests(unittest.TestCase):

    def run_launcher_with_release(
        self,
        os_id,
        codename,
        pretty_name,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            fake_binary_directory = temporary_path / "bin"
            fake_binary_directory.mkdir()

            fake_id = fake_binary_directory / "id"
            fake_id.write_text(
                "#!/bin/sh\n"
                "if [ \"${1:-}\" = '-u' ]; then\n"
                "    echo 0\n"
                "    exit 0\n"
                "fi\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake_id.chmod(0o755)

            apt_marker = temporary_path / "apt-was-called"
            fake_apt_get = fake_binary_directory / "apt-get"
            fake_apt_get.write_text(
                "#!/bin/sh\n"
                "printf 'called\\n' > \"${TEST_APT_MARKER}\"\n"
                "exit 99\n",
                encoding="utf-8",
            )
            fake_apt_get.chmod(0o755)

            os_release = temporary_path / "os-release"
            os_release.write_text(
                "ID=\"{}\"\n"
                "VERSION_CODENAME=\"{}\"\n"
                "PRETTY_NAME=\"{}\"\n".format(
                    os_id,
                    codename,
                    pretty_name,
                ),
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["PATH"] = (
                str(fake_binary_directory)
                + os.pathsep
                + environment.get("PATH", "")
            )
            environment[
                "SVXLINK_BOOTSTRAP_OS_RELEASE_FILE"
            ] = str(os_release)
            environment["TEST_APT_MARKER"] = str(apt_marker)

            result = subprocess.run(
                ["/bin/sh", str(LAUNCHER)],
                cwd=str(REPOSITORY_ROOT),
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            return result, apt_marker.exists()

    def test_bullseye_is_rejected_before_apt(self):
        result, apt_was_called = self.run_launcher_with_release(
            "debian",
            "bullseye",
            "Debian GNU/Linux 11 (bullseye)",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "Unsupported operating-system release",
            result.stderr,
        )
        self.assertIn("bullseye", result.stderr)
        self.assertIn("Bookworm or Trixie", result.stderr)
        self.assertFalse(apt_was_called)

    def test_buster_is_rejected_before_apt(self):
        result, apt_was_called = self.run_launcher_with_release(
            "raspbian",
            "buster",
            "Raspbian GNU/Linux 10 (buster)",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "Unsupported operating-system release",
            result.stderr,
        )
        self.assertIn("buster", result.stderr)
        self.assertFalse(apt_was_called)

    def test_unsupported_operating_system_is_rejected_before_apt(self):
        result, apt_was_called = self.run_launcher_with_release(
            "ubuntu",
            "noble",
            "Ubuntu 24.04 LTS",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "Unsupported operating system",
            result.stderr,
        )
        self.assertIn("Ubuntu 24.04 LTS", result.stderr)
        self.assertFalse(apt_was_called)

    def test_launcher_has_valid_shell_syntax(self):
        result = subprocess.run(
            ["/bin/sh", "-n", str(LAUNCHER)],
            cwd=str(REPOSITORY_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
