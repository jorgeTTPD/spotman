"""Transparencia 100% para Textual 8.2.x.

Bug de fondo: Textual convierte ``background: transparent`` en
``Color(0,0,0,alpha=0)``, pero ``Color.rich_color`` descarta el canal
alpha y lo emite como NEGRO OPACO literal. Estos 3 monkey-patches
corrigen el bug en caliente (sin tocar el paquete instalado):

  * Parche 1 - ``Color.rich_color`` respeta el alpha: si alpha == 0
    devuelve ``RichColor.parse("default")`` (fondo por defecto del
    terminal = transparente real).
  * Parche 2 - ``ANSIToTruecolor.truecolor_style``: NO convierte los
    colores 'default' a los colores del tema (que volvían a tapar la
    transparencia). 'default' sobrevive y Rich emite '49'.
  * Parche 3 - ``dim_color``: no crashear cuando un color no tiene
    triplet (los colores 'default' no tienen). Si falta, devuelve el
    color sin cambiar.

Blindaje: solo se aplica si textual.__version__ empieza por "8.2"
(los internals cambian entre versiones). Los imports de internals de
``textual.filter`` van en try/except: si no existen, PATCHABLE pasa a
False y la app arranca igual (solo pierde la transparencia, nunca
crashea).
"""

from __future__ import annotations

import functools
import logging

import textual

log = logging.getLogger(__name__)

_APPLIED = False

# API pública estable (segura de importar en cualquier versión)
from rich.color import Color as RichColor  # noqa: E402
from rich.style import Style  # noqa: E402
from textual.color import Color  # noqa: E402

# Internals de textual.filter: pueden cambiar/renombrarse entre versiones.
try:
    from textual.filter import (  # noqa: E402
        ANSIToTruecolor,
        DIM_FACTOR,
        NO_DIM,
    )
    _HAS_INTERNALS = True
except Exception:  # pragma: no cover - blindaje de versión
    ANSIToTruecolor = DIM_FACTOR = NO_DIM = None  # type: ignore[assignment]
    _HAS_INTERNALS = False

PATCHABLE = textual.__version__.startswith("8.2") and _HAS_INTERNALS


def _patch_rich_color() -> bool:
    """Parche 1: Color.rich_color respeta el canal alpha."""
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
            # Transparente real -> fondo por defecto del terminal
            return RichColor.parse("default")
        # Comportamiento original para colores opacos
        return fget(self)

    Color.rich_color = property(rich_color)  # type: ignore[method-assign]
    return True


def _patch_truecolor_style() -> bool:
    """Parche 2: no convertir colores 'default' al tema en el filtro ANSI."""
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

    ANSIToTruecolor.truecolor_style = truecolor_style  # type: ignore[method-assign]
    return True


def _patch_dim_color() -> bool:
    """Parche 3: dim_color no crashea con colores sin triplet."""
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

    _tf.dim_color = dim_color  # type: ignore[assignment]
    return True


def apply_patches() -> bool:
    """Aplica los 3 parches (idempotente). Devuelve True si se aplicaron."""
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
        except Exception:  # pragma: no cover - blindaje de versión
            log.exception("transparencia: falló el parche %s, se omite", name)

    _APPLIED = True
    log.debug("transparencia: %d/3 parches aplicados", applied)
    return applied == 3
