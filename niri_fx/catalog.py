"""Finished action pairings built from the same presets used by every interface.

Keep recipes as preset references so a renderer or preset fix reaches all uses.
Single styles and profiles remain distinct documents; interfaces must not flatten
a profile into its opening effect when reviewing or applying a selection.
"""

from .documents import effect_document
from .presets import PRESETS
from .profiles import Profile

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
}
PROFILES = {
    name: Profile(PRESETS[opening], PRESETS[closing])
    for name, (opening, closing, _) in PROFILE_RECIPES.items()
}
STYLES = PRESETS | PROFILES


def title(name):
    return name.replace("-", " ").title()


def families(style):
    effects = (style.open, style.close) if isinstance(style, Profile) else (style,)
    return tuple(dict.fromkeys(effect.family for effect in effects))


def documents(styles=STYLES):
    """Normalized, portable documents for pickers; returned values are fresh copies."""
    return {name: effect_document(title(name), style) for name, style in styles.items()}
