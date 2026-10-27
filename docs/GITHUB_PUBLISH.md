# GitHub preparation and publication

## Prepared source tree

Run the exporter from the development workspace:

```sh
python3 tools/prepare_github.py --destination output/github/machinista
```

It creates a new directory, copies an explicit source/data allowlist, sanitizes
controller maps, validates the result and writes an inventory beside the export.
It refuses an existing destination. Never upload the original development
workspace or use git add -f to bypass exclusions. No history from that workspace
is copied. No GitHub repository, remote, commit or upload is created automatically.

The export retains reproducible original Factory assets and small required
fixtures. It omits external plug-ins, ROMs, private recordings, personal data,
local build products and the original development handoff/session log.

## Before public publication

- Review the custom LICENSE.md with specialist counsel and identify the publishing rights holder.
- Decide contributor terms before accepting outside code intended for commercial
  relicensing. The current contribution policy does not imply a CLA.
- Choose the actual GitHub owner/repository. No remote is preconfigured.
- Run tools/check_public_source.py in the export and review its inventory.

## Initial repository and branches

Run these commands inside the prepared export when ready. Use your own Git
identity; this preparation does not invent an author or commit on your behalf.

```sh
git init -b beta
git add .
git diff --cached --check
git commit -m "Initial Machinista source import"
git branch release
# Add the real GitHub remote, then push beta and release explicitly.
```

Keep beta for ongoing beta development; promote tested commits to release.
Protect release against direct writes and require CI checks/review. The included
workflow tests both branches and pull requests. It does not publish artifacts,
create releases, push branches or deploy devices.

## Releases and updates

Keep .img/.img.xz, manuals, compiled LV2 bundles and matching sources in release
assets rather than normal Git history. Add SHA256 checksums, component licenses,
a matching source archive, test results and explicit hardware qualification.
Tag stable releases vX.Y.Z and betas vX.Y.Z-beta.N after choosing the version.

The updater skeleton already distinguishes beta/release and public/supporter
editions. A Git branch alone is not an update feed: tools/build_update.py creates
a manifest and signed bundle. Configure the real repository and verification
key only when the release infrastructure is ready. Private signing keys remain
outside the repository. Public images retain updater=False.
