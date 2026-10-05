// Use translucent textures to catch source gaps, duplicate ownership and bad bounds.
import assert from "node:assert/strict";
import { renderShape } from "./shape-checks.mjs";

export async function checkMotion(evaluate, setProgress, sample, callFunction) {
  const started = performance.now();
  await evaluate(`window.niriFxMotionProbe=${renderShape.toString()}`);
  const before = await evaluate(
    '({document:effectDocument(),preset:byId("preset").value,resizeDirection:byId("resize-direction").value,movementDirection:byId("movement-direction").value})',
  );
  const probe = (effect, options = {}, moving = false, wide = false) =>
    callFunction(
      String.raw`function(effect, options, moving, wide) {
        let source = shaderFor({...catalog.defaults, ...effect}, false, !moving, moving);
        if (wide) source = source.replace(
          /for \(int ([xy]) = -(\d+); \1 <= \2; \1\+\+\)/g,
          (_, axis, radius) => 'for (int ' + axis + ' = -' + (+radius + 3) + '; '
            + axis + ' <= ' + (+radius + 3) + '; ' + axis + '++)'
        );
        return window.niriFxMotionProbe(source, {
          entry: moving ? 'move_color' : 'resize_color', ...options
        });
      }`,
      [effect, options, moving, wide],
    );
  // A retained material is sampled in current geometry. New client endpoints
  // must not repartition pieces or reverse deformation at the same phase. This
  // checks the generated native branch, not compositor cache/privacy ownership.
  const retainedResize = {
    active: true,
    size: [192, 144],
    from: [144, 96],
    to: [192, 144],
  };
  for (const style of [
    { family: "fragments" },
    { family: "fragments", fragment_shape: "triangle", fragment_orientation: 37 },
    { family: "fragments", fragment_shape: "hexagon", resize_mode: "edge" },
    { family: "slices", slice_angle: 37 },
    { family: "elastic", elastic_frequency: 1, elastic_damping: 0, elastic_strength: 1 },
    { family: "distortion", distortion_resize_mode: "ripple" },
    { family: "distortion", distortion_resize_mode: "edge-ripple" },
    { family: "distortion", distortion_resize_mode: "torsion" },
  ]) {
    const effect = { ...style, resize_strength: 0.9, particles: 120 };
    const options = { progress: 0.25, retainedResize };
    const material = await probe(effect, options);
    assert.equal(material.error, 0);
    assert(
      material.occupied > 0 && material.occupied <= 144 * 96,
      `${style.family}: retained material stays in bounds`,
    );
    assert.equal(
      (await probe(effect, { ...options, alphaValue: 0 })).occupied,
      0,
      `${style.family}: retained transparent content stays transparent`,
    );
    assert.deepEqual(
      await probe(effect, { ...options, from: [220, 32], to: [48, 160] }),
      material,
      `${style.family}: incoming client sizes do not reset the retained material`,
    );
    assert.notEqual(
      (await probe(effect, { ...options, progress: 0.5 })).hash,
      material.hash,
      `${style.family}: retained deformation continues advancing`,
    );
    assert.deepEqual(
      await probe(effect, { ...options, retainedResize: { ...retainedResize, active: false } }),
      await probe(effect, { progress: options.progress }),
      `${style.family}: inactive native state matches stock rendering`,
    );
    const uninterrupted = {
      progress: 0.25,
      width: 120,
      height: 90,
      from: [96, 72],
      to: [192, 144],
    };
    const retainedFirst = {
      ...uninterrupted,
      retainedResize: { ...retainedResize, from: uninterrupted.from },
    };
    const firstImage = await probe(effect, retainedFirst);
    const stockImage = await probe(effect, uninterrupted);
    if (firstImage.hash !== stockImage.hash) {
      const a = (await probe(effect, { ...retainedFirst, includePixels: true })).pixels;
      const b = (await probe(effect, { ...uninterrupted, includePixels: true })).pixels;
      // Separate shader programs can round a sample differently. Permit one
      // 8-bit channel step, as in the search-bound comparison below; coverage
      // and alpha totals must still match exactly, and larger changes fail.
      let worst = 0;
      for (let i = 0; i < a.length; i++) worst = Math.max(worst, Math.abs(a[i] - b[i]));
      assert(worst <= 1, `${style.family}: uninterrupted material differs by ${worst}`);
    }
    assert.deepEqual(
      { ...firstImage, hash: 0 },
      { ...stockImage, hash: 0 },
      `${style.family}/${style.distortion_resize_mode || "default"}: the first uninterrupted resize retains its stock appearance`,
    );
  }
  for (const shape of [
    "square",
    "rectangle",
    "triangle",
    "circle",
    "ellipse",
    "hexagon",
    "diamond",
    "star",
  ]) {
    for (const aspect of [0.25, 1, 4]) {
      const effect = {
        fragment_shape: shape,
        fragment_aspect: aspect,
        fragment_orientation: 37,
        particles: 120,
        resize_strength: 0.7,
        spin: 270,
        size_variation: 0.5,
        fragment_shrink: 0.3,
      };
      const intact = await probe(effect);
      const joined = await probe(effect, { progress: 0.000001 });
      assert.equal(intact.occupied, 144 * 96);
      assert.equal(joined.occupied, intact.occupied, `${shape} ${aspect}: joined resize source`);
      assert.equal(joined.overlap, 0, `${shape} ${aspect}: one translucent source owner`);
      assert.equal(joined.alpha, intact.alpha);
      for (const mode of ["full", "edge", "soft"]) {
        effect.resize_mode = mode;
        const middle = await probe(effect, { progress: 0.5 });
        assert.equal(middle.error, 0);
        assert(
          middle.alpha > 0 && middle.alpha <= intact.alpha,
          `${shape} ${mode}: bounded visible resize`,
        );
        const reference = await probe(effect, { progress: 0.5 }, false, true);
        assert.equal(reference.occupied, middle.occupied, "search preserves occupied pixels");
        assert.equal(reference.overlap, middle.overlap, "search preserves source ownership");
        assert.equal(reference.error, 0);
        if (reference.hash !== middle.hash) {
          // Different loop bounds can change hardware compiler rounding. Check
          // every channel, allowing only one 8-bit quantization step, not gaps.
          const options = { progress: 0.5, includePixels: true };
          const actualPixels = (await probe(effect, options)).pixels;
          const referencePixels = (await probe(effect, options, false, true)).pixels;
          assert.equal(actualPixels.length, referencePixels.length);
          let worst = 0;
          for (let i = 0; i < actualPixels.length; i++)
            worst = Math.max(worst, Math.abs(actualPixels[i] - referencePixels[i]));
          assert(
            worst <= 1,
            `${shape} ${aspect} ${mode}: conservative search bound, max difference ${worst}`,
          );
        }
        assert.deepEqual(await probe(effect, { progress: 0.5 }), middle, "deterministic replay");
      }
      assert.deepEqual(
        await probe({ ...effect, resize_strength: 0 }, { progress: 0.5 }),
        intact,
        "zero strength is intact",
      );
      assert.deepEqual(await probe(effect, { progress: 1 }), intact, "exact endpoint");
      assert.equal(
        (await probe(effect, { progress: 0.5, alphaValue: 0 })).occupied,
        0,
        "transparent source stays transparent",
      );
    }
  }
  for (const shape of ["triangle", "hexagon", "circle"]) {
    const effect = {
      fragment_shape: shape,
      fragment_orientation: 37,
      resize_strength: 0.7,
      particles: 120,
    };
    for (const [width, height, to] of [
      [48, 176, [208, 24]],
      [208, 24, [48, 176]],
      [6, 4, [192, 144]],
    ]) {
      const options = { width, height, to, from: [width, height] };
      const intact = await probe(effect, options);
      assert.equal(intact.occupied, width * height, "extreme window endpoint coverage");
      assert.deepEqual(await probe(effect, { ...options, progress: 1 }), intact);
      const middle = await probe(effect, { ...options, progress: 0.5 });
      assert.equal(middle.error, 0);
      assert(middle.occupied > 0 && middle.occupied <= width * height);
    }
  }
  const studioHash = () =>
    evaluate(
      `(()=>{const gl=byId('stage').getContext('webgl'),pixels=new Uint8Array(1000*760*4);gl.finish();gl.readPixels(0,0,1000,760,gl.RGBA,gl.UNSIGNED_BYTE,pixels);let hash=2166136261;for(const value of pixels)hash=Math.imul(hash^value,16777619);return hash;})()`,
    );
  for (const shape of ["triangle", "hexagon", "circle"]) {
    await evaluate(
      `loadDocument(normalizePreset({schema:3,name:'Resize textures',effect:{fragment_shape:'${shape}',resize_mode:'edge',resize_strength:.6}}));populate();document.querySelector('[data-mode=resize]').click()`,
    );
    const ends = {};
    for (const direction of ["grow", "shrink"]) {
      await evaluate(
        `byId('resize-direction').value='${direction}';byId('resize-direction').dispatchEvent(new Event('change'))`,
      );
      for (const p of [0, 0.25, 0.5, 0.75, 1]) {
        await setProgress(p);
        const pixels = await sample();
        assert.equal(pixels.error, 0);
        assert(pixels.occupied > 0);
        if (p === 0 || p === 1) ends[direction + p] = await studioHash();
      }
    }
    assert.equal(ends.grow0, ends.shrink1, "small texture restored exactly");
    assert.equal(ends.grow1, ends.shrink0, "large texture restored exactly");
    assert.notEqual(ends.grow0, ends.grow1, "old and new textures really differ");
    assert.equal(
      await evaluate("parameters.resize"),
      false,
      "shape selection does not activate resize",
    );
    for (const field of [
      "scatter",
      "dispersion",
      "wave_strength",
      "wave_frequency",
      "wave_speed",
      "direction_variation",
      "gravity_strength",
    ])
      assert.equal(
        await evaluate(`byId('${field}').disabled`),
        true,
        field + " has no resize effect",
      );
  }
  for (const preset of ["fragment-wake", "ribbon-transfer", "momentum-glide"]) {
    await evaluate(
      `byId('preset').value='${preset}';byId('preset').dispatchEvent(new Event('change'));document.querySelector('[data-mode=movement]').click()`,
    );
    const effect = await evaluate("parameters");
    const intact = await probe(effect, {}, true);
    assert.equal(intact.occupied, 144 * 96);
    assert.deepEqual(
      await probe(effect, { progress: 1 }, true),
      intact,
      "movement ends intact at destination",
    );
    assert.deepEqual(
      await probe({ ...effect, movement_strength: 0 }, { progress: 0.5 }, true),
      intact,
      "zero intensity preserves source",
    );
    const images = new Set();
    for (const impulse of [
      [1, 0],
      [-1, 0],
      [0, 1],
      [0, -1],
    ]) {
      const frame = await probe(effect, { progress: 0.37, impulse }, true);
      assert.equal(frame.error, 0);
      images.add(frame.hash);
    }
    assert.equal(images.size, 4, `${preset}: four distinct directions`);
    for (const p of [0, 0.5, 1]) {
      await setProgress(p);
      assert.equal((await sample()).error, 0);
    }
  }
  // A movement slot is explicit, independently editable and JSON-only.
  await evaluate(
    "byId('independent').checked=true;byId('independent').dispatchEvent(new Event('change'));byId('action').value='movement';byId('action').dispatchEvent(new Event('change'))",
  );
  assert.equal(
    await evaluate("effectDocument().actions.movement"),
    null,
    "viewing movement never enables it",
  );
  await evaluate(
    "byId('action-mode').value='style';byId('action-mode').dispatchEvent(new Event('change'));byId('preset').value='fragment-wake';byId('preset').dispatchEvent(new Event('change'))",
  );
  const document = await evaluate("effectDocument()");
  assert.equal(document.actions.movement.movement_focus, 1);
  assert.equal(document.actions.resize, null);
  assert.equal(document.actions.open.family, "elastic");
  assert(
    !(await evaluate("kdlDocument().includes('window-movement')")),
    "stock export excludes native movement",
  );
  assert.deepEqual(
    await callFunction("function(document) { return normalizePreset(document); }", [document]),
    document,
  );
  await evaluate(
    "byId('movement_ms').value=1200;byId('movement_ms').dispatchEvent(new Event('input'));byId('undo').click()",
  );
  assert.equal(await evaluate("effectDocument().actions.movement.movement_ms"), 850);
  await evaluate("byId('redo').click()");
  assert.equal(await evaluate("effectDocument().actions.movement.movement_ms"), 1200);
  await evaluate(
    "byId('action-mode').value='preserve';byId('action-mode').dispatchEvent(new Event('change'))",
  );
  assert.equal(await evaluate("effectDocument().actions.movement"), null);
  await callFunction(
    `function(before) {
      loadDocument(before.document);
      byId('preset').value = before.preset;
      byId('resize-direction').value = before.resizeDirection;
      byId('movement-direction').value = before.movementDirection;
      populate();
      document.querySelector('[data-mode=effect]').click();
      refresh();
      window.niriFxMotionProbe.context.getExtension('WEBGL_lose_context')?.loseContext();
      delete window.niriFxMotionProbe;
    }`,
    [before],
  );
  console.log(
    `PASS: retained resize references, phase advancement and stock fallback; shaped resize ownership, bounds, endpoints, eight silhouettes; directional movement and independent JSON-only editing (${Math.round(performance.now() - started)} ms)`,
  );
}
