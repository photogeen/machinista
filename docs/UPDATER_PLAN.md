# Machinista updates

The update menu is implemented in System and in the WebUI. Beta and Release use
one shared, persistent channel selection. Release is the default. Checking is
manual; there is no scheduled installation or unattended OS upgrade.

## One image for everyone

All installations include the update menu and the root-owned updater service.
There is no public/supporter feature split. Legacy image-edition markers do not
hide the UI. A missing signing key or feed configuration leaves installation
unavailable with an explicit status; it never bypasses signature verification.
`tools/prepare_beta_release.py` creates a standard image marker and
`tools/build_beta_image.py` provisions the broker on every new image.

## User workflow

Open System > UPDATE, or Updates in the WebUI. Choose Beta or Release, then
CHECK / Check for updates. Installed version, latest compatible version, channel,
release notes, progress and errors come from the same service.

For installation, stop PLAY, REC and audio capture, finish other operations, then
choose INSTALL / Install update and confirm Save & update. The running application
rechecks that it is idle and temporarily prevents new recording/input while it
prepares to save and stop. A shared maintenance lock excludes shutdown/reboot.

The broker downloads and verifies first, saves/stops Machinista, retains a code
rollback archive plus a copy of the saved current project/settings, runs APT,
installs the application, restarts it and checks a fresh application heartbeat
from a new PID. It also restarts the WebUI. Finish using Power > Restart when the
completion state requests a Pi restart for OS/kernel changes.

Projects, samples, imported Sounds, LV2 binaries/state, imported plugin banks, settings,
network configuration and SSH keys are outside the update payload. They are not
replaced or reset. Only reserved built-in Machinista Synth factory category banks
and content-addressed generated factory waves can be updated. Rollback restores application code; it does not undo the
user's project save. Space required before starting: at least 2 GiB or four times
the download size, whichever is larger.

## Raspberry Pi OS

The fixed commands are `apt-get update`, followed by noninteractive
`apt-get -y --no-remove -o Dpkg::Options::=--force-confold dist-upgrade`.
They update installed packages, kernel and stable firmware within the configured
OS release. Existing configuration files are retained. If package removals are
necessary, the operation stops rather than silently removing an audio component.
There is no `rpi-update`, bootloader experimental firmware, source-list rewrite
or automatic major distribution upgrade.

APT changes cannot be atomically rolled back with the application. A failed or
interrupted OS upgrade may need `dpkg --audit`, `dpkg --configure -a` and APT
repair from SSH, or recovery from the SD backup/image. Error status and
`/var/lib/machinista-updater/update.log` identify this case. Application code is
restored after a failed restart or interrupted transaction. Keep power connected
through the complete update and restart; use an image backup before testing real
OS updates. No real APT upgrade is executed by automated tests or setup.

Raspberry Pi's recommended APT/major-version distinction:
https://www.raspberrypi.com/documentation/computers/os.html

## Configure the signed GitHub feed

The repository is photogeen/machinista, with beta and release branches.
The production signing key and signed feed still require trusted provisioning.
Never publish the private signing key.

1. Use the GitHub repository with `beta` and `release` branches. Keep the source
   appropriate to each train on its branch.
2. Create an Ed25519 signing key outside the repository:
   `openssl genpkey -algorithm ED25519 -out update-private.pem`.
   Export only its public key with
   `openssl pkey -in update-private.pem -pubout -out update-public.pem`.
3. Install the public key as root-owned `/etc/machinista/update-public.pem` and
   edit root-owned `/etc/machinista/updater.json`. Keep both files mode 0644. Set `repository` to
   `OWNER/REPOSITORY` and `public_key` to that public-key path. Do not store an
   access token/private signing key in the image or expose feed/key edits via HTTP.
4. Build/test a sanitized ARM64 payload and increment `app/branding.py` VERSION.
   Use `tools/build_update.py` with `--payload`, `--key`, `--repository`,
   `--channel beta|release`, `--version`, `--minimum-version`, `--os-codename trixie`
   and `--output`. The release train requires a final version; beta may use a
   prerelease. Check the current target image codename before choosing it.
5. Upload the generated `machinista-VERSION-arm64.tar.gz` as a GitHub Release
   asset under tag `vVERSION`. Commit the generated `update.json` and
   `update.json.sig` to `updates/` on the corresponding branch **after** the asset
   upload. GitHub releases attach binaries to a tagged revision:
   https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
6. Check and exercise an actual signed application+APT update on a disposable SD
   card, including interrupted network, reboot and restoration, before enabling
   the feed for users. Tests use temporary keys and fake APT/service calls.

The broker reads
`https://raw.githubusercontent.com/OWNER/REPOSITORY/CHANNEL/updates/update.json`
and its detached Base64 Ed25519 signature. Signature validation precedes parsing
and download. The manifest pins version, channel, architecture, OS codename,
minimum installed version, release notes, artifact byte count and SHA-256.
Artifacts must belong to the configured repository's GitHub Releases. Redirects
are limited to GitHub's download hosts; archive links, traversal, user-data paths,
oversized archives and non-ARM64 executable payloads are rejected.

Checksums alone do not establish release trust. The root-owned updater broker,
unit, signing key and APT configuration are not installed from the user-owned app
payload. A change to that privileged updater API/deployment requires an explicit
trusted provisioning/image step; the app updater does not execute migration
scripts or arbitrary shell supplied by GitHub or the WebUI.

## Implementation and offline verification

- `app/update_manager.py`: root-owned service core after provisioning.
- `tools/update_service.py`: peer-UID-checked Unix socket, fixed commands.
- `tools/update_rpc.py`: same-user idle/freeze handshake.
- `app/updater.py`: nonblocking controller adapter and display actions.
- `web/updates.js`, `/api/update`: status/channel/check/install plus CSRF checks.
- `deploy/machinista-updater.service`, `deploy/updater.example.json`: provisioning.
- `tools/build_update.py`: sanitized, architecture-checked artifact + signature.
- `tests/test_updater.py`: signatures, tampering, compatibility, idle/stale state,
  legacy edition compatibility, user-data preservation, failed APT/start rollback, interrupted
  transactions, controller routing, freeze and HTTP authorization.

Service logs/status survive a restart; a partially downloaded package is replaced
on retry. Channel changes invalidate the prior candidate. Downgrades are refused.
No automatic branch checkout, local compilation or plugin installation occurs.

## Published feeds

The deployment public key is distributed in deploy/update-public.pub and installed
as /etc/machinista/update-public.pem. The private signing key stays outside the
public export. Beta carries signed ARM64 packages; Release carries a signed empty
feed until a stable release exists. Empty feeds cannot install files. Each check
verifies the signature before accepting either kind of feed.
