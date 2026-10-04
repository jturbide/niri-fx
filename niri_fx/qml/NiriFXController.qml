// SPDX-License-Identifier: MIT
// A reusable UI-independent adapter. Arguments are arrays; shader generation,
// document validation and conflict-aware writes belong to the Python CLI.
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    property var command: ["niri-fx"]
    property string configPath: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/niri/config.kdl"
    property string statePath: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/niri-fx/quickshell"
    property string startupFile: ""
    property var presets: ({})
    property string query: ""
    property string family: ""
    property string selectedPreset: ""
    property string customPath: ""
    property var customDocument: null
    property var reviewPlan: null
    property bool allowResize: false
    property string undoTransaction: ""
    property string undoStatus: "Checking Undo…"
    property string status: "Loading styles…"
    property string error: ""
    property string operation: ""
    property string requestKey: ""
    property string requestedFile: ""
    property bool processStarted: false
    readonly property bool busy: operation !== ""
    readonly property bool mutating: operation === "apply" || operation === "undo"
    readonly property string selectionKey: JSON.stringify([command, configPath, statePath, selectedPreset, customPath])
    readonly property var selectedDocument: selectedPreset && presets[selectedPreset] ? presets[selectedPreset] : customDocument
    readonly property string selectedName: selectedDocument ? selectedDocument.name : "Choose a style"
    readonly property var actions: selectedDocument ? (selectedDocument.kind === "profile" ? selectedDocument.actions : ({
                open: selectedDocument.effect,
                close: selectedDocument.effect,
                resize: selectedDocument.effect.resize ? selectedDocument.effect : null,
                movement: null
            })) : ({})
    readonly property bool changesResize: !!actions.resize
    readonly property bool canApply: !busy && !!reviewPlan && reviewPlan.changes.length > 0 && (!changesResize || allowResize)
    readonly property var families: [""].concat([...new Set(Object.values(presets).reduce((all, doc) => all.concat(documentFamilies(doc)), []))].sort((a, b) => a === "fragments" ? -1 : b === "fragments" ? 1 : a.localeCompare(b)))
    readonly property var items: {
        let rows = Object.keys(presets).map(id => ({
                    id,
                    name: presets[id].name,
                    families: documentFamilies(presets[id]),
                    comment: presets[id].kind === "profile" ? "Open / close profile" : title(presets[id].effect.family)
                }));
        if (customDocument) {
            const effects = customDocument.kind === "profile" ? Object.values(customDocument.actions).filter(Boolean) : [customDocument.effect];
            rows.unshift({
                id: "custom",
                name: customDocument.name,
                families: [...new Set(effects.map(e => e.family))],
                comment: "Loaded JSON"
            });
        }
        const text = query.toLowerCase().trim();
        return rows.filter(row => (!family || row.families.includes(family)) && (row.id + " " + row.name + " " + row.comment + " " + row.families.join(" ")).toLowerCase().includes(text));
    }
    signal completed(string action, bool success)
    signal studioRequested(var arguments)

    function documentFamilies(doc) {
        const effects = doc.kind === "profile" ? Object.values(doc.actions).filter(Boolean) : [doc.effect];
        return [...new Set(effects.map(effect => effect.family))];
    }
    function title(value) {
        return value.split("-").map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
    }
    function displayPath(value) {
        let text = String(value);
        for (const name of ["XDG_CONFIG_HOME", "XDG_STATE_HOME", "HOME"]) {
            const prefix = Quickshell.env(name);
            if (prefix)
                text = text.split(prefix + "/").join(name === "HOME" ? "~/" : "$" + name + "/");
        }
        return text;
    }
    function invalidateReview() {
        reviewPlan = null;
    }
    onSelectionKeyChanged: invalidateReview()

    function select(id) {
        if (busy)
            return;
        if (id === "custom" && customDocument)
            selectedPreset = "";
        else if (Object.prototype.hasOwnProperty.call(presets, id))
            selectedPreset = id;
        else {
            error = "Unknown style. Refresh the catalog.";
            return;
        }
        reviewPlan = null;
        allowResize = false;
        error = "";
        status = "Selection only. Review changes before applying.";
    }
    function selectionArguments() {
        return selectedPreset ? [selectedDocument.kind === "profile" ? "--profile" : "--preset", selectedPreset] : ["--custom", customPath];
    }
    function setupArguments() {
        return ["setup", "--target", "standalone", "--config", configPath, "--state", statePath, "--no-launcher"].concat(selectionArguments());
    }
    function request(action, args) {
        if (busy)
            return false;
        operation = action;
        requestKey = selectionKey;
        processStarted = false;
        worker.command = command.concat(args);
        worker.running = true;
        return true;
    }
    function reload() {
        if (!busy) {
            invalidateReview();
            error = "";
            status = "Loading styles…";
            request("catalog", ["list", "--documents"]);
        }
    }
    function loadFile(file) {
        if (busy || !file)
            return;
        invalidateReview();
        requestedFile = file;
        error = "";
        status = "Validating JSON…";
        request("inspect", ["inspect", "--custom", file]);
    }
    function loadUrl(url) {
        const value = url.toString();
        if (!value.startsWith("file:///")) {
            error = "Choose a local JSON file.";
            return;
        }
        loadFile(decodeURIComponent(value.slice(7)));
    }
    function review() {
        if (busy || !selectedDocument)
            return;
        error = "";
        reviewPlan = null;
        status = "Checking the selected effect and Niri configuration…";
        request("review", setupArguments());
    }
    function apply() {
        if (!canApply)
            return;
        error = "";
        status = "Applying the reviewed changes…";
        // The fresh Python plan must match this review, including config hashes.
        const args = setupArguments().concat(["--expect-plan", reviewPlan.plan_sha256, "--apply"]);
        request("apply", args);
    }
    function refreshUndo() {
        if (!busy)
            request("history", ["restore", "--state", statePath]);
    }
    function undo() {
        if (busy || !undoTransaction)
            return;
        error = "";
        status = "Restoring previous settings…";
        invalidateReview();
        request("undo", ["restore", "--state", statePath, "--transaction", undoTransaction, "--apply"]);
    }
    function openStudio() {
        if (busy || !selectedDocument)
            return;
        const args = command.concat(["studio", "--target", "standalone"], selectionArguments());
        Quickshell.execDetached(args);
        studioRequested(args);
        status = "Opening Studio for this selection. Previewing does not activate it.";
    }
    function finish(code, message) {
        const action = operation;
        if (!action)
            return;
        operation = "";
        let success = code === 0;
        try {
            if (!success)
                throw new Error(message || "NiriFX command failed.");
            const data = JSON.parse(output.text);
            if (!data || Array.isArray(data) || typeof data !== "object")
                throw new Error("Invalid response from NiriFX.");
            if (action === "catalog") {
                presets = data;
                if (!selectedDocument)
                    select("balanced");
                status = Object.keys(data).length + " styles and profiles available.";
            } else if (action === "inspect") {
                customDocument = data;
                customPath = requestedFile;
                query = "";
                family = "";
                select("custom");
                status = "Loaded " + data.name + ". Nothing has been applied.";
            } else if (action === "review") {
                if (requestKey !== selectionKey)
                    throw new Error("Selection changed. Review it again.");
                if (!/^[0-9a-f]{64}$/.test(data.plan_sha256) || !Array.isArray(data.changes))
                    throw new Error("Update NiriFX to a version with reviewed-plan support.");
                // A file may have changed since import, before this review.
                // Never approve an unseen resize override or stale description.
                const shown = selectedDocument.kind === "profile" ? selectedDocument.actions : selectedDocument.effect;
                if (JSON.stringify(data.effect) !== JSON.stringify(shown)
                    || JSON.stringify(data.desktop_motion || null) !== JSON.stringify(selectedDocument.motion || null))
                    throw new Error("The selection changed since loading. Reload its JSON or refresh the catalog, then review again.");
                reviewPlan = data;
                status = data.changes.length ? "Review ready. Apply activates this selection." : "This selection is already applied; no files need changing.";
            } else if (action === "apply" || action === "undo") {
                invalidateReview();
                status = action === "undo" ? "Previous settings restored exactly." : data.changed ? "Applied " + selectedName + ". Undo restores the previous settings." : "No files changed.";
            } else if (action === "history") {
                undoTransaction = data.transaction;
                undoStatus = "Undo the latest change made by this picker.";
            }
        } catch (problem) {
            success = false;
            const detail = displayPath(problem.message);
            if (action === "history") {
                undoTransaction = "";
                undoStatus = /No setup snapshots|No applied setup snapshot/.test(detail) ? "No picker changes to undo." : "Undo unavailable: " + detail;
            } else {
                error = detail;
                status = "The operation did not complete. Review the error below.";
                invalidateReview();
            }
        }
        completed(action, success);
        if (action === "catalog" && success && startupFile) {
            const file = startupFile;
            startupFile = "";
            Qt.callLater(() => root.loadFile(file));
        } else if (["catalog", "inspect", "apply", "undo"].includes(action)) {
            Qt.callLater(() => root.refreshUndo());
        }
    }
    Process {
        id: worker
        stdout: StdioCollector {
            id: output
        }
        stderr: StdioCollector {
            id: errors
        }
        onStarted: root.processStarted = true
        // Quickshell 0.3.1's type metadata omits QProcess::ExitStatus; runtime
        // supplies it (NormalExit = 0). Keep the crash check as well as the code.
        // qmllint disable signal-handler-parameters
        onExited: (code, exitStatus) => root.finish(code === 0 && exitStatus === 0 ? 0 : 1, errors.text)
        // qmllint enable signal-handler-parameters
    }
    // Failed-to-start does not emit exited on every Quickshell release. Recover
    // without ever terminating an in-flight configuration writer on a timer.
    Timer {
        interval: 1000
        repeat: true
        running: root.busy
        onTriggered: if (!worker.running && !root.processStarted)
            root.finish(1, "Cannot start NiriFX. Check the configured command and executable path.")
    }
    Component.onCompleted: reload()
}
