"""
views/styles.py
===============
Central stylesheet and colour token registry for the Quoridor UI.

All colours, radii, and spacing are derived from the Tailwind design tokens
embedded in the provided HTML prototypes.  Using a single Python source of
truth ensures pixel-perfect consistency across all screens.

Usage
-----
    from views.styles import COLORS, STYLESHEET, font

    widget.setStyleSheet(STYLESHEET)
    label.setFont(font("display-lg"))
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt

# ──────────────────────────────────────────────────────────────────────────────
# Color tokens  (verbatim from the Tailwind config in the provided HTML files)
# ──────────────────────────────────────────────────────────────────────────────

COLORS: dict[str, str] = {
    # Surfaces ─────────────────────────────────────────────────────────
    "background"               : "#0b1326",
    "surface"                  : "#0b1326",
    "surface-dim"              : "#0b1326",
    "surface-container-lowest" : "#060e20",
    "surface-container-low"    : "#131b2e",
    "surface-container"        : "#171f33",
    "surface-container-high"   : "#222a3d",
    "surface-container-highest": "#2d3449",
    "surface-variant"          : "#2d3449",
    "surface-bright"           : "#31394d",

    # Primary / Neutral ────────────────────────────────────────────────
    "primary"                  : "#ffffff",
    "primary-fixed"            : "#e5e2dd",
    "primary-fixed-dim"        : "#c8c6c2",
    "on-primary"               : "#31302d",
    "on-primary-fixed"         : "#1c1c19",
    "on-primary-fixed-variant" : "#474743",
    "primary-container"        : "#e5e2dd",
    "on-primary-container"     : "#656461",
    "inverse-primary"          : "#5f5e5b",

    # Secondary / Accent (coral) ────────────────────────────────────────
    "secondary"                : "#ffb4aa",
    "secondary-fixed"          : "#ffdad5",
    "secondary-fixed-dim"      : "#ffb4aa",
    "secondary-container"      : "#7d3029",
    "on-secondary"             : "#5c1813",
    "on-secondary-fixed"       : "#3f0303",
    "on-secondary-fixed-variant": "#7a2e27",
    "on-secondary-container"   : "#ff9f93",

    # Tertiary / Amber ─────────────────────────────────────────────────
    "tertiary"                 : "#ffffff",
    "tertiary-fixed"           : "#ffddbb",
    "tertiary-fixed-dim"       : "#e3c19f",
    "tertiary-container"       : "#ffddbb",
    "on-tertiary"              : "#412c14",
    "on-tertiary-fixed"        : "#291803",
    "on-tertiary-fixed-variant": "#5a4229",
    "on-tertiary-container"    : "#7a5f44",

    # Text & surfaces ──────────────────────────────────────────────────
    "on-background"            : "#dae2fd",
    "on-surface"               : "#dae2fd",
    "on-surface-variant"       : "#c8c7be",
    "inverse-surface"          : "#dae2fd",
    "inverse-on-surface"       : "#283044",

    # Borders ──────────────────────────────────────────────────────────
    "outline"                  : "#929189",
    "outline-variant"          : "#474741",

    # Error ────────────────────────────────────────────────────────────
    "error"                    : "#ffb4ab",
    "error-container"          : "#93000a",
    "on-error"                 : "#690005",
    "on-error-container"       : "#ffdad6",

    # Misc ─────────────────────────────────────────────────────────────
    "surface-tint"             : "#c8c6c2",
}


def color(token: str) -> QColor:
    """
    Return a QColor for a design-token name.

    Parameters
    ----------
    token : str
        Key from the COLORS dict (e.g. ``"surface-container"``).

    Returns
    -------
    QColor
    """
    hex_val = COLORS.get(token, "#ff00ff")   # magenta signals missing token
    return QColor(hex_val)


# ──────────────────────────────────────────────────────────────────────────────
# Typography helpers (Manrope via system / Google Fonts fallback)
# ──────────────────────────────────────────────────────────────────────────────

# Font scale tokens matching Tailwind fontSize config
_FONT_SCALE: dict[str, tuple[int, int, Qt.AlignmentFlag]] = {
    # token        : (pt_size, weight)
    "display-lg"   : (36,  QFont.Weight.Bold),
    "headline-md"  : (18,  QFont.Weight.DemiBold),
    "body-base"    : (12,  QFont.Weight.Normal),
    "label-caps"   : (9,   QFont.Weight.Bold),
    "inventory-num": (15,  QFont.Weight.Medium),
}


def font(token: str, *, italic: bool = False) -> QFont:
    """
    Return a QFont configured for the given typography token.

    If Manrope is installed on the system or registered via
    QFontDatabase, it will be used.  Otherwise falls back to the
    next closest system sans-serif.

    Parameters
    ----------
    token : str
        One of the keys in ``_FONT_SCALE``.
    italic : bool
        Whether to apply italic style.

    Returns
    -------
    QFont
    """
    pt_size, weight = _FONT_SCALE.get(token, (12, QFont.Weight.Normal))
    # Prefer Manrope; graceful fallback chain
    f = QFont("Manrope")
    if not f.exactMatch():
        f = QFont("Segoe UI")
        if not f.exactMatch():
            f = QFont()   # system default sans-serif
    f.setPointSize(pt_size)
    f.setWeight(weight)
    f.setItalic(italic)
    if token == "label-caps":
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 110)
    return f


# ──────────────────────────────────────────────────────────────────────────────
# Master QSS stylesheet
# ──────────────────────────────────────────────────────────────────────────────

def _c(token: str) -> str:
    """Shorthand: return a hex string for use inside the QSS f-string."""
    return COLORS[token]


STYLESHEET: str = f"""
/* ── Global reset ───────────────────────────────────────────────────── */
* {{
    margin:  0;
    padding: 0;
}}

