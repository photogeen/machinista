# Build and test

## Linux prerequisites

Primary deployment: Raspberry Pi OS 64-bit (Debian Trixie), Raspberry Pi 4/5.
Python 3.13 is used on the deployment image. Portable Python tests also run on 3.12.

On Debian/Ubuntu, install the native development libraries:

```sh
sudo apt-get update
sudo apt-get install build-essential cmake ninja-build pkg-config \
  libhidapi-dev libasound2-dev liblilv-dev libusb-1.0-0-dev \
  python3 python3-venv ffmpeg rubberband-cli
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

The device image additionally uses distro-provided Pillow, D-Bus, GI and GPIO
bindings plus BlueZ, NetworkManager, Samba and systemd services. The authoritative
runtime package list is in tools/build_beta_image.py. Do not assume pip alone
installs the complete device environment.

## Native engine and decoder tests

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
```

Linux development libraries are required. x86-64 compilation verifies host-side
code; it is not an ARM image or a test of physical controller/audio hardware.
Do not run diagnostic HID tools alongside the main application.

## Python regression tests

```sh
python3 -m unittest discover -v -s tests
```

For a portable run without native integration tests, leave build/audio_engine
absent. Native suites detect the executable and ALSA. Some require optional test
LV2 fixtures (swh-lv2 and optionally mda-lv2), a running LV2 metadata scanner and
its manager. Skips must be reported, not counted as device coverage.

CI deliberately separates full portable Python discovery (no native binary)
from Linux CMake/CTest and the native color-display protocol integration. Full ARM image testing with isolated LV2 services remains
an additional release validation step.

## Run on a development device

```sh
python3 tools/machinista.py
```

Controller permissions and the required runtime services must already be
configured. Use the supplied image for normal use; starting this command does
not install system services. Running creates local config/projects/cache paths.
Back up a working device before changing its installation.

## Release image tooling

Read docs/GITHUB_PUBLISH.md and docs/INSTALL.md. tools/prepare_beta_release.py
assembles an explicit public payload from tested ARM binaries and original
Factory assets. tools/build_beta_image.py configures a disposable offline Pi OS
root; it is not an installer for the running system. Full disk partitioning,
firmware provenance, sanitization and cold-boot checks are separate steps.

Manual generation currently also requires ReportLab, PDF tooling, browser
capture dependencies and the configured document fonts. They are not runtime
requirements. Generated PDFs are distributed as release assets.
