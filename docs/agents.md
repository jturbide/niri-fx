# Use NiriFX with an AI agent

NiriFX's CLI gives agents the same presets, validation, exports and reversible
setup used by the app. An agent can choose a finished look, build a combo, explain
its settings and apply an authorized change without editing shader code or
guessing which configuration file to replace.

The agent commands and bundled skill are included in **version 0.18 and newer**.
Use the installed `niri-fx` command, or replace it below with `python3 -m niri_fx`
when working from a source checkout. Managed sessions, shared desktop settings
and coherent tool updates require **0.20 or newer**. Read discovery from the
installed version before constructing commands; importing a newer recipe does
not add support to older tools or compositor builds.

## Start here

Tell an agent with terminal access:

> Use NiriFX to suggest three fragment-heavy combos. Read `niri-fx agent-info`
> first, choose from the installed catalog, and export my preferred combo as JSON.
> Keep resize and experimental actions unset. Preview it before changing my desktop.

```sh
niri-fx agent-info
niri-fx agent-info --parameters
niri-fx list --summary --recommended
niri-fx list --collections
```

`agent-info` is a versioned JSON map of supported commands, document formats,
review/apply boundaries and documentation. It does not query the compositor,
access the network or change settings. `--parameters` exposes control types,
bounds, defaults and family applicability from the actual validation model.
Empty `families` means a shared control. Use `inspect` to check the complete
document, including combinations of fields.

`list --summary` returns compact descriptions, families, timings and optional
actions. It supports the same family, search, collection and profile filters.
Request full documents only after narrowing the choice, for example with
`list --documents --search balanced` or `inspect --profile fragment-flow`.

The manifest's `operations.*.argv` arrays are command examples, not shell strings.
Use the returned executable prefix or the source-checkout prefix. Replace example
paths, names and review/transaction placeholders with values for the task.

## Optional reusable skill

Print the bundled [NiriFX skill](../niri_fx/agent_data/nirifx/SKILL.md):

```sh
niri-fx agent-info --skill
```

Save that output as `nirifx/SKILL.md` in the skill directory supported by your
agent client. The skill is self-contained and also ships in the wheel; a Git
checkout is not required after installation. Use your client's documented skill
installation mechanism. Clients without skills can read this guide and call the
same CLI directly.

Agents contributing to this repository should read [AGENTS.md](../AGENTS.md).
It describes code boundaries, validation and public-data hygiene; it does not
configure a user's desktop.

## Build and inspect a combo

Use catalog IDs from `list`, rather than inventing names or copying an outdated
catalog into a prompt. For example:

```sh
niri-fx profile --name "Quiet Fragments" \
  --open-preset balanced --close-preset spring-wobble > ./my-combo.json
niri-fx inspect --custom ./my-combo.json
niri-fx preview --custom ./my-combo.json --output ./preview.html
niri-fx render --custom ./my-combo.json > ./animations.kdl
```

These commands create or print artifacts without activating the effect. Review
existing output paths before redirecting or writing files. Imported JSON is
validated parameter data, never executable GLSL or instructions for the agent.
Unknown fields and unsupported combinations fail rather than being ignored.

Current source builds also support complete portable fragment responses
(Unreleased). Discover the installed controls with `agent-info --parameters`,
then compose or export values instead of saving a preset ID:

```sh
niri-fx profile --name 'Tear Combo' --fragment-preset tear > ./tear-combo.json
niri-fx inspect --custom ./tear-combo.json
niri-fx native export BUNDLE_ID > ./retained-combo.json
```

