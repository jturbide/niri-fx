# Public-release preparation

Prepared on **2026-10-02**. The project is suitable for review as an **early
prototype**, with explicit capability and validation limits. This record does
not mean that repository visibility, a GitHub release or a package publication
has been changed.

## Prepared content

- README with quick starts, feature/compatibility boundaries, Studio screenshot
  and 17 GIFs covering every preset and supplied scenario.
- Installation, updating, rollback, controls, troubleshooting, integration,
  compatibility and experimental movement guides.
- Changelog reconstructed from versioned history, plus an Unreleased section and
  a contributor/release policy for maintaining it.
- Bug/feature templates, PR template, security policy and scoped license notices.
- Project metadata/topics, package links, complete source assets, and a CI check
  for local documentation links, GIF metadata and version/changelog consistency.

## Inspection record

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
The GIF gallery totals about 15 MiB; the largest clip is the native swap.

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

## Visibility and launch settings

The repository remains **private** during preparation. No history rewrite was
needed based on the inspection results. No tags, releases or public package
uploads were created as part of this update.

The branch-protection API returned HTTP 403: the current plan requires GitHub Pro
or a public repository for that feature. Configure protection after the visibility
decision. Private vulnerability reporting and public security features also need
verification at launch; the security policy includes a fallback contact request
while private reporting is unavailable.

Before changing visibility, review the final commit and require its Checks run
to pass. After the owner approves publication, follow [the launch steps](releasing.md#first-public-launch)
for anonymous access, branch rules, security reporting and README/media rendering.
Re-run the audit if additional code, assets, issues or workflow output are added
before launch.
