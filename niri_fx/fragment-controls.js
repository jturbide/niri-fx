// Interaction owns a temporary canvas view. The portable recipe and editor
// history stay unchanged through demos, pointer cancellation and view changes.
function createFragmentPreviewControls({
  getDocument,
  canvas,
  texture,
  stopOther,
  restore,
  reportError,
  eligible,
}) {
  const element = (id) => document.getElementById(id);
  const size = [600, 380];
  let view = null,
    motion = null,
    renderer = null,
    raf = 0,
    pointer = null,
    last = null,
    offset = [0, 0],
    demo = null,
    lastSample = null;
  const reduced = () => element("reduced-motion").checked;
  const visibleIds = [
    "stage",
    "motion-stage",
    "concept-note",
    "effect-playback-controls",
    "caption",
    "combo-preview-status",
  ];

  function releaseCapture() {
    const id = pointer;
    pointer = null;
    last = null;
    if (id !== null && canvas.hasPointerCapture(id)) canvas.releasePointerCapture(id);
  }
  function stop() {
    if (!view) return;
    cancelAnimationFrame(raf);
    raf = 0;
    releaseCapture();
    renderer?.destroy();
    renderer = motion = demo = null;
    for (const [id, hidden] of Object.entries(view.visibility)) element(id).hidden = hidden;
    for (const [tab, pressed] of view.tabs) tab.setAttribute("aria-pressed", pressed);
    view = null;
    canvas.hidden = element("fragment-preview-tools").hidden = true;
    element("try-fragments").textContent = "Try fragment dragging";
    element("try-fragments").setAttribute("aria-pressed", "false");
    delete document.documentElement.dataset.fragmentPreview;
    restore();
  }
  function paint(state, phase) {
    lastSample = state;
    renderer.draw(state, { offset });
    document.documentElement.dataset.fragmentPreview = phase;
    canvas.style.cursor = pointer === null ? "grab" : "grabbing";
    element("fragment-preview-status").textContent = reduced()
      ? "Reduced motion: direct movement without breakup or settling."
      : phase === "demo"
        ? "Grab, hold, move, reverse and release. Reset position to drag it yourself."
        : phase === "dragging"
          ? "Hold still to see the pieces catch up, or reverse direction."
          : phase === "settling"
            ? "Released. The pieces are reconstructing at the new position."
            : "Grab anywhere on the sample window and move it. Nearby pieces follow first.";
  }
  function tick(now) {
    raf = 0;
    if (!view) return;
    try {
      if (demo) {
        const elapsed = Math.min(demo.value.durationMs, now - demo.started);
        const state = demo.value.sample(elapsed);
        offset = [...state.target];
        paint(state, "demo");
        if (elapsed < demo.value.durationMs) raf = requestAnimationFrame(tick);
        else {
          demo = null;
          // A finished demo becomes an ordinary resting interactive window.
          motion = createFragmentMotion(view.settings, { ...view.geometry, nowMs: now });
          paint(motion.sample(now), "ready");
        }
      } else {
        const state = motion.sample(now);
        paint(state, pointer !== null ? "dragging" : state.moving ? "settling" : "ready");
        if (state.moving && !reduced()) raf = requestAnimationFrame(tick);
      }
    } catch (error) {
      stop();
      reportError("Cannot preview fragment dragging: " + error.message);
    }
  }
  function advance(now = performance.now()) {
    cancelAnimationFrame(raf);
    tick(now);
  }
  function reset() {
    if (!view) return;
    cancelAnimationFrame(raf);
    releaseCapture();
    demo = null;
    offset = [0, 0];
    view.grabbed = false;
    const now = performance.now();
    motion = createFragmentMotion(view.settings, { ...view.geometry, nowMs: now });
    advance(now);
  }
  function play() {
    if (!view) return;
    reset();
    if (reduced()) return;
    demo = { value: createFragmentDemo(view.settings, view.geometry), started: performance.now() };
    advance(demo.started);
  }
  function start(playDemo = false) {
    const doc = getDocument();
    if (!doc.fragment_motion || !eligible(doc.actions?.movement)) return false;
    stop();
    stopOther();
    view = {
      settings: structuredClone(doc.fragment_motion),
      geometry: {
        size,
        particles: doc.actions.movement.particles,
        tile: doc.actions.movement.tile_size,
      },
      visibility: Object.fromEntries(visibleIds.map((id) => [id, element(id).hidden])),
      tabs: [...document.querySelectorAll("[data-mode]")].map((tab) => [
        tab,
        tab.getAttribute("aria-pressed"),
      ]),
    };
    try {
      renderer = createFragmentRenderer(canvas, texture);
      for (const id of visibleIds) element(id).hidden = true;
      for (const [tab] of view.tabs) tab.setAttribute("aria-pressed", "false");
      canvas.hidden = element("fragment-preview-tools").hidden = false;
      element("try-fragments").textContent = "Stop fragment preview";
      element("try-fragments").setAttribute("aria-pressed", "true");
      reset();
      if (view && playDemo) play();
      if (view) canvas.focus({ preventScroll: true });
      return !!view;
    } catch (error) {
      stop();
      reportError("Cannot preview fragment dragging: " + error.message);
      return false;
    }
  }
  function point(event) {
    const rect = canvas.getBoundingClientRect();
    const scale = Math.min(canvas.clientWidth / canvas.width, canvas.clientHeight / canvas.height);
    return [
      (event.clientX -
        rect.left -
        canvas.clientLeft -
        (canvas.clientWidth - canvas.width * scale) / 2) /
        scale,
      (event.clientY -
        rect.top -
        canvas.clientTop -
        (canvas.clientHeight - canvas.height * scale) / 2) /
        scale,
    ];
  }
  element("try-fragments").onclick = () => (view ? stop() : start());
  element("fragment-demo").onclick = play;
  element("fragment-reset").onclick = reset;
  element("fragment-stop").onclick = stop;
  canvas.addEventListener("pointerdown", (event) => {
    if (!view || demo || pointer !== null || event.button !== 0 || !event.isPrimary) return;
    const p = point(event);
    const anchor = p.map(
      (value, axis) =>
        (value - ((axis ? canvas.height : canvas.width) - size[axis]) / 2 - offset[axis]) /
        size[axis],
    );
    if (anchor.some((value) => value < 0 || value > 1)) return;
    event.preventDefault();
    pointer = event.pointerId;
    last = p;
    canvas.setPointerCapture(pointer);
    const now = performance.now();
    if (!reduced()) {
      const previous = motion.sample(now);
      // Niri creates a new episode at the actual first grab and retires it once
      // released motion settles. Only an active regrab retains the old pin field.
      if (!view.grabbed || (previous.released && !previous.moving))
        motion = createFragmentMotion(view.settings, {
          ...view.geometry,
          anchor,
          nowMs: now,
        });
      motion.grab(anchor, now);
      view.grabbed = true;
    }
    advance(now);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!view || pointer !== event.pointerId) return;
    event.preventDefault();
    const p = point(event);
    const next = offset.map((value, axis) => {
      const limit = Math.max(0, ((axis ? canvas.height : canvas.width) - size[axis]) / 2 - 36);
      return Math.max(-limit, Math.min(limit, value + p[axis] - last[axis]));
    });
    const delta = next.map((value, axis) => value - offset[axis]);
    last = p;
    offset = next;
    const now = performance.now();
    if (!reduced()) motion.push(delta, now);
    advance(now);
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!view || pointer !== event.pointerId) return;
    releaseCapture();
    const now = performance.now();
    if (!reduced()) motion.release(now);
    advance(now);
  });
  for (const type of ["pointercancel", "lostpointercapture"])
    canvas.addEventListener(type, (event) => {
      if (pointer === event.pointerId) stop();
    });
  canvas.addEventListener("keydown", (event) => {
    if (!view || !["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    play();
  });
  canvas.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    stop();
    reportError(
      "Fragment preview graphics were interrupted. Try the preview again after recovery.",
    );
  });
  document.addEventListener("keydown", (event) => {
    if (view && event.key === "Escape") {
      event.preventDefault();
      stop();
      element("try-fragments").focus();
    }
  });
  for (const type of ["click", "input", "change"])
    document.addEventListener(
      type,
      (event) => {
        if (
          !view ||
          !(event.target instanceof Element) ||
          event.target.closest(
            "#try-fragments,#fragment-preview-tools,#fragment-stage,#reduced-motion",
          ) ||
          !event.target.closest("button,input,select")
        )
          return;
        stop();
      },
      true,
    );
  element("reduced-motion").addEventListener("change", reset);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
  });
  addEventListener("blur", stop);
  addEventListener("resize", stop);
  return {
    start,
    stop,
    snapshot: () =>
      structuredClone({
        active: !!view,
        captured: pointer !== null,
        scheduled: !!raf,
        demo: !!demo,
        offset,
        frame: lastSample,
      }),
  };
}
