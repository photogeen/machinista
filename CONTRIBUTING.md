# Contributing

The project is in beta and licensed under GNU GPL version 3 or later.
Submit original contributions under GPL-3.0-or-later unless a separate license
has been explicitly agreed. You retain your copyright and must have the right
to contribute the material. No copyright assignment or proprietary relicensing
permission is implied by a pull request. Discuss substantial changes first.

1. Start a branch from beta and keep changes focused.
2. Explain the visible problem and resulting behavior.
3. Run the relevant tests; report platform-specific skips and hardware checks.
4. Keep real-time audio free from file/network/display jobs.
5. Add regressions for changed behavior, especially shared controller workflows.
6. Keep private projects, samples, Wi-Fi data, credentials and hardware recordings
   out of commits. tools/check_public_source.py verifies the publication tree.
7. Preserve third-party notices and identify any introduced dependency/license.

For UI changes, show the affected controller screens and identify the tested
hardware. Do not claim that a rendered screenshot proves physical USB/audio
behavior. Identify any third-party code and its license before submitting it.
