























from __future__ import annotations

import functools
import logging

import textual

log = logging.getLogger(__name__)

_APPLIED = False


from rich.color import Color as RichColor
from rich.style import Style
from textual.color import Color


try:
    from textual.filter import (
        ANSIToTruecolor,
        DIM_FACTOR,
        NO_DIM,
    )
    _HAS_INTERNALS = True
except Exception:
    ANSIToTruecolor = DIM_FACTOR = NO_DIM = None
    _HAS_INTERNALS = False

PATCHABLE = textual.__version__.startswith("8.2") and _HAS_INTERNALS


def _patch_rich_color() -> bool:
    
    fget = Color.rich_color.fget

    def rich_color(self) -> RichColor:
        r, g, b, a, ansi, _ = self
        if ansi is not None:
            return (
                RichColor.parse("default")
                if ansi < 0
                else RichColor.from_ansi(ansi)
            )
        if a == 0:

            return RichColor.parse("default")

        return fget(self)

    Color.rich_color = property(rich_color)
    return True


def _patch_truecolor_style() -> bool:
    
    import textual.filter as _tf

    @functools.lru_cache(1024)
    def truecolor_style(self, style, background):
        terminal_theme = self._terminal_theme
        changed = False

        color = style.color
        bgcolor = style.bgcolor

        if color is not None and not color.is_default and color.triplet is None:
            color = RichColor.from_triplet(
                color.get_truecolor(terminal_theme, foreground=True)
            )
            changed = True

        if (
            bgcolor is not None
            and not bgcolor.is_default
            and bgcolor.triplet is None
        ):
            bgcolor = RichColor.from_triplet(
                bgcolor.get_truecolor(terminal_theme, foreground=False)
            )
            changed = True

        if style.dim and color is not None:
            color = _tf.dim_color(
                background if bgcolor is None else bgcolor, color
            )
            style += NO_DIM
            changed = True

        return style + Style.from_color(color, bgcolor) if changed else style

    ANSIToTruecolor.truecolor_style = truecolor_style
    return True


def _patch_dim_color() -> bool:
    
    import textual.filter as _tf

    @functools.lru_cache(1024)
    def dim_color(background, color, factor: float = DIM_FACTOR) -> RichColor:
        if background.triplet is None or color.triplet is None:
            return color
        red1, green1, blue1 = background.triplet
        red2, green2, blue2 = color.triplet
        return RichColor.from_rgb(
            red1 + (red2 - red1) * factor,
            green1 + (green2 - green1) * factor,
            blue1 + (blue2 - blue1) * factor,
        )

    _tf.dim_color = dim_color
    return True


def apply_patches() -> bool:
    
    global _APPLIED
    if _APPLIED:
        return True
    if not PATCHABLE:
        log.debug("transparencia: versión de Textual no soportada, se omite")
        return False

    applied = 0
    for name, patch in (
        ("rich_color", _patch_rich_color),
        ("truecolor_style", _patch_truecolor_style),
        ("dim_color", _patch_dim_color),
    ):
        try:
            if patch():
                applied += 1
        except Exception:
            log.exception("transparencia: falló el parche %s, se omite", name)

    _APPLIED = True
    log.debug("transparencia: %d/3 parches aplicados", applied)
    return applied == 3
