"""Finished action pairings built from the same presets used by every interface.

Keep recipes as preset references so a renderer or preset fix reaches all uses.
Finished combos can apply a small set of action-specific refinements to those
references without changing the single styles or their other uses.
Single styles and profiles remain distinct documents; interfaces must not flatten
a profile into its opening effect when reviewing or applying a selection.
"""

from dataclasses import replace

from .action_sets import ACTION_SETS
from .documents import effect_document
from .model import FAMILIES
from .motion import MOTION_PACKS
from .presets import PRESETS
from .profiles import Profile

# Editorial starting points, not another preset registry or parameter source.
# All IDs refer to the same immutable styles used by Studio and shell pickers.
RECOMMENDED = {
    "balanced": "Everyday textured fragments",
    "explosion": "A dense outward burst",
    "implosion": "Pieces collapse toward the center",
    "alternating-blinds": "Strips slide in alternating directions",
    "spring-wobble": "A springy whole-window wobble",
    "frost-vanish": "A frosted dissolve",
    "pixel-wipe": "A progressive pixel reveal",
    "ghost-wisps": "Soft drifting wisps",
    "shockwave": "An expanding distortion wave",
}


# Opening style, closing style, and the visible intent of the pairing.
PROFILE_RECIPES = {
    "fragment-flow": ("balanced", "implosion", "Textured assembly, then an inward collapse"),
    "burst-and-drift": ("explosion", "dust-drift", "A strong arrival followed by drifting dust"),
    "frost-and-fragments": (
        "frost-vanish",
        "pixel-dust",
        "A frosted reveal that breaks into pixels",
    ),
    "spring-and-ember": (
        "spring-wobble",
        "ember-erosion",
        "A playful spring with a monochrome fade",
    ),
    "ghost-and-shockwave": ("ghost-wisps", "shockwave", "Soft wisps arrive; a ripple clears them"),
    "pixel-shuffle": ("pixel-wipe", "pixelate", "A pixel reveal and a chunky pixel exit"),
    "ribbon-exit": ("alternating-blinds", "ribbon-fold", "Alternating strips arrive and fold away"),
    "geometric-flow": ("triangle-shatter", "hex-swarm", "Triangles assemble; hexagons drift away"),
    "ribbon-current": (
        "ribbon-wave",
        "ribbon-transfer",
        "Waving ribbons arrive; alternating strips leave",
    ),
    "soft-landing": (
        "momentum-glide",
        "frost-vanish",
        "A gentle elastic arrival and a frosted exit",
    ),
    "gentle-motion": (
        "momentum-glide",
        "frost-vanish",
        "Gentle arrivals and smooth desktop settling",
    ),
    "balanced-motion": (
        "balanced",
        "implosion",
        "Everyday fragments with restrained desktop motion",
    ),
    "playful-motion": (
        "spring-wobble",
        "bubble-burst",
        "Springy arrivals and lightly bouncing desktop motion",
    ),
}
PROFILE_MOTIONS = {f"{key}-motion": value for key, value in MOTION_PACKS.items()}
PROFILE_RECIPES.update(
    {
        name: (recipe.opening, recipe.closing, recipe.description)
        for name, recipe in ACTION_SETS.items()
    }
)

# A compact complete-combo selection, independent of the single-style starters.
# Keep fragments first and the descriptions sourced from the same recipes shown
# in CLI, Studio and shell pickers. This is browsing metadata, not saved settings.
RECOMMENDED_PROFILES = {
    name: PROFILE_RECIPES[name][2]
    for name in (
        "fragment-flow",
        "soft-landing",
        "ribbon-current",
        "playful-motion",
        "geometric-flow",
    )
}

