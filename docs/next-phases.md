# Development design notes

These notes are for contributors changing rendering, controls or shell adapters.
They explain design constraints and the checks needed to preserve existing behavior.
The [project roadmap](../ROADMAP.md) tracks priorities; the
[stability and compatibility policy](stability.md) defines the path to 1.0 and
future public-interface commitments. Current support and observed results are in
[Compatibility](compatibility.md) and [Validation](validation.md).

For installation and customization, start with the [user guides](README.md#install-and-use).

## Rendering and interruptions

A window effect has more state than its visible position: texture geometry,
progress, seed, rotation and direction all contribute to a continuous image.
Retargeting should retain those values where possible. A new random field or a
fully reconstructed snapshot can produce a visible jump even when position is continuous.

The experimental patch carries shader phase through swaps, blends direction
impulses and continues an interrupted opening trajectory while fading out. This
preserves visual state and sampled deformation speed through cubic handoffs.
Interrupted tile and column offsets also retain their sampled position velocity
when a movement shader is configured. Their cubic path ends at the new destination
with zero speed; unchanged moves use Niri's configured curve. Acceleration,
camera motion and shared particle physics remain separate problems. Phase curves
must stay bounded without discarding their incoming speed.

Resize geometry follows the same principle in the experimental movement
renderer. Width and height retain sampled velocity independently; an unchanged
axis keeps its original curve and finish time so neighboring tiles stay on the
same clock. Active size and neighbor paths also retain their existing timing
configuration across a reload; newly moving axes use the new configuration.
Deterministic tests cover reversals, orthogonal retargets, small changes and
client commits that start a stationary axis. The
[native comparisons](validation.md#resize-geometry-continuity) show reversals,
orthogonal retargets and the timing-reload fix. Stock rendering and disabled
resize keep their existing behavior.

Resize geometry and visual material have separate lifetimes. The development
renderer retains the original phase, reference geometry and shader program for
marked NiriFX resize shaders. It composites newly committed content on a separate
clock and applies deformation once to that flat material. Retargeting promotes a
flat composite, never a recursive snapshot or an already deformed image.

Each capture target owns its own bounded cache. A visibility-rule change starts
with current content under the new rule, and renderer recreation discards old
context resources. Unmarked custom shaders keep the stock interface; generated
NiriFX shaders also fall back to stock behavior without the native extension.
See [native material validation](validation.md#retained-material-acceptance-unreleased)
for the tested boundaries.

The closing handoff freezes undeformed material separately for each render target
and detaches the current size trajectories from the mapped tile. Resize is applied
once, before continuing opening or movement and the closing fade. Borders and
shadows are rebuilt at the evolving size; popup/background planes retain their
own placement. Applying resize to the ordinary assembled snapshot would deform
the window twice, so it remains a fallback instead.

All three target captures must succeed before the handoff is enabled. Partial
failure drops the new resources and retains Niri's protected snapshot path.
Frozen textures and pinned programs are released when closing ends, an applicable
animation is disabled or the renderer is replaced. Fullscreen windows and
transitions, and changed output scale, keep the snapshot path until their own
handoffs are defined.

Acceptance compares the last mapped frame with the first closing frame at a fixed
clock, then checks advancing geometry, phase and eventual removal after resuming.
Keep separate Output, Screencast and ScreenCapture controls: capture targets must
never borrow unredacted Output material. Transparent margins, popups, protected
blurred backgrounds, repeated cycles and renderer/allocation failures each need
their own evidence; success on ordinary cards does not establish those boundaries.

The development renderer shares constrained resize displacement per source and
axis. Its path brakes before the minimum size, and affected neighbors follow that
same path. Independent resize contributions remain separate from ordinary swap
offsets; stacked columns follow the maximum visible width. Turning resize off
finishes the shared paths before discarding their source state.

Regression tests cover simultaneous resizes, source removal, swaps, focus changes
and handoffs at the floor, including position and velocity on both sides. Preserve
those tests when changing geometry ownership or timing. Native before/after
comparisons complement the mathematical checks; aligned edges alone do not prove
texture or deformation continuity.

Changes to this path should include deterministic state tests and native recordings
of reversal, repeated retargets, close-during-open, close-during-move and shader
removal. Verify the final layout and disappearance of closed surfaces. Retain
Niri's blocked-out capture paths and ordinary-renderer fallback.

## Pointer-driven deformation

The [pointer prototype](pointer-wobble.md) keeps an analytically integrated spring
on each dragged tile. Input adds velocity; the spring's energy is bounded without
rescaling existing displacement. Release retains the state, and regrabs blend the
anchor while preserving the current deformation. Test these transitions against
different frame cadences and extreme input, then check the real Wayland drag path.
The visual shader must not move input regions or change layout ownership.

## Performance evidence

Use [the GPU harness](performance.md) for shader draw cost. Measure compositor
presentation separately: capture cadence, IPC acknowledgements and WebGL GPU
queries answer different questions. Record the driver, window/output dimensions,
refresh rate, sample count and release/debug build profile with each result.

Publish concise results, limitations, reproducible commands and sanitized measurement
data. Keep local investigation notes, raw logs, source recordings and personal
configuration snapshots under ignored `artifacts/`. The
[recording guide](gifs/README.md) describes how to prepare synthetic public media.

Inverse shader lookups need a coverage bound before reducing their search radius.
Compare intermediate frames, extreme settings and multiple seeds against a
reference renderer. Preserve premultiplied alpha, transparent decorations and
exact endpoints. Particle count alone is not a universal performance control.

## Shell integration contract

Reuse the parameter catalog and CLI rather than reproducing shader math in a
picker. A shell adapter should provide search, editable profiles, deliberate
activation, a dedicated restore state and visible error messages. Use argument
arrays and catalog identifiers instead of interpolating names into shell commands.

Test selection, activation and exact restore with temporary configurations.
Preserve existing resize behavior unless the profile selects resize, keep unrelated
settings, and describe ownership when another animation manager is present.
See [shell integration design](roadmap.md).

## Adding effects and controls

Follow [Adding an effect](adding-effects.md) and [Architecture](architecture.md).
Each distinct effect needs an importable example, a faithful recording and
Python/browser export parity. Family capability metadata determines which actions
are supported; supporting resize never enables it automatically.

Basic Studio controls should be enough to tune the main look. Detailed controls
belong in Advanced view and must retain their values when hidden. Respect reduced
motion in previews and galleries without silently changing exported effects.
