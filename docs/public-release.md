# Public-release preparation

Reviewed on **2026-10-02** for the first public **0.5.0 prerelease**, with explicit
capability and validation limits. This page records the audit scope; see the
[repository](https://github.com/jturbide/niri-fragments) and
[release page](https://github.com/jturbide/niri-fragments/releases/tag/v0.5.0)
for current publication status. No PyPI or AUR publication is configured.

## Prepared content

- README with quick starts, feature/compatibility boundaries, Studio screenshot
  and GIFs covering every preset and supplied scenario.
- Installation, updating, rollback, controls, troubleshooting, integration,
  compatibility and experimental movement guides.
- Changelog reconstructed from versioned history, plus an Unreleased section and
  a contributor/release policy for maintaining it.
- Bug/feature templates, PR template, security policy and scoped license notices.
- Project metadata/topics, package links, complete source assets, and a CI check
  for local documentation links, GIF metadata and version/changelog consistency.

## Initial inspection record

The initial audit covered all five existing development commits through
`7ac916d5e1381fe52db9aaac9741c326e708f0ba`, 83 unique historical file blobs and the
proposed documentation/media tree. The Git history used the maintainer's GitHub
noreply author identity; all five existing commit signatures verified.

Gitleaks **8.30.1**, downloaded from its official release and checked against the
published SHA-256, reported no credentials in that history, the proposed tree or
the five completed Checks workflow logs. A separate historical text scan found no personal absolute
home paths, private infrastructure domains or private-key blocks. These are
bounded checks, not proof that every possible secret pattern is detectable.

All six historical image blobs and the new recording sources/representative
frames were inspected. They contain synthetic window content. Raw recordings,
test reports, toolchains and built binaries remain ignored under `artifacts/`.
The initial 17-GIF gallery totaled about 15 MiB. The follow-up showcase expands
it to 24 GIFs (about 25 MiB), adding synchronized comparisons and three importable
custom examples. Their synthetic sources and representative frames were also
inspected. The largest clip remains the native swap.

At inspection, GitHub contained no issues/PRs (including closed), releases or
repository Actions secrets. Five completed project Checks runs were successful;
GitHub-generated dependency graph jobs were still queued and had no completed
logs to inspect. The project workflow uses read-only token permissions and pinned
action SHAs. No workflow publishes packages or deploys software.

The original application/shaders/assets have MIT notices. The separate
Niri-derived movement patch has GPL-3.0-or-later notices and license text.
The source archive now includes the patch needed by its build scripts. The wheel
contains the Python/editor/shader resources and license notices, without a
patched compositor binary or patch installation. See [license scope](../THIRD_PARTY.md).

Local verification includes 22 regression tests, 44 shader compilations, 11 stock
Niri config validations, source/wheel builds and installed CLI render/preview
checks outside the checkout. The native GIF recorder was rerun successfully in
its own nested session. See [validation limits](validation.md); DMS runtime and
broad desktop performance acceptance remain open.

## 0.5.0 launch review

The new gallery has 31 GIFs (about 30 MiB), including seven new preset/origin/resize
clips. Synthetic sources and representative frames were inspected. Setup and
restore use temporary fixtures during tests; the maintainer's active desktop
configuration is not part of the release assets. The release adds a browser CI
job with pinned actions and read-only token permissions.

Current validation is recorded in [validation.md](validation.md). The first
public artifact is a **prerelease**: stock open/close and optional resize,
app-style Studio, iNiR registration and standalone setup. Native movement is an
isolated experiment; DMS-native settings, seamless swap retargeting and broad GPU
performance acceptance remain future work.

## Visibility and launch settings

The repository was private during the initial audit. The maintainer subsequently
approved public visibility and a signed v0.5.0 GitHub prerelease, after validation
and final inspection. No history rewrite was needed based on the audit results.

During private preparation the branch-protection API returned HTTP 403 because
of the account plan. Branch protection and public security features must be
configured and verified once visibility permits them. Required checks are
`validate (3.10)`, `validate (3.14)` and `browser`; force pushes and deletion must
be blocked. The owner/admin retains a recovery bypass for emergency maintenance;
normal changes should use pull requests and successful checks.

Before changing visibility, review the final commit and require its Checks run
to pass. For the approved publication, follow [the launch steps](releasing.md#first-public-launch)
for anonymous access, branch rules, security reporting and README/media rendering.
Re-run the audit if additional code, assets, issues or workflow output are added
before launch.