# Refine only the action being used: choosing a finished combo must not mutate
# its source presets or opt into resize/movement. Equal piece/strip counts help
# paired effects feel related; shorter exits and damped springs keep the sequence
# readable without delaying everyday interaction. Unlisted fields keep following
# the source preset, so renderer fixes and shared settings still reach the combo.
PROFILE_TUNING = {
    "fragment-flow": {
        "open": {"open_ms": 560, "scatter": 105, "spin": 140, "stagger": 0.12},
        "close": {
            "close_ms": 520,
            "particles": 720,
            "gravity_strength": 1.3,
            "spin": 160,
            "stagger": 0.12,
        },
    },
    "soft-landing": {
        "open": {
            "open_ms": 480,
            "elastic_strength": 0.28,
            "elastic_damping": 3.6,
            "elastic_stretch": 0.16,
            "elastic_twist": 1,
        },
        "close": {"close_ms": 600, "edge_width": 0.06, "edge_saturation": 0.2},
    },
    "ribbon-current": {
        "open": {
            "open_ms": 760,
            "slice_distance": 135,
            "slice_stagger": 0.12,
            "slice_rotation": 3,
            "wave_strength": 0.75,
        },
        "close": {
            "close_ms": 640,
            "slice_count": 18,
            "slice_distance": 135,
            "slice_stagger": 0.1,
            "slice_rotation": 3,
            "wave_strength": 0.35,
        },
    },
    "playful-motion": {
        "open": {
            "open_ms": 760,
            "elastic_strength": 0.68,
            "elastic_frequency": 2,
            "elastic_damping": 2.4,
        },
        "close": {
            "close_ms": 620,
            "scatter": 130,
            "gravity_strength": 0.65,
            "spin": 65,
            "stagger": 0.12,
        },
    },
    "geometric-flow": {
        "open": {
            "open_ms": 680,
            "particles": 480,
            "scatter": 140,
            "gravity_strength": 0.6,
            "spin": 150,
            "stagger": 0.07,
        },
        "close": {
            "close_ms": 620,
            "particles": 480,
            "scatter": 120,
            "spin": 90,
            "swirl": 18,
            "stagger": 0.07,
        },
    },
}


def _profile(name, opening, closing):
    tuning = PROFILE_TUNING.get(name, {})
    return Profile(
        replace(PRESETS[opening], **tuning["open"]) if "open" in tuning else PRESETS[opening],
        replace(PRESETS[closing], **tuning["close"]) if "close" in tuning else PRESETS[closing],
        motion=PROFILE_MOTIONS.get(name),
    )


PROFILES = {
    name: _profile(name, opening, closing)
    for name, (opening, closing, _) in PROFILE_RECIPES.items()
}
PROFILES.update({name: recipe.profile() for name, recipe in ACTION_SETS.items()})
STYLES = PRESETS | PROFILES

