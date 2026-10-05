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
   from outside the checkout. The source archive must also build a wheel. From
   the extracted archive, run `python3 scripts/check-native-compatibility.py matrix`
   and `python3 scripts/build-nirifx-session.py --help`; verify every declared
   patch and the upstream license are present. These source-tool checks need no
   compositor build or network access.
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

## Native release candidates

The Python package and a patched compositor have different release gates. A
NiriFX package may include experimental build/session tools without shipping a
supported compositor binary. Keep those claims separate in release notes and
downloads. The [native compatibility matrix](native-compatibility.md) records
build targets; passing it does not certify a physical desktop.

Before publishing a native binary candidate:

- [ ] Select an exact Niri commit and ordered patch stack, and pass clean patch,
      compilation and regression checks for every advertised variant.
- [ ] Build with the declared desktop features and locked dependencies; retain
      toolchain, target, build identity, source, patch and license provenance.
- [ ] Package a distinctly named compositor and session alongside stock Niri.
      Declare runtime library dependencies and verify a clean installation on
      each advertised distribution and architecture.
- [ ] Exercise Studio and CLI review, stale-review refusal, next-login selection,
      rollback and interrupted-install recovery using the installed package.
- [ ] Complete the [physical session checks](native-session.md#updates-and-acceptance):
      startup, input, movement, resizing, capture, suspend, logout and return to
      stock. Record the tested GPU, outputs, scale and known limitations.
- [ ] Verify an ordinary Niri and shell upgrade leaves their sources unchanged
      and either keeps the native session working or provides a clear stock
      recovery path.
- [ ] Sign the release tag and declared artifacts, verify checksums and inspect
      the draft release's source correspondence, licenses and installation guide.

Keep a failed candidate out of supported downloads. Publish its limitation in
the compatibility results without changing users' installed or next-login
selections. A release candidate should invite testing against a stated scope;
it is not a substitute for the future [1.0 acceptance criteria](stability.md#acceptance-criteria-for-10).

## Repository maintenance

Keep the public [release and download guide](releases.md), versioned documentation
and package contents consistent. Review screenshots, recordings, source archives
and release notes for personal data and local workspace details before upload.

Maintain required pull-request checks, signed commits, read-only workflow tokens
and pinned third-party actions. Confirm the reporting link in
[SECURITY.md](../SECURITY.md) works. Keep raw audit reports, local configuration
snapshots and outreach drafts outside tracked files.