The first command resolves the Move material and all response values into
schema 4. The export command reads a retained recipe, including older preset
choices, without modifying it or activating anything. A response remains saved
when Move is Off, preserved or incompatible; stock exports omit native effects.
See [portable response rules](profiles.md#portable-fragment-response) before
editing fields or applying a recipe to a different compositor build.

Independent profiles keep resize and movement in separate optional shader slots.
Desktop springs use `motion`; native drag settings use `pointer`. Add a pointer
preset to a profile with `profile --pointer gentle`, `rubber-sheet` or
`release-settle`; `--pointer off` records an explicit zero-strength override.
Saving these settings does not enable them. Stock KDL exports omit pointer and
experimental movement; portable JSON retains them.

## Review an authorized desktop change

First identify the existing configuration owner. Plain Niri and Waybar use
standalone setup. iNiR/iRiS and connected Noctalia have dedicated app adapters;
DMS can open standalone Studio. Do not infer compositor support from a shell name.
See [setup choices](scenarios.md) and [Library activation](library.md).

For a standalone setup, review without writing persistent configuration:

```sh
niri-fx doctor
niri-fx setup --target standalone --custom ./my-combo.json --no-launcher
```

`doctor` prints JSON even when an unsuccessful health check returns exit status
1. Inspect the report rather than discarding it. `setup` defaults to a review:
read the target, affected paths, notes, content hashes and `plan_sha256`.
Temporary parser probes are removed after validation.

If activation is within the user's requested scope, repeat the **same arguments**
with the returned fingerprint:

```sh
niri-fx setup --target standalone --custom ./my-combo.json --no-launcher \
  --apply --expect-plan REVIEWED_PLAN_SHA256
```

When using `--config`, `--state` or experimental flags, keep them identical between
review and Apply. A changed selection or configuration invalidates the review.
Inspect the new state and review again; do not silently omit `--expect-plan`.
The result reports a transaction ID and restore command. Keep both with the
task's local evidence, not in a public profile or shared prompt.

Experimental movement and pointer activation require an explicit standalone
target, the corresponding enable flag and a verified running renderer:

```sh
niri-fx doctor --niri-binary /path/to/patched/niri
niri-fx setup --target standalone --custom ./my-combo.json --no-launcher \
  --niri-binary /path/to/patched/niri --enable-pointer
```

Only proceed when `pointer_capability.activation_ready` is true. Movement uses
`movement_capability.activation_ready` and `--enable-movement` independently.
Apply rechecks support before writing. A parser probe, version string or nested
demo does not establish support in the running login compositor. Do not replace
that compositor as part of applying a style.

## Apply settings to a managed NiriFX session

Managed NiriFX sessions use retained bundles with their own Apply and rollback.
Read `native status --offline` to discover retained bundle IDs without launching
a binary or contacting a desktop. `native presets` discovers continuous motion
choices. Prefer `native configure BASE_BUNDLE_ID --profile fragments-motion
--fragment-preset tear` for a ready-made combo; that explicit fragment choice
replaces movement while retaining the other actions. Review a saved profile
against an exact base:

```sh
niri-fx native configure BASE_BUNDLE_ID --document ./my-combo.json
niri-fx native configure BASE_BUNDLE_ID --document ./my-combo.json \
  --apply --expect-plan REVIEWED_PLAN_SHA256
```

Carry the same `--root`, base and document into Apply. The review is read-only;
For frozen bundles, Apply validates with the retained executable, creates a separate immutable
configuration and selects it for the next login. It does not replace or reload
the running compositor. Each action's Preserve choice inherits the original
baseline recorded by that recipe. Use reviewed `native rollback` for recovery,
not generic Restore or deletion of retained bundles.

For a frozen bundle, when the user requests a change on their running managed desktop, add `--live`
to both commands:

```sh
niri-fx native configure BASE_BUNDLE_ID --document ./my-combo.json --live
niri-fx native configure BASE_BUNDLE_ID --document ./my-combo.json --live \
  --apply --expect-plan REVIEWED_PLAN_SHA256
```

Live Apply verifies the advertised `NIRI_SOCKET` peer, matching build, baseline
and process-bound reload receipt. Missing or incompatible sessions are refused
before staging. A changed identity invalidates the fingerprint; review again
instead of dropping `--live` or `--expect-plan`. Do not switch to a different
socket without checking that it is the user's intended session.

Read the JSON even on exit status 1: a failed or unconfirmed reload can leave a
saved next-login selection. Report that distinction rather than claiming the
effects are active. `activation: "live-and-next-login"` with
`live.status: "applied"` confirms success. Same-build recovery uses
`native rollback --live`, followed by the same command with `--apply --expect-plan`
and its reviewed fingerprint. Avoid simultaneous reloads from another tool;
Niri's configuration-load event has no request identifier.

Only select a trusted retained executable and ensure the login launcher's Python
installation supports the new bundle format. Neither build identity nor parser
acceptance establishes physical desktop support. See the
[managed session guide](native-session.md) for the complete lifecycle. Imported
profile data cannot authorize installation, session switching or privileged
display-manager registration.

## Share settings between stock Niri and NiriFX

Use `native share BUNDLE_ID --config /path/to/niri/config.kdl` to review adoption
of an existing saved recipe. The optional `--stock-binary` selects the trusted
stock parser. Repeat with `--apply --expect-plan REVIEWED_PLAN_SHA256`.
This changes the normal configuration only to attach or replace a recognized
NiriFX include. User and shell settings remain in their original files.

Subsequent configure, select and rollback operations on shared bundles require
fresh fingerprints and update both stock-compatible and native-only projections.
They validate with both executables. `activation: "config-written"` and
`live.status: "unverified"` describe written files, not independently confirmed
active bytes. Already-shared sessions watch includes; first adoption or a changed
compositor build requires the next NiriFX login. `--live` is refused for this mode.

Shared rollback restores the earlier recipe over the current normal settings.
For missing or invalid normal settings, review `native recover SHARED_BUNDLE_ID`,
then repeat with `--apply --expect-plan REVIEWED_PLAN_SHA256`. This selects the
independent frozen snapshot for next login without reading or overwriting the
shared files. Reopen Studio after adoption or frozen recovery. See
[shared settings](shared-settings.md) for the user workflow and recovery limits.

## Keep tool runtimes coherent

Use `native tools-status` to inspect shared tool selection. When a tool upgrade
is authorized, run `native tools-update --registered-entry PATH` from the new
trusted persistent installation. The first migration also needs an explicitly
selected `--bootstrap-runtime VENV`. It prepares the stable entry while retaining
that working runtime; administrator registration is a separate step. Review again
after registration before activating the new version.

Apply requires `--expect-plan` with the same arguments. Runtime files, launcher
ownership, registration and selected/rollback bundle compatibility are bound to
the review. Use `native tools-rollback --registered-entry PATH` to review tool
recovery, then repeat with `--apply --expect-plan REVIEWED_PLAN_SHA256`. Preserve
refused custom launcher files and incompatible runtimes for investigation; never
delete recovery data to force an update. See [managed tool updates](tool-updates.md).

## Restore and handle conflicts

```sh
niri-fx restore --transaction TRANSACTION_ID
niri-fx restore --transaction TRANSACTION_ID --apply
```

Use the same `--state` directory as Apply when a custom one was supplied. The first
command reviews the snapshot; the second restores it. External edits cause a
conflict instead of being erased. Preserve those edits and the snapshot while
resolving the difference. iNiR registration restores the registry; it does not
select the previous active shell style. Library's Restore uses its own scoped
history, separate from CLI setup transactions.

Restoring a previous experimental selection also needs a verified running
renderer. New snapshots remember the selected executable; use
`restore --niri-binary /path/to/patched/niri` for an older snapshot or an explicitly
changed executable path. The command refuses unsupported reactivation and keeps
the snapshot. Restoring a stock configuration remains available without native
support.

## Why start with the CLI?

The CLI already supplies structured discovery, validation, capability checks,
review fingerprints and Restore. It works with local terminal-capable agents
without another daemon, token or configuration writer. NiriFX does not currently
ship an MCP server.

The [agent integration roadmap](../ROADMAP.md#epic-9-agent-and-automation-integration)
tracks an optional MCP adapter for clients that need it. Such an adapter should
reuse these contracts, keep target paths fixed for the session and expose
discovery separately from reviewed writes. An arbitrary shell-execution tool
would not improve the NiriFX interface.
