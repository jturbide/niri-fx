# Stability and the path to 1.0

NiriFX is in **0.x development**. Commands, document formats and integrations can
still change as real use exposes better designs. Breaking changes belong in the
[changelog](../CHANGELOG.md), with practical migration guidance in
[Updating NiriFX](upgrading.md). This document sets the target for a future stable
release; it does not freeze today's interfaces or announce a 1.0 release date.
Version 0.20 and subsequent 0.x releases can deliver tested improvements while
these gates remain open. There is no requirement to move directly from 0.20 to 1.0.

The [roadmap](../ROADMAP.md) tracks the work. [Compatibility](compatibility.md)
describes current support, and [validation](validation.md) records what has
actually been tested.

## What 1.0 will mean

Before 1.0, publish an exact inventory of supported interfaces and their behavior.
From 1.0 onward, maintain backward compatibility for that public contract throughout
1.x. Following [Semantic Versioning](https://semver.org/), compatible additions
belong in minor releases, compatible fixes in patch releases, and incompatible
public-interface changes require 2.0 or a later major version. Deprecation can
begin in a minor release; removal waits for the next major release.

Features can keep growing during 1.x. New effects, presets, controls and internal
refactors are welcome when existing supported workflows keep their meaning.
Stability concerns the public contract, rather than every implementation detail
or an identical image on every GPU.

## Proposed public contract

The inventory below is the starting scope to finalize before 1.0. Each included
interface needs a versioned reference and executable compatibility checks.

| Surface | Intended guarantee during 1.x |
| --- | --- |
| Documented CLI commands and options | Existing invocations retain their documented meaning, output type and exit-status categories. Human-readable layout and error sentences may improve. |
| Machine-readable CLI results and discovery | Supported fields, types and meanings remain usable. The reference specifies which responses allow additive fields and how clients discover capabilities. |
| Portable styles and action profiles | Newer 1.x versions read documents from earlier stable 1.x interfaces, preserving parameter meanings, defaults, action choices and inheritance. |
| Preset and profile identifiers | Existing IDs remain resolvable. Materially redesigned looks receive new IDs; fixes preserve the documented visual intent. Recommendations and catalog ordering may change. |
| Saved user data | Upgrades retain access to named profiles, favorites and supported Restore history. Internal storage may migrate without discarding users' data. |
| Review, Apply and Restore | Applying remains tied to a reviewed plan; unrelated configuration and external edits remain protected. Earlier supported transactions can be restored after upgrading within documented environment constraints. |
| Export and adapters | Selected actions retain their meaning on the declared supported Niri and shell versions. Unsupported combinations are reported without silently activating a different effect. |
| Documented embedding APIs | Enumerate the supported Quickshell and GTK entry points, properties, methods and lifecycle behavior, or explicitly classify and version them as experimental before 1.0. |

The [agent guide](agents.md) builds on CLI discovery and the same Apply/Restore
contract. A future MCP adapter should reuse those operations.

### Starting compatibility corpus: 0.19

The first [versioned reference cases](../tests/fixtures/compatibility/v0.19/contract.json)
record a small, executable baseline of current behavior. They begin the contract
inventory; they do not freeze 0.19 interfaces or complete the 1.0 compatibility
gate. The existing broader validation and export-parity suites remain required.

| Recorded surface | Semantic expectation |
| --- | --- |
| Style schema 3 | Omitted parameters receive defaults; representative timing and shape bounds retain their values and units. Resize remains explicit. |
| Profile schema 1 imports | Valid older profiles normalize to schema 2 without changing their selected styles or optional-action inheritance. Invalid legacy null opening/closing choices are rejected. |
| Profile schema 3 swap override | Adds a fifth `swap` action using the same modes. Existing documents without an override remain schema 2. Stock exports omit it; managed activation requires the separate native swap contract. |
| Profile schema 2 action choices | All four action keys are required. `null` means Preserve, `"off"` means Off, and an effect object means NiriFX Style. Preserve omits the override; Off emits an explicit disabling node. |
| Profile schema 4 fragment response (0.21) | Requires all five action keys and 18 explicit response values. Dormant responses survive imports and edits. Native export requires an eligible material; legacy schemas gain no implicit response. |
| Pointer retention and stock export | Absent or null pointer settings preserve underlying behavior; zero strength is Off, and positive strength retains the chosen settings. Stock export omits experimental movement and pointer settings, including explicit Off choices. |
| Unsupported input | Unknown fields, schemas and actions, partial pointer settings, unsupported resize families, booleans used as numbers and out-of-range controls fail validation. CLI `inspect` returns status 2 with a diagnostic and no success JSON. Error sentences are not frozen. |
| Representative catalog IDs | `balanced`, `spring-wobble`, `frost-vanish` and `soft-landing` remain discoverable with their recorded families and action intent. Catalog size, ordering, recommendations and shader bytes are not snapshotted. |
| CLI JSON consumers | Discovery, parameter metadata, profile composition, normalized inspection and compact catalog examples retain the recorded fields, types and meanings. Additional response fields are allowed; this does not relax strict imported-document validation. |

Python and the DOM-free browser core consume the same reference documents. They
compare normalized values and stock action semantics, including omission and Off,
without requiring identical KDL formatting or stored shader text. CLI cases run
the actual module entry point, using temporary files for imports. These checks
run through the existing Python and Node test commands; focused runs are:

```sh
python3 -m unittest discover -s tests -p 'test_compatibility.py' -v
node --test tests/effect-core.test.mjs
```

Keep earlier reference cases reviewable when extending the corpus. An intentional
0.x change needs an explicit migration decision and updated guidance, rather than
silently replacing expected values to make a test pass. These examples do not yet
cover released-package upgrades, saved favorites and Restore history, the complete
CLI and adapter inventory, or a supported environment matrix. Native activation
and renderer contract numbers remain experimental and are outside this starting
baseline. All 1.0 gates below remain open.

### Compatibility has a direction

Backward compatibility means a newer 1.x release can use a document or command from any
earlier stable 1.x interface. It does not mean an older application can
understand every feature added later. Exporting for older versions, if offered,
must state its target and report settings that cannot be represented.

Current document readers reject unknown fields. Before freezing formats, choose
how documents identify new requirements and how unsupported input is reported;
do not silently discard settings. Define omitted fields, `null`, defaults and
Preserve / Style / Off explicitly. Updated NiriFX builds provide a separate Swap
override for explicit left/right swaps; pointer drag has separate controls even where their exported configuration shares
a node. See the [action-selection work](../ROADMAP.md#consistent-action-selection).

Application versions, document schema numbers, discovery schemas and native
renderer contract numbers are separate. A schema bump alone does not preserve
compatibility: newer readers still need to load or migrate the older supported
format. Existing 0.x documents need a documented migration decision before 1.0;
they are not automatically covered by a promise starting at 1.0.

Plan fingerprints and transaction IDs are opaque. An upgrade may require a fresh
review before Apply; it must retain access to supported Restore history. The
contract protects recovery behavior, not the bytes of an internal snapshot format.

## Implementation and experimental boundaries

Python module paths, JavaScript internals, shader templates, generated KDL/GLSL
formatting, DOM/CSS, test and recording helpers, hash construction and Studio's
session HTTP transport are implementation details unless explicitly included in
the public inventory. Generated exports must remain valid and preserve documented
behavior; they need not be byte-identical between releases.

Native movement and pointer deformation currently depend on pinned experimental
compositor patches. Before 1.0, decide whether each becomes supported or remains
explicitly experimental. A stable stock-Niri core can coexist with clearly marked
experiments. No advertised stable feature may be reclassified after release merely
to avoid its compatibility commitment. Portable retention of experimental settings
does not guarantee their activation on every compositor.

The support matrix must name tested Niri, Python, shell and toolkit versions, and
state how long each remains supported. NiriFX cannot guarantee compatibility with
unknown future upstream changes. Unsupported renderer contracts must continue to
fail safely. [Current native limitations](pointer-wobble.md) remain unresolved
until their own acceptance checks pass.

## Acceptance criteria for 1.0

These are release gates, not claims that the work is complete. Every gate needs
reviewable evidence from the proposed release. An unavailable required check
remains incomplete.

- [ ] **Complete the contract reference.** Enumerate stable CLI/JSON, document,
      preset, storage and adapter behavior; label every documented embedding API.
      Resolve defaults, action choices, error categories, schema evolution and
      0.x migration. Publish the supported environment and maintenance policies.
- [ ] **Establish a compatibility corpus.** Keep accepted documents and executable
      CLI/JSON workflows for the 1.0 contract, then extend it for additions in
      later 1.x releases. Cover omitted/null fields, parameter bounds, stable IDs,
      all action choices and rejected unsupported input. Require later 1.x
      candidates to pass all earlier stable contract cases in Python and the browser.
- [ ] **Prove upgrade and recovery.** Use released packages and temporary
      configurations to verify saved JSON, favorites, named profiles, active files
      and both CLI and Library Restore histories. Restore must recover original
      bytes or refuse an external-edit conflict without data loss. Updating the
      package must not activate effects.
- [ ] **Verify configuration boundaries.** Cover stale reviews, changed files,
      symlink retargeting, no-op Apply, write/validation failures and lost or unknown
      runtime capabilities. Document recovery limits, including the absence of a
      multi-file crash-atomicity guarantee, without implying it has been tested away.
- [ ] **Meet the declared support matrix.** Pass release CI, installed wheel and
      source-package checks, Python/browser export parity, stock Niri validation
      and real workflow checks for each adapter claimed stable. Publish scoped
      rendering, capture/input and performance evidence for any native feature
      promoted out of experimental status. List remaining limits accurately.
- [ ] **Prepare a coherent release.** Review the getting-started, upgrade, API and
      support guides against the candidate. Prepare matching signed sources,
      packages, checksums, release notes and migration examples. After approval,
      use the [release process](releasing.md) to sign the tag and publish 1.0 as
      stable only when these gates pass.

## Decisions to settle before the freeze

- Choose how long supported Niri/Python/toolkit versions remain in the 1.x matrix,
  and whether fixes target only the latest 1.x release or also older branches.
  Ending maintenance of an older 1.x binary does not remove compatibility
  obligations for its stable interfaces or documents.
- Decide which reusable picker interfaces and native features are stable in 1.0.
  Record that decision beside each feature, including any separate experimental
  contract version and its update requirements.
- Define a narrow security policy for compatibility. Malformed input and
  unauthorized writes are outside the supported contract. Do not assume a
  security fix permits arbitrary breaking changes; if valid supported use must
  change, publish its impact and migration path under an explicitly agreed policy.

Completing every research epic or reaching a particular preset count is not a
1.0 gate. A useful, tested and maintainable public contract is.