QWidget {{
    background-color: {_c("background")};
    color: {_c("on-surface")};
    font-family: "Manrope", "Segoe UI", sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}}

/* ── Scroll areas ───────────────────────────────────────────────────── */
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
QScrollBar:vertical {{
    background: {_c("surface-container-low")};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {_c("outline-variant")};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* ── Navigation top-bar ─────────────────────────────────────────────── */
#TopBar {{
    background-color: rgba(3, 7, 18, 0.90);
    border-bottom: 1px solid {_c("outline-variant")};
}}

/* ── Containers / Cards ─────────────────────────────────────────────── */
#Card {{
    background-color: {_c("surface-container")};
    border: 1px solid {_c("outline-variant")};
    border-radius: 8px;
}}

#CardHigh {{
    background-color: {_c("surface-container-high")};
    border: 1px solid {_c("outline-variant")};
    border-radius: 8px;
}}

#SectionCard {{
    background-color: {_c("surface-container-low")};
    border: 1px solid {_c("outline-variant")};
    border-radius: 2px;
}}

/* ── Labels ─────────────────────────────────────────────────────────── */
#LabelPrimary   {{ color: {_c("primary")};            }}
#LabelMuted     {{ color: {_c("on-surface-variant")}; }}
#LabelSecondary {{ color: {_c("secondary")};          }}
#LabelError     {{ color: {_c("error")};              }}
#LabelAmber     {{ color: {_c("tertiary-fixed")};     }}

/* ── Line edits / inputs ────────────────────────────────────────────── */
QLineEdit {{
    background-color: {_c("surface")};
    color: {_c("primary")};
    border: 1px solid {_c("outline-variant")};
    border-radius: 2px;
    padding: 10px 16px;
    font-size: 14px;
    selection-background-color: {_c("surface-variant")};
}}
QLineEdit:focus {{
    border: 1px solid {_c("primary-fixed")};
}}
QLineEdit::placeholder {{
    color: {_c("on-surface-variant")};
}}

/* ── Primary button ─────────────────────────────────────────────────── */
#BtnPrimary {{
    background-color: {_c("primary")};
    color: {_c("on-primary")};
    border: none;
    border-radius: 2px;
    padding: 14px 32px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}}
#BtnPrimary:hover  {{ background-color: {_c("primary-fixed")};     }}
#BtnPrimary:pressed{{ background-color: {_c("primary-fixed-dim")};  }}

/* ── Secondary / outline button ────────────────────────────────────── */
#BtnOutline {{
    background-color: transparent;
    color: {_c("on-surface")};
    border: 1px solid {_c("outline-variant")};
    border-radius: 2px;
    padding: 14px 32px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.2px;
}}
#BtnOutline:hover  {{ background-color: {_c("surface-variant")}; color: {_c("primary")}; border-color: {_c("outline")}; }}
#BtnOutline:pressed{{ background-color: {_c("surface-bright")}; }}

/* ── Icon / action button (board controls) ──────────────────────────── */
#BtnIcon {{
    background-color: {_c("surface-container-high")};
    color: {_c("on-surface")};
    border: 1px solid {_c("outline-variant")};
    border-radius: 8px;
    padding: 10px;
    font-size: 11px;
}}
#BtnIcon:hover  {{ background-color: {_c("surface-bright")}; border-color: {_c("outline")}; }}
#BtnIcon:pressed{{ background-color: {_c("surface-container")}; }}
#BtnIcon:disabled {{ color: {_c("outline-variant")}; border-color: {_c("surface-container-high")}; }}

/* ── Difficulty radio selectors ─────────────────────────────────────── */
#DiffCard {{
    background-color: {_c("surface-container-highest")};
    border: 1px solid {_c("outline-variant")};
    border-radius: 8px;
    padding: 16px;
}}
#DiffCard[selected="true"] {{
    border: 1px solid {_c("primary")};
    background-color: {_c("surface-container-high")};
}}
#DiffCardHard[selected="true"] {{
    border: 1px solid {_c("secondary")};
    background-color: rgba(125, 48, 41, 0.20);
}}

/* ── Player HUD cards ───────────────────────────────────────────────── */
#PlayerCard {{
    background-color: {_c("surface-container-high")};
    border: 1px solid {_c("outline-variant")};
    border-radius: 8px;
    padding: 10px 16px;
}}
#PlayerCard[active="true"] {{
    border: 1px solid {_c("primary-fixed-dim")};
}}

/* ── Stat tiles (Victory screen) ────────────────────────────────────── */
#StatTile {{
    background-color: {_c("surface-container")};
    border: 1px solid {_c("outline")};
    border-radius: 8px;
    padding: 32px 24px;
}}
#StatTile:hover {{
    background-color: {_c("surface-container-high")};
}}

/* ── Rules bento sections ───────────────────────────────────────────── */
#RulesSection {{
    background-color: {_c("surface-container-low")};
    border: 1px solid {_c("outline-variant")};
    border-radius: 2px;
}}
#RulesWarning {{
    background-color: rgba(147, 0, 10, 0.10);
    border-left: 2px solid {_c("error")};
}}
#EngagementBox {{
    background-color: {_c("surface-container")};
    border: 1px solid rgba(71, 71, 65, 0.5);
    border-radius: 2px;
}}
#TurnActionCard {{
    background-color: {_c("surface-dim")};
    border: 1px solid rgba(71, 71, 65, 0.5);
    border-radius: 2px;
}}
#TurnActionCard:hover {{
    border-color: {_c("outline")};
}}

/* ── Separator ──────────────────────────────────────────────────────── */
#Separator {{
    background-color: {_c("outline-variant")};
    max-height: 1px;
    min-height: 1px;
}}
"""
