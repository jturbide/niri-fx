"""Finished action pairings built from the same presets used by every interface.

Keep recipes as preset references so a renderer or preset fix reaches all uses.
Single styles and profiles remain distinct documents; interfaces must not flatten
a profile into its opening effect when reviewing or applying a selection.
"""

from .documents import effect_document
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
}
PROFILES = {
    name: Profile(PRESETS[opening], PRESETS[closing])
    for name, (opening, closing, _) in PROFILE_RECIPES.items()
}
STYLES = PRESETS | PROFILES

# Collections describe a look across renderer families. Membership is editorial,
# not inferred from parameters: a changed shader must not silently move a style.
# Keep document schemas free of this browsing metadata.
COLLECTIONS = {
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
