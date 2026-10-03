# Maintaining releases

## Changelog policy

Add user-visible changes to [Unreleased](../CHANGELOG.md) in the same pull request
as the change. Use Added, Changed, Fixed or Removed, and describe observable
behavior. Mention changed defaults and required migration actions explicitly.
Documentation-only work does not require an immediate package version bump.

When releasing, choose `MAJOR.MINOR.PATCH`, replace Unreleased's populated section
with the version/date, and leave a new empty Unreleased heading above it. Keep
`pyproject.toml` and `niri_fx/__init__.py` in sync. Historical private
milestones in the changelog do not imply published tags; do not create backdated
releases just to fill the list.

## Prepare a release

1. Review the complete diff and changelog. Keep resize opt-in and distinguish
   stock support, browser concepts and patched compositor capabilities.
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

## First public launch

See the [preparation record](public-release.md). Changing repository visibility
exposes reachable Git history, metadata, issues, pull requests and Actions logs;
review those before the switch. Preparation does not itself authorize publication.

After the owner approves public visibility:

1. Change visibility, then verify anonymous access and README/media rendering.
2. Enable private vulnerability reporting, secret scanning and push protection
   where available. Confirm the private-report link in [SECURITY.md](../SECURITY.md).
3. Configure a main-branch rule requiring pull requests and the actual successful
   `Checks` jobs; block force pushes/deletion. Verify available settings on the
   account plan, and keep a documented maintainer recovery path.
4. Confirm Actions retain read-only default token permissions and external pull
   requests cannot access secrets. Keep third-party actions pinned to commit SHAs.
5. Recheck repository description/topics, clone instructions, issue forms and
   license rendering from an unauthenticated view.

Official references: [visibility changes](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility),
[private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).
