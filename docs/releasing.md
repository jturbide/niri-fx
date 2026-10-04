# Maintaining releases

This guide is for maintainers preparing a release. For installation and package
selection, use [Releases and downloads](releases.md). Before publishing 1.0 as
stable, complete
all [stability acceptance criteria](stability.md#acceptance-criteria-for-10).
Subsequent 1.x releases must preserve that published contract and pass the
compatibility fixtures from all earlier stable 1.x interfaces, even when those
older binaries no longer receive fixes.

## Changelog policy

Add user-visible changes to [Unreleased](../CHANGELOG.md) in the same pull request
as the change. Use Added, Changed, Fixed or Removed, and describe observable
behavior. Mention changed defaults and required migration actions explicitly.
Documentation-only work does not require an immediate package version bump.

When releasing, choose `MAJOR.MINOR.PATCH`, replace Unreleased's populated section
with the version/date, and leave a new empty Unreleased heading above it. Keep
`pyproject.toml` and `niri_fx/__init__.py` in sync. Historical development
milestones in the changelog do not imply published tags; do not create backdated
releases just to fill the list.

## Prepare a release

1. Review the complete diff and changelog. Check that unselected resize leaves
   existing settings unchanged and distinguish stock support, browser concepts
   and patched compositor capabilities.
2. Run the [contributor checks](../CONTRIBUTING.md), including lint/format, docs, unit/integration/browser E2E tests,
   GLSL compilation and installed Niri validation. Require the GitHub Checks
   workflow to pass on the exact proposed commit.
3. Build with `python3 -m build`. Inspect the wheel and source archive, including
   shader/editor resources, docs/media, the source patch and license texts.
   Install the wheel in a clean virtual environment and run `render` and `preview`
   from outside the checkout. The source archive must also build a wheel.
4. For rendering changes, run the browser checks and relevant native checks.
   Record hardware/scale and limitations when claiming desktop acceptance.
   Do not present the debug movement build as a performance benchmark.
5. For new public content, scan history and the proposed tree for credentials;
   inspect binary assets for private content. Keep raw reports in ignored
   artifacts. Review attribution and imported code separately.
6. Create a focused, **signed** version commit on a branch, verify its signature
   and open a pull request. Merge only after the exact head passes `lint`,
   `validate (3.10)`, `validate (3.14)` and `browser`. Never bypass signing or
   branch protections to work around a failure.

Commands after that pull request is merged (replace `X.Y.Z`):

```sh
git switch main
git pull --ff-only
git verify-commit HEAD
git tag -s vX.Y.Z -m "NiriFX X.Y.Z"
git verify-tag vX.Y.Z
git push origin vX.Y.Z
```

Only tag/publish when the maintainer has approved that release. Use the changelog
entry as the GitHub release notes and label prototype releases as prereleases.
Create a draft first, review asset contents, then publish. Package registry
publication is a separate decision; no automatic PyPI upload is configured.

Use `NiriFX X.Y.Z` for the GitHub release title. Put feature summaries in the
release notes, keeping titles consistent across versions.

## Repository maintenance

Keep the public [release and download guide](releases.md), versioned documentation
and package contents consistent. Review screenshots, recordings, source archives
and release notes for personal data and local workspace details before upload.

Maintain required pull-request checks, signed commits, read-only workflow tokens
and pinned third-party actions. Confirm the reporting link in
[SECURITY.md](../SECURITY.md) works. Keep raw audit reports, local configuration
snapshots and outreach drafts outside tracked files.
