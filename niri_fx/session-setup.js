// Package adoption uses the installed tools through the local Studio backend.
// This view never installs packages, selects paths or changes the edited recipe.
function createSessionSetup({ catalog, onApplied }) {
  if (!catalog.connection?.session || catalog.hosted) return null;
  const element = (id) => document.getElementById(id);
  const panel = element("session-setup");
  const states = new Set(["missing", "ready", "update", "current", "blocked", "unavailable"]);
  let snapshot = catalog.connection.session,
    review = null,
    busy = false,
    applied = snapshot.reopen_required === true,
    uncertain = snapshot.apply_uncertain === true;
  const short = (value) => (typeof value === "string" ? value.slice(0, 8) : "unknown");

  function render() {
    const state = states.has(snapshot?.state) ? snapshot.state : "unavailable";
    panel.hidden = false;
    panel.dataset.state = state;
    element("session-setup-title").textContent = applied
      ? uncertain
        ? "Session setup needs checking"
        : "Ready for your next NiriFX login"
      : {
          missing: "Add the NiriFX session",
          ready: "Set up your NiriFX session",
          update: "Update your NiriFX session",
          current: "Your selected session is up to date",
          blocked: "Session setup needs attention",
          unavailable: "Session status is unavailable",
        }[state];
    element("session-setup-detail").textContent = applied
      ? uncertain
        ? "The setup response could not be confirmed. Save or export any edits, then close Studio and reopen it from the NiriFX launcher to check your selection before making more changes. Your current desktop was not restarted."
        : "Your current desktop is still running. Save or export any edits, then close Studio and reopen it from the NiriFX launcher. Log in to NiriFX when you are ready to use the selected compositor."
      : snapshot.detail || "Check again to inspect the installed package and your selection.";
    element("session-installed").textContent = snapshot.installed
      ? `NiriFX ${snapshot.installed.version} · build ${short(snapshot.installed.build_id)}`
      : "Complete package not installed";
    element("session-next-login").textContent = snapshot.next_login
      ? `NiriFX ${snapshot.next_login.tools_version || "tools"} · build ${short(snapshot.next_login.build_id)}`
      : "Not selected";
    element("session-running").textContent =
      snapshot.running?.detail || snapshot.running?.version || "Not verified";
    element("session-config").textContent =
      snapshot.config?.mode === "copy"
        ? `${snapshot.config.detail || "First setup keeps a saved copy; later changes to normal Niri settings are not automatically shared."} Configuration: ${snapshot.config.path || "the configuration selected when Studio opened"}. This Studio draft is not applied.`
        : "Your selected session keeps its saved settings and effects.";
    element("session-config").hidden = !snapshot.can_review || applied;
    element("session-review").hidden = !snapshot.can_review || applied;
    element("session-review").textContent =
      snapshot.action === "update" ? "Review update" : "Review setup";
    for (const id of ["session-review", "session-refresh", "session-apply", "session-cancel"])
      element(id).disabled = busy;
    element("session-apply").disabled ||= !review;
    element("session-plan").hidden = !review;
    element("session-install-guide").hidden = state !== "missing";
  }

  async function post(path, body = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 150000);
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-NiriFX-Token": catalog.connection.token },
        body: JSON.stringify(body),
        cache: "no-store",
        signal: controller.signal,
      });
      const result = await response.json();
      if (!response.ok) {
        const error = new Error(result.error || "The session operation could not finish.");
        error.serverRefusal = true;
        error.reopenRequired = result.reopen_required === true;
        throw error;
      }
      return result;
    } catch (error) {
      if (error.name === "AbortError")
        throw new Error(
          "The request timed out. Check session status before trying again; an update may have finished.",
          { cause: error },
        );
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  async function operation(work) {
    if (busy) return;
    busy = true;
    const focused = document.activeElement;
    element("session-error").textContent = "";
    render();
    try {
      await work();
    } catch (error) {
      review = null;
      if (error.reopenRequired) {
        applied = uncertain = true;
        snapshot = { ...snapshot, reopen_required: true, apply_uncertain: true };
        element("session-result").textContent =
          "Check session setup before making further changes.";
        onApplied({ uncertain: true });
      }
      element("session-error").textContent = error.message;
    } finally {
      busy = false;
      render();
      if (review) {
        element("session-plan").scrollIntoView({ block: "nearest" });
        element("session-apply").focus({ preventScroll: true });
      } else if ([element("session-cancel"), element("session-apply")].includes(focused)) {
        element(applied ? "session-refresh" : "session-review").focus({ preventScroll: true });
      }
    }
  }

  element("session-refresh").onclick = () =>
    operation(async () => {
      if (review) await post("/session-cancel", { expected: review.plan_sha256 });
      review = null;
      const next = await post("/session-status");
      if (!states.has(next?.state))
        throw new Error("The session status response could not be read.");
      snapshot = next;
      if (snapshot.reopen_required) {
        applied = true;
        uncertain = snapshot.apply_uncertain === true;
        onApplied({ uncertain });
      }
      element("session-result").textContent = "Session status checked.";
    });
  element("session-review").onclick = () =>
    operation(async () => {
      const plan = await post("/session-review");
      if (!/^[a-f0-9]{64}$/.test(plan.plan_sha256) || !Array.isArray(plan.changes))
        throw new Error("The session review could not be read. Check status and try again.");
      review = plan;
      element("session-plan-title").textContent =
        plan.intent === "update"
          ? "Select this package update for your next login?"
          : "Set up this package for your next NiriFX login?";
      element("session-plan-summary").textContent =
        `${plan.changes.length} file changes. Your current desktop keeps running. Review the details before applying.`;
      element("session-plan-notes").textContent = (plan.notes || []).join(" ");
      element("session-plan-files").replaceChildren();
      for (const change of plan.changes) {
        const row = document.createElement("li");
        row.textContent = `${change.action || "update"}: ${change.path}`;
        element("session-plan-files").append(row);
      }
      element("session-result").textContent = "Review ready. Nothing has changed yet.";
    });
  element("session-cancel").onclick = () =>
    operation(async () => {
      if (review) await post("/session-cancel", { expected: review.plan_sha256 });
      review = null;
      element("session-result").textContent = "Review cancelled. Nothing changed.";
    });
  element("session-apply").onclick = () =>
    operation(async () => {
      if (!review) throw new Error("Review the session update first.");
      const expected = review.plan_sha256;
      // Never reuse a token after an ambiguous response or a failed transaction.
      review = null;
      let result;
      try {
        result = await post("/session-apply", { expected });
        if (
          result.activation !== "next-login" ||
          result.reopen_required !== true ||
          !states.has(result.session?.state)
        )
          throw new Error(
            "The session setup result could not be confirmed. Check status before continuing.",
          );
      } catch (error) {
        // A lost or malformed success response cannot establish whether Apply
        // finished. Only an explicit refusal can keep this launch writable.
        if (!error.serverRefusal) error.reopenRequired = true;
        throw error;
      }
      snapshot = result.session;
      applied = true;
      uncertain = false;
      element("session-result").textContent =
        "Session selected for next login. Your current desktop was not restarted.";
      onApplied({ uncertain: false });
    });
  render();
  return {
    snapshot: () =>
      structuredClone({ session: snapshot, reviewing: !!review, busy, applied, uncertain }),
  };
}
