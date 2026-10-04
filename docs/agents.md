# Use NiriFX with an AI agent

NiriFX's CLI gives agents the same presets, validation, exports and reversible
setup used by the app. An agent can choose a finished look, build a combo, explain
its settings and apply an authorized change without editing shader code or
guessing which configuration file to replace.

The agent commands and bundled skill are included in **version 0.18 and newer**.
Use the installed `niri-fx` command, or replace it below with `python3 -m niri_fx`
when working from a source checkout.

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
