# Factory image contents and Init ordering

Machinista Synth's original Factory collection is required image content:
264 patches, thirteen category banks, and the nine generated wavetable assets
referenced by them. Personal Sounds, recordings, sample libraries, ROMs and
third-party LV2 binaries/banks are outside this allowlist.

`tools/factory_payload.py` validates this declared set before release packaging.
`tools/prepare_beta_release.py` fails if a required bank, metadata file or wave
is missing, invalid or references undeclared user content. No full new SD image
is produced merely by changing this packaging rule.

All host-managed parameter-bank instruments (Machinista Synth, OB-Xd, Dexed and
RaffoSynth) list their Factory/imported banks before Init. Within a bank, Init,
Init Patch, Init Voice and similar explicit Init entries appear last. The
original file/program identities are retained; saved projects and Sounds keep
their controls and selection. This does not reorder hardware MIDI program
numbers or ROM banks of instruments that use their own native bank controls.

The controller and WebUI share the catalog. To reach the preceding banks from
Init at the final position, turn the bank encoder left. If no banks are installed,
Init remains available on its own.

62 tests pass locally and on ARM, covering preserved program IDs, old projects,
WebUI loading, background bank refresh, and an isolated clean Factory payload
with all dependencies. Test artifacts: output/init-bank-order/.
