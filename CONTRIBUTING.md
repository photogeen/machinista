# Contributing

The project is in beta and uses the custom LICENSE.md. Contributor terms for
commercial relicensing are not yet finalized. Discuss substantial changes first;
no commercial relicensing permission is inferred from opening a pull request.

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
behavior. Maintainers will define contribution licensing before accepting code
that changes the commercial licensing position.
