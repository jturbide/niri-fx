// SPDX-License-Identifier: MIT
// A combo is a snapshot of the document, not an editor action. The planner has
// no DOM or GPU dependencies; its clock can also be driven by a GIF recorder.
function createComboPreview({
  normalizeDocument,
  families,
  render,
  pointerDemo,
  onFinish = () => {},
  requestFrame = (callback) => requestAnimationFrame(callback),
  cancelFrame = (id) => cancelAnimationFrame(id),
  now = () => performance.now(),
}) {
  // Keep spring replay state outside the serializable, immutable timeline.
  const pointerDemos = new WeakMap();
  function freeze(value) {
    if (value && typeof value === "object") {
      for (const child of Object.values(value)) freeze(child);
      Object.freeze(value);
    }
    return value;
  }
  function plan(document, { seed = 0.37, holdMs = 650, reducedMotion = false } = {}) {
    if (!Number.isFinite(seed) || seed < 0 || seed > 1)
      throw new Error("Preview seed must be between zero and one.");
    if (!Number.isFinite(holdMs) || holdMs < 0 || holdMs > 5000)
      throw new Error("Preview hold must be between zero and 5000 ms.");
    const snapshot = structuredClone(normalizeDocument(document));
    const actions =
      snapshot.kind === "profile"
        ? snapshot.actions
        : {
            open: snapshot.effect,
            close: snapshot.effect,
            resize: snapshot.effect.resize ? snapshot.effect : null,
            movement: null,
          };
    const stages = [];
    let totalMs = 0;
    function add(action, direction, fromOffset, toOffset, hold = true) {
      const effect = actions[action];
      if (effect === null || effect === "off") {
        const preserved = effect === null;
        const label =
          action === "movement" ? "Move / swap" : action[0].toUpperCase() + action.slice(1);
        const stage = {
          action,
          mode: "idle",
          effect: null,
          direction,
          fromOffset: toOffset,
          toOffset,
          size: action === "resize" && direction === "grow" ? [800, 440] : [600, 380],
          visible: preserved || action !== "close",
          label: label + (preserved ? " · Preserve" : " · Off"),
          support: preserved
            ? "Underlying desktop or shell animation cannot be previewed without its context"
            : "Instant endpoint; animation disabled" +
              (action === "movement" ? "; stock Niri exports omit movement" : ""),
          actionDurationMs: 0,
          phase: "hold",
          startMs: totalMs,
          durationMs: holdMs,
        };
        stages.push(stage);
        totalMs += stage.durationMs;
        return;
      }
      const mode = ["resize", "movement"].includes(action) ? action : "effect",
        family = families[effect.family];
      if (!family || (mode !== "effect" && !family[mode]))
        throw new Error("This family does not support " + action + ".");
      const durationMs = effect[action + "_ms"];
      if (!Number.isFinite(durationMs) || durationMs <= 0)
        throw new Error("Invalid " + action + " preview duration.");
      const label =
        action === "movement"
          ? "Experimental movement shader preview · " + direction
          : action === "resize"
            ? "Resize · " + direction
            : action === "open"
              ? "Opening"
              : "Closing";
      const support =
        action === "movement"
          ? "Experimental shader preview; stock Niri exports omit movement"
          : action === "resize"
            ? "Stock Niri resize"
            : "Stock Niri open/close";
      const stage = {
        action,
        mode,
        effect,
        direction,
        fromOffset,
        toOffset,
        label: label + " · " + family.label + " · " + durationMs + " ms",
        support,
        actionDurationMs: durationMs,
        phase: "animation",
        startMs: totalMs,
        durationMs: reducedMotion ? 0 : durationMs,
      };
      stages.push(stage);
      totalMs += stage.durationMs;
      if (hold && holdMs) {
        stages.push({ ...stage, phase: "hold", startMs: totalMs, durationMs: holdMs });
        totalMs += holdMs;
      }
    }
    add("open", null, [0, 0], [0, 0]);
    // Paired transitions restore the initial window size and position before
    // closing. They preview only actions explicitly included in this snapshot.
    if (actions.resize) {
      add("resize", "grow", [0, 0], [0, 0]);
      add("resize", "shrink", [0, 0], [0, 0]);
    }
    if (actions.movement) {
      add("movement", "right", [0, 0], [160, 0]);
      add("movement", "left", [160, 0], [0, 0]);
    }
    if (snapshot.kind === "profile" && snapshot.pointer?.strength > 0 && !reducedMotion) {
      if (typeof pointerDemo !== "function") throw new Error("Pointer preview is unavailable.");
      const demo = pointerDemo(snapshot.pointer);
      const stage = {
        action: "pointer",
        mode: "pointer",
        effect: actions.open,
        pointerSettings: snapshot.pointer,
        direction: null,
        fromOffset: [0, 0],
        toOffset: [0, 0],
        label: "Pointer drag preview",
        support: "Native spring and shader math; synthetic input, not compositor validation",
        actionDurationMs: demo.durationMs,
        phase: "animation",
        startMs: totalMs,
        durationMs: demo.durationMs,
      };
      pointerDemos.set(stage, demo);
      stages.push(stage);
      totalMs += stage.durationMs;
    }
    add("close", null, [0, 0], [0, 0], false);
    const preservedActions = Object.entries(actions)
      .filter(([, value]) => value === null)
      .map(([action]) => action);
    return freeze({ document: snapshot, stages, seed, reducedMotion, totalMs, preservedActions });
  }
  function sample(plan, elapsedMs) {
    if (!Number.isFinite(elapsedMs)) throw new Error("Preview timestamp must be finite.");
    elapsedMs = Math.min(plan.totalMs, Math.max(0, elapsedMs));
    const complete = elapsedMs >= plan.totalMs;
    // Empty animation intervals under reduced motion resolve directly to the
    // following hold. At the final boundary, the closing endpoint is transparent.
    const stage =
      plan.stages.find((stage) => elapsedMs < stage.startMs + stage.durationMs) ||
      plan.stages.at(-1);
    const fraction =
      complete || stage.phase === "hold" || !stage.durationMs
        ? 1
        : (elapsedMs - stage.startMs) / stage.durationMs;
    const eased = fraction * fraction * (3 - 2 * fraction);
    let pointer;
    if (stage.action === "pointer") {
      let demo = pointerDemos.get(stage);
      // Serialized plans can be replayed by capture tools, including backwards.
      if (!demo) {
        if (typeof pointerDemo !== "function") throw new Error("Pointer preview is unavailable.");
        demo = pointerDemo(stage.pointerSettings);
        pointerDemos.set(stage, demo);
      }
      pointer = demo.sample(elapsedMs - stage.startMs);
    }
    return {
      action: stage.action,
      mode: stage.mode,
      effect: stage.effect,
      ...(stage.mode === "idle" ? { visible: stage.visible, size: stage.size } : {}),
      direction: stage.direction,
      progress: stage.action === "open" ? 1 - fraction : fraction,
      offset:
        pointer?.offset ||
        stage.fromOffset.map((from, index) => from + (stage.toOffset[index] - from) * eased),
      ...(pointer ? { pointer } : {}),
      seed: plan.seed,
      phase: pointer?.phase || stage.phase,
      label: stage.label,
      support:
        stage.support +
        (plan.preservedActions?.length
          ? " · Preserve: " + plan.preservedActions.join(", ") + "; desktop context required"
          : ""),
      actionDurationMs: stage.actionDurationMs,
      elapsedMs,
      totalMs: plan.totalMs,
      complete,
    };
  }

  let currentPlan = null,
    active = false,
    generation = 0,
    frame = null,
    startedAt = 0;
  function stop() {
    generation++;
    active = false;
    if (frame !== null) cancelFrame(frame);
    frame = null;
  }
  function present(elapsedMs, epoch) {
    if (!active || epoch !== generation) return null;
    const state = sample(currentPlan, elapsedMs);
    render(state);
    // Rendering may trigger a document edit or start a different preview. Never
    // finish or schedule on behalf of that newly selected document.
    if (!active || epoch !== generation) return state;
    if (state.complete) {
      active = false;
      onFinish(state);
    }
    return state;
  }
  function play(document, options = {}) {
    // Validate first so an invalid request does not disturb a running preview.
    const next = plan(document, options);
    stop();
    currentPlan = next;
    active = true;
    startedAt = now();
    const epoch = generation;
    function tick(timestamp) {
      if (!active || epoch !== generation) return;
      frame = null;
      present(timestamp - startedAt, epoch);
      if (active && epoch === generation) frame = requestFrame(tick);
    }
    present(0, epoch);
    if (!options.manual && active && epoch === generation) frame = requestFrame(tick);
    return next;
  }
  function seek(elapsedMs) {
    if (!Number.isFinite(elapsedMs)) throw new Error("Preview timestamp must be finite.");
    if (!active) return null;
    // Capture drives the existing preview through the same render callback.
    // Cancel and invalidate RAF before seeking so late frames cannot fight it.
    generation++;
    if (frame !== null) cancelFrame(frame);
    frame = null;
    return present(elapsedMs, generation);
  }
  return {
    plan,
    sample,
    play,
    seek,
    stop,
    get active() {
      return active;
    },
    get currentPlan() {
      return currentPlan;
    },
  };
}