# Collections describe a look across renderer families. Membership is editorial,
# not inferred from parameters: a changed shader must not silently move a style.
# Keep document schemas free of this browsing metadata.
COLLECTIONS = {
    "action-sets": {
        "label": "Coordinated action sets",
        "description": "Finished looks with matching opt-in resize and movement companions",
        "styles": tuple(ACTION_SETS),
    },
    "desktop": {
        "label": "Desktop motion",
        "description": "Coordinated window effects and workspace, camera and overview springs",
        "styles": ("gentle-motion", "balanced-motion", "playful-motion"),
    },
    "everyday": {
        "label": "Everyday",
        "description": "Compact movement and readable arrivals",
        "styles": (
            "subtle",
            "balanced",
            "momentum-glide",
            "soft-phase",
            "soft-swirl",
            "fragment-flow",
            "soft-landing",
        ),
    },
    "bursts": {
        "label": "Explosions and gravity",
        "description": "Outward blasts, inward collapses and drifting debris",
        "styles": (
            "explosion",
            "implosion",
            "dramatic",
            "earth",
            "black-hole",
            "space",
            "vortex",
            "confetti",
            "core-detonation",
            "corner-burst",
            "orbital-collapse",
            "burst-and-drift",
        ),
    },
    "shapes": {
        "label": "Geometric pieces",
        "description": "Triangles, circles, rectangles and hexagonal layouts",
        "styles": (
            "triangle-shatter",
            "circle-burst",
            "rectangle-confetti",
            "hex-swarm",
            "bubble-burst",
            "mosaic-burst",
            "hexagon-burst",
            "hive-collapse",
            "geometric-flow",
            "mixed-confetti",
            "orbiting-shapes",
        ),
    },
    "ribbons": {
        "label": "Slices and ribbons",
        "description": "Alternating strips, folds, hinges and flowing waves",
        "styles": (
            "slide-apart",
            "alternating-blinds",
            "diagonal-shear",
            "split-curtain",
            "ribbon-wave",
            "shuffled-slats",
            "venetian-sweep",
            "hinged-fan",
            "venetian-shutter",
            "ribbon-fold",
            "zipper",
            "slice-exchange",
            "ribbon-transfer",
            "orbital-ribbons",
            "ribbon-exit",
            "ribbon-current",
        ),
    },
    "playful": {
        "label": "Wobble and bounce",
        "description": "Elastic sheets, twists and springy settling",
        "styles": (
            "spring-wobble",
            "rubber-band",
            "jelly",
            "twist-snap",
            "flag-wave",
            "corner-spring",
            "accordion",
            "spring-and-ember",
        ),
    },
    "atmospheric": {
        "label": "Soft and atmospheric",
        "description": "Frost, wisps, ink and restrained distortion",
        "styles": (
            "frost-vanish",
            "noise-dissolve",
            "ember-erosion",
            "ghost-wisps",
            "ink-current",
            "ink-spread",
            "ink-bloom",
            "ripple-collapse",
            "soft-swirl",
            "frost-and-fragments",
            "ghost-and-shockwave",
            "soft-landing",
        ),
    },
    "pixels": {
        "label": "Pixels and glitches",
        "description": "Pixel wipes, chunky breakup and digital disruption",
        "styles": (
            "pixel-wipe",
            "pixelate",
            "pixel-dust",
            "dust-drift",
            "signal-glitch",
            "chromatic-glitch",
            "pixel-transfer",
            "pixel-shuffle",
        ),
    },
}


def collection_names(name):
    return tuple(key for key, collection in COLLECTIONS.items() if name in collection["styles"])


def collection_documents():
    """Fresh browsing metadata; portable style documents remain unchanged."""
    return {key: dict(value, styles=list(value["styles"])) for key, value in COLLECTIONS.items()}


def title(name):
    return name.replace("-", " ").title()


def families(style):
    effects = (
        (style.open, style.close, style.resize, style.movement)
        if isinstance(style, Profile)
        else (style,)
    )
    return tuple(dict.fromkeys(effect.family for effect in effects if effect is not None))


def documents(styles=STYLES):
    """Normalized, portable documents for pickers; returned values are fresh copies."""
    return {name: effect_document(title(name), style) for name, style in styles.items()}


def summaries(keys):
    """Discover looks without serializing every control for every action.

    Keys use the same filters and ordering as the full catalog. Consumers can
    fetch only their chosen document after comparing these short descriptions.
    """
    result = {}
    for key in keys:
        style = STYLES[key]
        profile = isinstance(style, Profile)
        opening, closing = (style.open, style.close) if profile else (style, style)
        optional = []
        if style.resize:
            optional.append("resize")
        if profile:
            optional.extend(
                action for action in ("movement", "motion", "pointer") if getattr(style, action)
            )
        result[key] = {
            "name": title(key),
            "kind": "profile" if profile else "effect",
            "families": list(families(style)),
            "description": PROFILE_RECIPES[key][2]
            if profile
            else RECOMMENDED.get(key, FAMILIES[style.family]["label"]),
            "open_ms": opening.open_ms,
            "close_ms": closing.close_ms,
            "optional_actions": optional,
        }
    return result
