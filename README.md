# SvxLink-Bootstrap

SvxLink-Bootstrap provides a safe, guided route from a supported Debian, Raspberry Pi OS or Armbian installation to a complete SvxLink 26.05.1 and SvxLink-Dash V4.0 system.

It detects the operating system, release, Debian architecture and hardware platform, selects one exact compatible SvxLink Debian package from a controlled manifest, verifies the downloaded package and installs SvxLink-Dash V4.0.

The normal installation is performed through a temporary, token-protected web manager. After installation succeeds, the browser is handed directly to the permanent SvxLink-Dash V4.0 configuration workflow.

## Project relationship

SvxLink 26.05.1 is created and maintained by Tobias Blömberg, SM0SVX.

SvxLink-Bootstrap and SvxLink-Dash V4.0 are developed and maintained by Chris Jackson, G4NAB, to provide a guided installation, configuration and operational environment around the standard SvxLink software.

For authoritative SvxLink configuration and operating information, refer only to:

* [Official SvxLink repository](https://github.com/sm0svx/svxlink)
* [Official SvxLink wiki](https://github.com/sm0svx/svxlink/wiki)

## Supported systems

Package selection requires an exact match for:

* Hardware platform.
* Operating-system identity.
* Release codename.
* Debian package architecture.

The current manifest contains seven supported package targets:

| Platform     | Operating system          | Release  | Architecture |
| ------------ | ------------------------- | -------- | ------------ |
| Raspberry Pi | Raspberry Pi OS           | Bookworm | arm64        |
| Raspberry Pi | Raspberry Pi OS.          | Trixie   | arm64        |
| Raspberry Pi | Raspberry Pi OS.          | Bookworm | armhf        |
| Debian PC    | Debian                    | Bookworm | amd64        |
| Debian PC    | Debian                    | Trixie   | amd64        |
| Debian PC    | Debian                    | Bookworm | i386         |
| NanoPi Neo   | Armbian based on Debian   | Trixie   | armhf        |

A system that does not exactly match one of these entries is rejected without downloading or installing an SvxLink package.

The NanoPi Neo package is selected from the device-tree model, Debian Trixie identity and `armhf` package architecture. The fact that Armbian identifies itself as Debian in `/etc/os-release` does not cause it to receive a generic Debian PC package.

## Older operating systems

SvxLink-Bootstrap is intended to run only on the supported Bookworm and Trixie systems listed above.

The launcher refuses to proceed on Debian or Raspberry Pi OS releases earlier than Bookworm and performs this check before refreshing apt or installing dependencies. Installing `python3` on an older system would supply only the Python version and supporting packages available to that historical distribution; these may not be capable of running the current Bootstrap or SvxLink-Dash V4.0 software.

Do not use Bootstrap as an in-place operating-system upgrade tool.

For a system based on Jessie, Stretch, Buster, Bullseye or any another unsupported release:

1. Record the existing radio, audio, GPIO, squelch, transmitter, logic, module and reflector configuration.
2. Make an independent copy of `/etc/svxlink`, `/etc/default/svxlink` and any locally maintained scripts or certificates.
3. Install a currently supported operating system appropriate to the hardware.
4. Update and reboot the new operating system.
5. Run SvxLink-Bootstrap as a fresh installation.
6. Recreate and validate the required configuration through SvxLink-Dash V4.0.

Historical configuration should be retained for reference, but it should not be restored wholesale over the current installation. GPIO libraries, device naming, reflector protocols, talkgroup operation and configuration structure may differ substantially.


## Before running Bootstrap

The operator is responsible for updating the operating system before starting SvxLink-Bootstrap.

On a newly installed or existing system, run:

```bash
sudo apt-get update
sudo apt-get upgrade --yes
sudo reboot
```

Reconnect after the system has restarted.

Bootstrap does not perform a general operating-system upgrade. Its launcher refreshes the APT package index only so that its own essential prerequisites can be installed.

The target system must have:

* Working network access.
* Correct DNS resolution.
* Access to Debian or Raspberry Pi OS package repositories.
* Access to GitHub.
* A working `apt-get` installation.
* Root authority through `sudo` or a root login.
* `curl` available for the one-line launcher.

If `curl` is not installed:

```bash
sudo apt-get update
sudo apt-get install --yes curl
```

## Quick installation

Run the launcher from the target system:

```bash
curl -fsSL \
https://raw.githubusercontent.com/f5vmr/Svxlink-Bootstrap/main/launch-bootstrap.sh |
sudo sh
```

The launcher requires root authority. It:

1. Confirms that the host reports a supported Debian or Raspberry Pi OS identity and a Bookworm or Trixie release before using APT.
2. Refreshes the APT package index.
3. Installs `ca-certificates`, Git, Python 3 and Flask if required.
4. Creates a temporary working directory.
5. Clones the current `main` branch of SvxLink-Bootstrap.
6. Starts the temporary Bootstrap web manager.
7. Removes the temporary checkout when the web manager finishes.

Keep the terminal open throughout installation and Dashboard handover.

### Inspecting the launcher before running it

Operators who prefer to inspect the launcher first can use:

```bash
curl -fsSL \
https://raw.githubusercontent.com/f5vmr/Svxlink-Bootstrap/main/launch-bootstrap.sh \
-o /tmp/launch-bootstrap.sh

less /tmp/launch-bootstrap.sh

sudo sh /tmp/launch-bootstrap.sh
```

## Opening the Bootstrap web manager

The launcher prints a unique address similar to:

```text
http://192.168.1.203:8765/?token=<unique-access-token>
```

Open the complete address in a browser on the same trusted network.

The temporary web manager:

* Listens on TCP port `8765`.
* Uses a randomly generated access token.
* Uses a separate confirmation token when installation is requested.
* Permits only one installation request during its lifetime.
* Remains open if installation fails so that the failure can be examined.
* Shuts down shortly after successful Dashboard handover.

The temporary interface uses HTTP and is intended for installation on a trusted local network. Treat the complete token-bearing URL as temporary privileged information and do not publish or forward it.

## What the inspection page shows

Before making any system changes, the web manager displays:

### Detected system

* Operating-system name.
* Hardware platform.
* Debian package architecture.
* Device model, when supplied by the device tree.

### Selected package

* Debian package filename.
* GitHub release tag.
* Recorded package size.
* Recorded SHA-256 digest.

### Existing SvxLink installation

* Whether an installation was detected.
* Installation type.
* Reported or embedded version.
* Executable path.
* systemd service state.
* Debian package status.

### Proposed action

The page explains whether Bootstrap will:

* Install SvxLink.
* Retain an existing package.
* Convert a supported compiler installation.
* Stop for manual review.

Review this information before selecting **Install SvxLink-Dash V4.0**.

## Host detection

Bootstrap obtains host information from standard system interfaces:

* Operating-system identity and release codename from `/etc/os-release`.
* Debian package architecture from `dpkg --print-architecture`.
* Hardware model from `/proc/device-tree/model`, when available.

Platform classification is applied in this order:

1. A device model containing `Raspberry Pi` is classified as `raspberry_pi`.
2. A device model containing both `NanoPi` and `Neo` is classified as `nanopi_neo`.
3. A system whose operating-system ID is `debian` is classified as `debian`.
4. Other values remain unsupported unless explicitly added to the manifest.

Package selection succeeds only when exactly one manifest entry matches every required field. No match or multiple matches cause processing to stop.

## Package integrity and trust

The package manifest records the expected:

* Package filename.
* GitHub release URL.
* Exact byte size.
* SHA-256 digest.
* Platform and operating-system compatibility.

Bootstrap accepts package URLs only from:

```text
https://github.com/f5vmr/svxlink/releases/
```

The selected package is initially downloaded to a file ending in `.part`.

Before that file can be retained or installed, Bootstrap verifies:

1. The package filename is safe.
2. The download URL is within the trusted release location.
3. The expected size is a positive integer.
4. The recorded SHA-256 value is valid.
5. The downloaded byte count exactly matches the manifest.
6. The calculated SHA-256 digest exactly matches the manifest.

Only after every check succeeds is the partial file atomically renamed to its final `.deb` filename.

A failed or interrupted download is not installed.

## Existing-installation detection

Bootstrap does not rely solely on the Debian package database. It also looks for evidence left by compiler-installed or partially removed installations.

An existing installation is considered present if one or more of the following is found:

* An `svxlink` executable.
* A loaded `svxlink.service`.
* An SvxLink Debian package record.
* An `svxlink` system user.
* `/etc/svxlink`.
* `/etc/default/svxlink`.

Where possible, Bootstrap runs:

```bash
svxlink --version
```

If the executable cannot run because a shared library or another runtime component is missing, Bootstrap attempts to read the embedded SvxLink version from the executable. The runtime failure is retained and displayed for manual review.

## Installation decisions

Bootstrap deliberately follows a conservative decision policy.

### SvxLink is absent

The selected package is downloaded, verified and installed using APT.

No configuration backup is attempted when no previous SvxLink configuration exists.

### Package-managed SvxLink 26.05.1 is installed

The existing package is retained.

Bootstrap does not download or reinstall SvxLink, but it backs up the existing configuration before installing or updating SvxLink-Dash V4.0.

### Catalogued compiler-installed SvxLink release is detected

This replacement path applies only when the older SvxLink installation is already running on a currently supported Bookworm or Trixie host. It does not make an older operating system eligible for Bootstrap.

Bootstrap permits automatic replacement of compiler-installed SvxLink releases from the following release families:

* 24
* 25
* 26

SvxLink reports a software version and release version separated by `@`. For example:

```text
1.10.1@26.05.1
```

Bootstrap applies the replacement catalogue to the release component after `@`.

Automatic replacement is permitted only when:

* The release component begins with 24, 25 or 26.
* The host operating system and architecture exactly match a supported package in the manifest.
* `svxlink.service` is loaded.
* The canonical executable is `/usr/bin/svxlink`.
* SvxLink is not already recorded as an installed Debian package.

For a recognised older release, the inspection page displays the detected version and warns that it will be upgraded to the verified SvxLink 26.05.1 Debian package. The installation button remains available so that the operator can approve the replacement.

Bootstrap then:

1. Backs up the existing configuration.
2. Downloads and verifies the selected package.
3. Stops `svxlink.service` if it is active.
4. Installs the verified SvxLink 26.05.1 Debian package.
5. Verifies the resulting package-managed installation.
6. Installs SvxLink-Dash V4.0.

### Earlier, unidentified or nonstandard installation is detected

Automatic installation stops for manual review.

This includes:

* SvxLink release families earlier than 24.
* A version without a recognisable release component after `@`.
* A compiler installation in a nonstandard executable location.
* Configuration files, users or service remnants that cannot be safely classified.
* A package-managed SvxLink version other than 26.05.1.

Earlier SvxLink releases were commonly installed on operating systems and hardware-support environments that are not compatible with the current packages and Dashboard configuration model. Differences can include GPIO handling, library availability, reflector protocols, talkgroup operation and configuration structure.

For these systems, a fresh installation of a currently supported operating system followed by SvxLink-Bootstrap is advised. Preserve the old configuration separately for reference, but do not assume that it can be restored unchanged onto SvxLink 26.05.1.

When Bootstrap blocks an installation, the installation button is not offered and no automatic package replacement is attempted.


## Configuration backup

Before retaining or converting a supported existing installation, Bootstrap copies the existing SvxLink configuration into a timestamped directory beneath:

```text
/var/backups/svxlink-bootstrap
```

For example:

```text
/var/backups/svxlink-bootstrap/20260913-212058
```

The original directory layout is preserved:

```text
/var/backups/svxlink-bootstrap/<timestamp>/etc/svxlink/
/var/backups/svxlink-bootstrap/<timestamp>/etc/default/svxlink
```

The complete `/etc/svxlink` tree is copied recursively. This includes subdirectories and locally added material such as reflector, certificate or federation-related configuration.

Symbolic links are preserved as symbolic links, and normal file metadata is retained where possible.

The backup is constructed in a temporary staging directory. It is renamed to the final timestamped directory only after the copy succeeds. If backup creation fails, installation stops before package conversion or Dashboard installation.

### Inspecting available backups

List backup generations with:

```bash
sudo find \
/var/backups/svxlink-bootstrap \
-mindepth 1 \
-maxdepth 1 \
-type d \
-print |
sort
```

Inspect one backup without changing the system:

```bash
sudo find \
/var/backups/svxlink-bootstrap/<timestamp> \
-print
```

Do not copy an old configuration back over an active installation without first reviewing the differences and stopping the relevant services.

## Debian package installation

A downloaded package is installed with APT in noninteractive mode.

Bootstrap instructs `dpkg` to retain existing configuration files where a package configuration conflict occurs. This complements, but does not replace, the timestamped Bootstrap backup.

After APT finishes, Bootstrap verifies that:

* SvxLink 26.05.1 is detected.
* SvxLink is recorded as package-managed.
* `/usr/bin/svxlink` is owned by the installed `svxlink` package.
* The canonical executable is `/usr/bin/svxlink`.
* `/usr/bin/svxlink --version` runs successfully.

APT returning success is not, by itself, treated as proof of a valid installation.

## Installation progress

After installation is authorised, the web manager reports these stages:

1. Preserve existing configuration.
2. Download and verify package.
3. Prepare the existing SvxLink service.
4. Install and verify SvxLink 26.05.1.
5. Install SvxLink-Dash V4.0.
6. Open Dashboard configuration.

Stages that are unnecessary are shown as skipped. For example, a clean installation has no existing configuration to preserve, while a retained package does not require a package download.

Do not close the browser, close the terminal or interrupt power while installation is running.

## SvxLink-Dash V4.0 installation

After SvxLink has been prepared, Bootstrap:

1. Creates a temporary working directory.
2. Clones the `main` branch of:
   [f5vmr/SvxLink-Dash-V4.0](https://github.com/f5vmr/SvxLink-Dash-V4.0)
3. Confirms that `install/install-dashboard.sh` exists and is executable.
4. Runs the Dashboard’s established installer.
5. Verifies that the installer completed successfully.
6. Records `/opt/dashboard` as the installed Dashboard location.

The Dashboard repository remains responsible for its own:

* Package dependencies.
* Runtime directories.
* File ownership and permissions.
* systemd service.
* Application installation beneath `/opt/dashboard`.

## Dashboard handover

When installation succeeds, the Bootstrap page displays a completion message and automatically opens:

```text
http://<device-address>:5000/start
```

This is the permanent SvxLink-Dash V4.0 configuration workflow.

The Bootstrap web manager shuts down shortly after handover. Port `8765` is temporary and is not the operational Dashboard address.

The permanent Dashboard normally uses:

```text
http://<device-address>:5000/
```

A new installation initially presents the **Authorise editing** page. Continue through the Dashboard’s guided configuration workflow to define the installation identity, radio hardware, audio, receiver, transmitter, squelch, logic, modules, reflector access and operating preferences.

**Continue with the full Dashboard guide:**

[SvxLink-Dash V4.0 configuration and operating documentation](https://github.com/f5vmr/SvxLink-Dash-V4.0#readme)

## Service state after installation

A successful package installation does not necessarily mean that `svxlink.service` should immediately be active.

On a new or converted system, the service may remain inactive until a valid configuration has been created and deployed through SvxLink-Dash V4.0. This avoids starting SvxLink against incomplete or unsuitable configuration.

The Dashboard service should be available for the configuration workflow.

Check both services with:

```bash
systemctl status \
svxlink.service \
svxlink-dash.service \
--no-pager
```

For concise results:

```bash
systemctl is-active svxlink.service
systemctl is-active svxlink-dash.service
systemctl is-enabled svxlink-dash.service
```

In systemd output:

* `Loaded: loaded` means the unit file was found and loaded successfully.
* `Active: active (running)` means the service process is currently running.
* `enabled` means the service is configured to start during normal boot.

## Verifying the completed installation

Check the installed Debian package:

```bash
dpkg-query -W \
-f='${Package}\t${Version}\t${Architecture}\t${Status}\n' \
svxlink
```

Locate the executable:

```bash
command -v svxlink
```

Check the executable version:

```bash
/usr/bin/svxlink --version
```

For release 26.05.1, the expected executable version is:

```text
1.10.1@26.05.1
```

The embedded version must not contain an operating-system, release-tag or processor-architecture label.

Check the permanent Dashboard listener:

```bash
ss -ltnp |
grep ':5000'
```

After successful handover, the temporary Bootstrap listener should no longer be present:

```bash
ss -ltnp |
grep ':8765'
```

No output from the final command is expected after the temporary server has stopped.

## Read-only compatibility check

For development or diagnostic use, clone the repository and run Bootstrap without an installation option:

```bash
git clone \
https://github.com/f5vmr/Svxlink-Bootstrap.git

cd Svxlink-Bootstrap

python3 bootstrap.py
```

This reports:

* Detected host information.
* The exact compatible manifest package.
* Existing SvxLink evidence.
* The proposed installation action.

It does not download files or change the system.

## Download-only operation

To download and verify the selected package without installing it:

```bash
python3 bootstrap.py \
--download /tmp/svxlink-packages
```

This operation:

* Detects the host.
* Selects the exact package.
* Downloads it into the requested directory.
* Verifies its filename, size and SHA-256 digest.
* Does not install the package.
* Does not change SvxLink configuration.

If a current package-managed SvxLink 26.05.1 installation is already present, the package download is skipped.

The destination directory must be writable by the user running the command.

## Direct command-line installation

The browser workflow is recommended for normal use because it displays the detected system, proposed action and live progress.

A cloned checkout can also perform installation directly:

```bash
sudo python3 bootstrap.py \
--install
```

This uses the same host detection, package selection, backup, download, verification, package installation and Dashboard installation logic as the web manager.

The `--download` and `--install` options are mutually exclusive.

## Exit statuses

The command-line Bootstrap uses these principal exit statuses:

| Status | Meaning                                             |
| -----: | --------------------------------------------------- |
|    `0` | Operation completed successfully                    |
|    `1` | Host detection failed                               |
|    `2` | No exact supported package could be selected        |
|    `3` | Package download or integrity verification failed   |
|    `4` | Existing installation blocked automatic processing  |
|    `5` | Root authority was required                         |
|    `6` | Configuration backup failed                         |
|    `7` | SvxLink package installation or verification failed |
|    `8` | SvxLink-Dash V4.0 installation failed               |
|    `9` | The existing SvxLink service could not be prepared  |

## Troubleshooting

### The launcher says root authority is required

Run the launcher through `sudo sh`:

```bash
curl -fsSL \
https://raw.githubusercontent.com/f5vmr/Svxlink-Bootstrap/main/launch-bootstrap.sh |
sudo sh
```

### No compatible package is found

Record:

```bash
cat /etc/os-release

dpkg --print-architecture

cat /proc/device-tree/model 2>/dev/null || true
```

The detected platform, operating-system identity, codename and architecture must match one manifest entry exactly.

Do not install a package intended for another platform merely because its Debian architecture is the same.

### The Bootstrap page cannot be opened

Confirm that the terminal still shows the web manager running.

On the target system, check:

```bash
ss -ltnp |
grep ':8765'
```

Use the complete URL printed by the launcher, including its access token. Ensure the browser is using the correct device address and is on a network permitted to reach the target system.

### Access is denied

A missing, incomplete or incorrect access token returns HTTP status `403`.

Return to the terminal and copy the complete URL printed by the launcher.

### Installation is blocked

Review the installation type, version, executable path, runtime error, service state and Debian package status displayed on the page.

Bootstrap intentionally refuses to replace a pre-24, unidentified, nonstandard or incompatible package-managed installation automatically.

For a pre-24 installation, preserve all required information and configuration for reference, then perform a fresh installation of a supported operating system and run SvxLink-Bootstrap. Recreate the required configuration through SvxLink-Dash V4.0 rather than restoring an incompatible historical configuration unchanged.

### Package verification fails

Do not bypass the size or SHA-256 checks.

A mismatch may mean:

* The release asset was replaced.
* The manifest is outdated.
* The download was incomplete.
* The wrong release URL was recorded.
* The downloaded content is not the expected Debian package.

The release asset and manifest must be audited and corrected together.

### Backup creation fails

Package conversion and Dashboard installation stop if a required backup cannot be completed.

Check:

* Available disk space.
* Permissions beneath `/var/backups`.
* Read access to `/etc/svxlink`.
* Read access to `/etc/default/svxlink`.
* Whether the proposed timestamped destination already exists.

### The existing service cannot be stopped

Bootstrap will not install over an active compiler installation if `svxlink.service` cannot be stopped successfully.

Inspect:

```bash
systemctl status \
svxlink.service \
--no-pager -l

journalctl \
-u svxlink.service \
-n 100 \
--no-pager
```

Resolve the service-control problem before retrying.

### Dashboard installation fails

The Bootstrap page remains available and marks the Dashboard stage as failed.

Review the displayed installation log and check:

```bash
systemctl status \
svxlink-dash.service \
--no-pager -l

journalctl \
-u svxlink-dash.service \
-n 100 \
--no-pager
```

The SvxLink package may already have been installed successfully even if the later Dashboard stage fails.

### The Dashboard opens but SvxLink is inactive

This can be expected before the initial Dashboard configuration has been completed.

Authorise editing, complete the guided configuration, validate the model and deploy the generated SvxLink configuration before expecting `svxlink.service` to run normally.

## Development and testing

Run the complete Bootstrap test suite from the repository root:

```bash
python3 -m unittest discover \
-s tests \
-p 'test_*.py'
```

Before committing changes, also run:

```bash
git diff --check
```

The current suite covers launcher release preflight checks, host detection, package selection, package verification, existing-installation classification, configuration backup, service control, package installation, Dashboard installation, command-line behaviour and web-manager orchestration.

## Extending platform support

New platforms can be added through the controlled package manifest without rewriting the core selection algorithm.

Each manifest entry must uniquely identify:

* Platform.
* Accepted operating-system IDs.
* Release codename.
* Debian architecture.
* GitHub release tag.
* Asset filename.
* Exact byte size.
* SHA-256 digest.
* Trusted release URL.

A new entry must be accompanied by package-selection and host-detection tests where appropriate. The release asset must be audited before its size and digest are recorded.

## Attribution

SvxLink 26.05.1 remains the work of Tobias Blömberg, SM0SVX, and the upstream SvxLink contributors.

SvxLink-Dash V4.0 and SvxLink-Bootstrap are developed and maintained by Chris Jackson, G4NAB.

These projects provide packaging, installation, configuration and operational management around SvxLink. They do not replace the upstream SvxLink project or its authoritative documentation.
