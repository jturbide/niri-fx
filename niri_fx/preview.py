"""Assemble a self-contained offline Studio from packaged, readable source files.

No build tool or web server is needed at runtime. The same catalog and shader
sources feed browser previews and CLI exports; parity is checked in CI.
"""

import base64
import json
from dataclasses import asdict
from html import escape
from importlib.resources import files

from .action_sets import companion_documents
from .catalog import (
    PROFILE_RECIPES,
    PROFILES,
    RECOMMENDED,
    RECOMMENDED_PROFILES,
    collection_documents,
    documents,
)
from .documents import MAX_DOCUMENT_BYTES
from .effects import (
    ELASTIC_ANCHORS,
    FAMILIES,
    LIMITS,
    PARAMETERS,
    PRESET_SCHEMA,
    RESIZE_TEMPLATES,
    Effect,
    describe_presets,
    shader_templates,
)
from .motion import SPRING_LIMITS, Spring, motion_documents
from .profiles import PROFILE_SCHEMA, Profile


def parameter_controls():
    groups = {}
    for key, spec in PARAMETERS.items():
        if key == "family":
            continue
        attrs = f'id="{key}"'
        if spec["type"] == "number":
            low, high = spec["limits"]
            control = f'<input {attrs} type="range" min="{16 if key == "particles" else low}" max="{high}" step="{1 if spec["integer"] else "any"}" />'
            output = f' <output id="{key}-value"></output>'
        elif spec["type"] == "boolean":
            control, output = f'<input {attrs} type="checkbox" />', ""
        else:
            options = "".join(
                f'<option value="{escape(value)}">{escape(value.replace("-", " ").title())}</option>'
                for value in spec["choices"]
            )
            control, output = f"<select {attrs}>{options}</select>", ""
        wrapper = (
            ' id="count-control"'
            if key == "particles"
            else ' id="tile-control"'
            if key == "tile_size"
            else ""
        )
        groups.setdefault(spec["group"], []).append(
            f'<div{wrapper} class="parameter{"" if spec["basic"] else " advanced"}" data-parameter="{key}"><label for="{key}">{escape(spec["label"])}{output}</label>{control}<button type="button" class="reset-parameter" data-reset="{key}" aria-label="Reset {escape(spec["label"])}">Reset</button></div>'
        )
    result = []
    for group, controls in groups.items():
        if group == "general":
            group = "resize"  # resize boolean uses the same opt-in group
        if group == "fragments":
            controls.insert(
                0,
                '<div><label for="density">Particle sizing</label><select id="density"><option value="count">Target particle count</option><option value="tile">Fixed piece size</option></select></div>',
            )
        identifier = {"fragments": "fragment", "slices": "slice"}.get(group, group)
        # Basic family settings stay visible; detailed variation is collapsible.
        if group == "variation":
            result.append(
                '<details id="variation-controls" class="wide advanced"><summary>Advanced waves and variation</summary>'
                + "".join(controls)
                + '<small id="variation-note"></small><span id="slice-variation"></span></details>'
            )
        else:
            result.append(
                f'<div id="{identifier}-controls" class="wide parameter-group">'
                + "".join(controls)
                + "</div>"
            )
    return "".join(result)


def preview_catalog(effect, name="balanced", connection=None, preferences=None, *, hosted=False):
    """Build the browser contract from the validated Python catalog, without I/O writes."""
    if hosted and connection is not None:
        raise ValueError("Hosted Studio must not contain a local session connection")
    profile = effect.document(name) if isinstance(effect, Profile) else None
    if profile:
        effect = effect.open

    return {
        "schema": PRESET_SCHEMA,
        "profile_schema": PROFILE_SCHEMA,
        "max_document_bytes": MAX_DOCUMENT_BYTES,
        "profile": profile,
        "preferences": preferences,
        "specifications": PARAMETERS,
        "parameters": asdict(effect),
        "name": name,
        "presets": describe_presets(),
        "profiles": documents(PROFILES),
        "recommended": RECOMMENDED,
        "recommended_profiles": RECOMMENDED_PROFILES,
        "action_companions": companion_documents(),
        "motion_packs": motion_documents(),
        "motion_defaults": asdict(Spring()),
        "motion_limits": SPRING_LIMITS,
        "collections": collection_documents(),
        "profile_descriptions": {name: recipe[2] for name, recipe in PROFILE_RECIPES.items()},
        "templates": shader_templates(),
        "resize_templates": RESIZE_TEMPLATES,
        "limits": LIMITS,
        "defaults": asdict(Effect()),
        "families": FAMILIES,
        "elastic_anchors": ELASTIC_ANCHORS,
        "connection": connection,
        "hosted": hosted,
        "save_target": connection.get("target", "inir") if connection else "standalone",
    }


def preview_document(effect, name="balanced", connection=None, preferences=None, *, hosted=False):
    """Inline assets so local HTTP and offline files execute identical source."""
    payload = preview_catalog(effect, name, connection, preferences, hosted=hosted)
    # Escape HTML's script-end delimiter even inside an inert JSON script block.
    data = json.dumps(payload).replace("</", "<\\/")
    root = files("niri_fx")
    return (
        root.joinpath("preview.html")
        .read_text()
        .replace("@EFFECT_JSON@", data)
        .replace("@PARAMETER_CONTROLS@", parameter_controls())
        .replace(
            "@FAMILY_OPTIONS@",
            "".join(
                f'<option value="{name}">{spec["label"]}</option>'
                for name, spec in FAMILIES.items()
            ),
        )
        .replace(
            "@APP_ICON@",
            base64.b64encode(root.joinpath("assets/niri-fx.svg").read_bytes()).decode(),
        )
        .replace(
            "<!--@EFFECT_CORE_JS@-->",
            "<script>" + root.joinpath("effect-core.js").read_text() + "</script>",
        )
        .replace(
            "<!--@MOTION_JS@-->",
            "<script>" + root.joinpath("motion-preview.js").read_text() + "</script>",
        )
        .replace(
            "<!--@STUDIO_CSS@-->", "<style>" + root.joinpath("studio.css").read_text() + "</style>"
        )
        .replace(
            "<!--@COMBO_PREVIEW_JS@-->",
            "<script>" + root.joinpath("combo-preview.js").read_text() + "</script>",
        )
        .replace(
            "<!--@STUDIO_JS@-->", "<script>" + root.joinpath("studio.js").read_text() + "</script>"
        )
        .replace(
            "<!--@LIBRARY_JS@-->",
            "<script>" + root.joinpath("library.js").read_text() + "</script>",
        )
    )
