"""
views/screens/rules_screen.py
==============================
Screen 6 — Rules

Bento-grid layout with four sections:

  ┌──────────────────────── full width ─────────────────────────────┐
  │  🏴  Objective                                                    │
  ├─────────────── 50 % ─────────────┬────────────── 50 % ──────────┤
  │  ✛  Pawn Movement                │  ⊞  Wall Placement            │
  │      └─ Engagement Protocol box  │      └─ ⚠ Absolute Rule box  │
  ├──────────────────────── full width ─────────────────────────────┤
  │  ⌛  Turn Order  │  ACTION 1  OR  ACTION 2                        │
  └──────────────────────────────────────────────────────────────────┘

Accessible from ANY screen via the TopBar "RULES" button.
Clicking "← Back" (or clicking RULES again) returns to the origin screen.

Bugs fixed vs. the previous draft
-----------------------------------
* SyntaxError on Python <= 3.11: all f-string dict-key lookups extracted to
  module-level constants before being embedded in template strings.
* QGridLayout missing column-stretch: both columns now share equal width via
  setColumnStretch(0,1) and setColumnStretch(1,1).
* glyph U+29D7 absent from most system fonts: replaced with safe U+231B.
* `opacity: 0.70` QSS property silently ignored by Qt: removed; colour
  transparency is expressed via RGBA hex instead.
* _body(small=True) now sets font point-size via QFont, not a CSS override
  that Qt ignores when a QFont is already applied.
* setColumnMinimumWidth prevents cards from collapsing on narrow viewports.
* reset_scroll() added so NavigationController can scroll to top on each push.

Emits
-----
back_requested : Signal()
    Consumed by NavigationController._pop_rules() to return to the previous
    screen.  Connected by TopBar.rules_requested AND the back button.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
)

from views.components.top_bar import TopBar
from views.styles import COLORS, font


# ──────────────────────────────────────────────────────────────────────────────
# Module-level colour aliases
# All dict key lookups are extracted here once so that f-strings inside
# methods can safely embed them on Python 3.10/3.11 without nested-quote
# ambiguity (which causes SyntaxError on those versions).
# ──────────────────────────────────────────────────────────────────────────────

_C_PRIMARY     = COLORS["primary"]
_C_ON_SURFACE  = COLORS["on-surface"]
_C_ON_VARIANT  = COLORS["on-surface-variant"]
_C_SURF_CH     = COLORS["surface-container-high"]
_C_SURF_C      = COLORS["surface-container"]
_C_SURF_DIM    = COLORS["surface-dim"]
_C_SURF_CL     = COLORS["surface-container-low"]
_C_OUTLINE     = COLORS["outline"]
_C_OUTLINE_V   = COLORS["outline-variant"]
_C_ERROR       = COLORS["error"]


# ──────────────────────────────────────────────────────────────────────────────
# Shared widget factories
# ──────────────────────────────────────────────────────────────────────────────

class _RulesSection(QFrame):
    """
    Styled bento card container used by every rules section.

    Provides the ``surface-container-low`` dark background, ``outline-variant``
    border, and 2 px corner radius
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RulesSection")
        self.setStyleSheet(
            "QFrame#RulesSection {"
            f"  background-color: {_C_SURF_CL};"
            f"  border: 1px solid {_C_OUTLINE_V};"
            "  border-radius: 2px;"
            "}"
        )


def _divider() -> QFrame:
    """
    Return a 1 px horizontal rule that matches the ``outline-variant/30``
    separator used beneath section headings
    """
    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet("background: rgba(71, 71, 65, 0.30); border: none;")
    return sep


def _body(text: str, *, small: bool = False) -> QLabel:
    """
    Return a word-wrapping, RichText-capable body label.

    Parameters
    ----------
    text : str
        Plain or inline-HTML text (``<b>``, ``<span style>`` are supported
        because ``Qt.TextFormat.RichText`` is set explicitly).
    small : bool
        When True the font point-size is reduced to 10 pt (used inside the
        inset Engagement Protocol and Warning boxes).  The size is set on the
        QFont object — NOT via a CSS ``font-size`` property, which Qt ignores
        when a QFont has already been applied to the widget.

    Returns
    -------
    QLabel
        Configured label ready to be added to a layout.
    """
    body_font = font("body-base")
    if small:
        body_font.setPointSize(10)

    lbl = QLabel(text)
    lbl.setFont(body_font)
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    lbl.setStyleSheet(f"color: {_C_ON_VARIANT}; background: transparent;")
    return lbl


def _section_header(title: str, icon_char: str) -> QWidget:
    """
    Return the icon + title heading row used at the top of Pawn Movement
    and Wall Placement cards.

    Parameters
    ----------
    title : str
        Section title rendered in ``headline-md`` weight.
    icon_char : str
        Short symbol character placed to the left of the title.

    Returns
    -------
    QWidget
        Horizontal row widget.
    """
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    rl = QHBoxLayout(row)
    rl.setContentsMargins(0, 0, 0, 0)
    rl.setSpacing(12)

    icon_lbl = QLabel(icon_char)
    icon_lbl.setStyleSheet(
        f"color: {_C_ON_VARIANT}; font-size: 15px; background: transparent;"
    )
    rl.addWidget(icon_lbl)

    title_lbl = QLabel(title)
    title_lbl.setFont(font("headline-md"))
    title_lbl.setStyleSheet(f"color: {_C_PRIMARY}; background: transparent;")
    rl.addWidget(title_lbl)
    rl.addStretch()
    return row


# ──────────────────────────────────────────────────────────────────────────────
# RulesScreen
# ──────────────────────────────────────────────────────────────────────────────

class RulesScreen(QWidget):
    """
    Scrollable rules reference screen.

    Faithfully reproduces the bento-grid layout.

    Signals
    -------
    back_requested : Signal()
        Emitted by both the "← Back" button and the TopBar RULES button.
        NavigationController connects this to ``_pop_rules()`` so the user
        returns to whichever screen they came from.
    """

    back_requested: Signal = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scroll: QScrollArea | None = None   # kept for reset_scroll()
        self._build_ui()

    # ------------------------------------------------------------------
    # Root layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble TopBar → QScrollArea containing page header + bento grid."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # TopBar — clicking RULES while on the Rules page acts as a back-press
        top_bar = TopBar()
        top_bar.rules_requested.connect(self.back_requested)
        root.addWidget(top_bar)

        # Scrollable content
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setStyleSheet("background: transparent; border: none;")
        self._scroll.setWidget(self._build_content())
        root.addWidget(self._scroll, stretch=1)

    def _build_content(self) -> QWidget:
        """
        Build and return the inner content widget:
        page header + bento grid + back button.
        """
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(60, 48, 60, 60)
        cl.setSpacing(28)

        # ── Page header ──────────────────────────────────────────────────
        header_font = font("display-lg")
        header_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5)

        page_title = QLabel("ARCHITECTURAL STRATEGY")
        page_title.setFont(header_font)
        page_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_title.setStyleSheet(f"color: {_C_PRIMARY}; background: transparent;")
        cl.addWidget(page_title)

        sub = QLabel(
            "Mastering the spatial constraints and tactical navigation "
            "required for victory."
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(font("body-base"))
        sub.setStyleSheet(f"color: {_C_ON_VARIANT}; background: transparent;")
        cl.addWidget(sub)

        # ── Bento grid ───────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(20)
        # BUG FIX: equal column stretch so both half-width sections share width
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        # Prevent cards from collapsing to zero on narrow viewports
        grid.setColumnMinimumWidth(0, 280)
        grid.setColumnMinimumWidth(1, 280)

        grid.addWidget(self._build_objective(),      0, 0, 1, 2)
        grid.addWidget(self._build_pawn_movement(),  1, 0)
        grid.addWidget(self._build_wall_placement(), 1, 1)
        grid.addWidget(self._build_turn_order(),     2, 0, 1, 2)

        cl.addLayout(grid)

        # ── Back button ──────────────────────────────────────────────────
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("BtnOutline")
        back_btn.setFont(font("label-caps"))
        back_btn.setFixedHeight(44)
        back_btn.setFixedWidth(130)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_requested)
        cl.addWidget(back_btn, 0, Qt.AlignmentFlag.AlignLeft)

        return content

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_objective(self) -> _RulesSection:
        """
        Full-width Objective card.

        Contains a flag icon badge, headline, thin rule, and body paragraph.
        """
        sec = _RulesSection()
        layout = QVBoxLayout(sec)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(14)

        # ── Icon + title header ──────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(16)
        hdr.setContentsMargins(0, 0, 0, 0)

        flag_badge = QLabel("🏴")
        flag_badge.setFixedSize(44, 44)
        flag_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flag_badge.setStyleSheet(
            f"font-size: 20px;"
            f"background: {_C_SURF_CH};"
            f"border: 1px solid {_C_OUTLINE_V};"
            f"border-radius: 22px;"
        )
        hdr.addWidget(flag_badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(6)
        title_col.setContentsMargins(0, 0, 0, 0)

        obj_lbl = QLabel("Objective")
        obj_lbl.setFont(font("headline-md"))
        obj_lbl.setStyleSheet(f"color: {_C_PRIMARY}; background: transparent;")
        title_col.addWidget(obj_lbl)
        title_col.addWidget(_divider())

        hdr.addLayout(title_col)
        hdr.addStretch()
        layout.addLayout(hdr)

        # ── Body ─────────────────────────────────────────────────────────
        # Colour variable extracted before f-string to avoid nested-quote
        # SyntaxError on Python <= 3.11.
        c = _C_ON_SURFACE
        body_html = (
            "The ultimate goal is spatial dominance. The first player to "
            "successfully navigate their pawn across the board and reach "
            f"<b style=\"color:{c}\">any square on the opponent's starting "
            "baseline</b> claims victory. "
            "It is a race of efficiency and obstruction."
        )
        layout.addWidget(_body(body_html))
        return sec

    # ------------------------------------------------------------------

    def _build_pawn_movement(self) -> _RulesSection:
        """
        Left-column Pawn Movement card.

        Describes orthogonal-only movement then explains the jump-over rule
        inside an inset "ENGAGEMENT PROTOCOL" sub-box.
        """
        sec = _RulesSection()
        layout = QVBoxLayout(sec)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(14)

        layout.addWidget(_section_header("Pawn Movement", "✛"))
        layout.addWidget(_divider())

        c = _C_ON_SURFACE
        move_html = (
            "Movement is restricted to orthogonal paths. Pawns move precisely "
            f"<b style=\"color:{c}\">one square at a time, horizontally or "
            "vertically</b>. Diagonal movement is strictly prohibited unless "
            "facilitating a jump."
        )
        layout.addWidget(_body(move_html))
        layout.addStretch()

        # ── Engagement Protocol inset ────────────────────────────────────
        box = QFrame()
        box.setObjectName("EngagementBox")
        box.setStyleSheet(
            "QFrame#EngagementBox {"
            f"  background: {_C_SURF_C};"
            "  border: 1px solid rgba(71, 71, 65, 0.50);"
            "  border-radius: 2px;"
            "}"
        )
        bl = QVBoxLayout(box)
        bl.setContentsMargins(16, 14, 16, 14)
        bl.setSpacing(8)

        cap_font = font("label-caps")
        cap_font.setPointSize(8)
        cap = QLabel("ENGAGEMENT PROTOCOL")
        cap.setFont(cap_font)
        # rgba white at 55 % opacity reproduces the `opacity: 0.70` intent
        # without using the unsupported QSS opacity property.
        cap.setStyleSheet(
            "color: rgba(255, 255, 255, 0.55); background: transparent;"
        )
        bl.addWidget(cap)

        jump_html = (
            f"If two pawns face each other on adjacent squares, the active "
            f"player may <b style=\"color:{c}\">jump over the opponent's "
            "pawn</b>, advancing two spaces in a straight line. If a wall is "
            "directly behind the opponent, the player may jump diagonally to "
            "either side."
        )
        bl.addWidget(_body(jump_html, small=True))
        layout.addWidget(box)
        return sec

    # ------------------------------------------------------------------

    def _build_wall_placement(self) -> _RulesSection:
        """
        Right-column Wall Placement card.

        Three bulleted rules describe inventory, span, and immutability,
        followed by the red-bordered Absolute Rule warning box.
        """
        sec = _RulesSection()
        layout = QVBoxLayout(sec)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(14)

        layout.addWidget(_section_header("Wall Placement", "⊞"))
        layout.addWidget(_divider())

        c = _C_ON_SURFACE
        bullets: list[tuple[str, str]] = [
            (
                "▪",
                "Each player begins the engagement with an inventory of "
                f"<b style=\"color:{c}\">10 walls</b>.",
            ),
            (
                "▪",
                "Walls must be placed precisely "
                f"<b style=\"color:{c}\">between two squares</b>, "
                "spanning the exact width of two adjacent cells.",
            ),
            (
                "▪",
                "Once committed to the board, a wall is immutable. "
                f"<b style=\"color:{c}\">They cannot be moved or removed.</b>",
            ),
        ]

        for bullet_char, html in bullets:
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 2, 0, 2)
            row_l.setSpacing(10)

            bullet_lbl = QLabel(bullet_char)
            bullet_lbl.setFixedWidth(14)
            bullet_lbl.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
            )
            bullet_lbl.setStyleSheet(
                f"color: {_C_ON_VARIANT}; background: transparent; "
                "font-size: 12px; padding-top: 3px;"
            )
            row_l.addWidget(bullet_lbl)
            row_l.addWidget(_body(html), stretch=1)
            layout.addWidget(row_w)

        layout.addStretch()

        # ── Absolute Rule warning ────────────────────────────────────────
        warn = QFrame()
        warn.setObjectName("RulesWarning")
        warn.setStyleSheet(
            "QFrame#RulesWarning {"
            "  background: rgba(147, 0, 10, 0.10);"
            f"  border-left: 2px solid {_C_ERROR};"
            "  border-top: none;"
            "  border-right: none;"
            "  border-bottom: none;"
            "  border-radius: 0px;"
            "}"
        )
        wl = QHBoxLayout(warn)
        wl.setContentsMargins(12, 10, 12, 10)
        wl.setSpacing(10)

        warn_icon = QLabel("⚠")
        warn_icon.setFixedWidth(20)
        warn_icon.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        warn_icon.setStyleSheet(
            f"color: {_C_ERROR}; font-size: 13px; background: transparent;"
        )
        wl.addWidget(warn_icon)

        e = _C_ERROR
        warn_html = (
            f"<b style=\"color:{e}\">Absolute Rule:</b> "
            f"<span style=\"color:{e}\">You cannot completely block an "
            "opponent's path to their goal line. There must always remain at "
            "least one valid route.</span>"
        )
        warn_body = _body(warn_html, small=True)
        warn_body.setStyleSheet(f"color: {_C_ERROR}; background: transparent;")
        wl.addWidget(warn_body, stretch=1)

        layout.addWidget(warn)
        return sec

    # ------------------------------------------------------------------

    def _build_turn_order(self) -> _RulesSection:
        """
        Full-width Turn Order card.

        Left third: hourglass icon + title + description.
        Right two-thirds: ACTION 1 card · OR · ACTION 2 card.

        The ⧗ (U+29D7) glyph has poor font coverage; ⌛ (U+231B) is used
        instead as it is present in every modern system font and Emoji font.
        """
        sec = _RulesSection()
        outer = QHBoxLayout(sec)
        outer.setContentsMargins(36, 28, 36, 28)
        outer.setSpacing(48)

        # ── Left: description ────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)
        left.setContentsMargins(0, 0, 0, 0)

        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(10)
        hdr_row.setContentsMargins(0, 0, 0, 0)

        hourglass = QLabel("⌛")
        hourglass.setStyleSheet(
            f"color: {_C_ON_VARIANT}; font-size: 18px; background: transparent;"
        )
        hdr_row.addWidget(hourglass)

        turn_lbl = QLabel("Turn Order")
        turn_lbl.setFont(font("headline-md"))
        turn_lbl.setStyleSheet(f"color: {_C_PRIMARY}; background: transparent;")
        hdr_row.addWidget(turn_lbl)
        hdr_row.addStretch()
        left.addLayout(hdr_row)

        left.addWidget(
            _body(
                "The architectural dance is sequential. On your turn, you "
                "must commit to a single strategic path."
            )
        )
        left.addStretch()
        outer.addLayout(left, stretch=1)

        # ── Right: two action cards ──────────────────────────────────────
        right = QHBoxLayout()
        right.setSpacing(12)
        right.setContentsMargins(0, 0, 0, 0)

        right.addWidget(
            self._action_card("🚶", "ACTION 1", "Advance your pawn to secure position."),
            stretch=1,
        )

        or_lbl = QLabel("OR")
        or_lbl.setFont(font("label-caps", italic=True))
        or_lbl.setFixedWidth(30)
        or_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        or_lbl.setStyleSheet(f"color: {_C_OUTLINE_V}; background: transparent;")
        right.addWidget(or_lbl)

        right.addWidget(
            self._action_card("🏗", "ACTION 2", "Deploy a wall to shape the battlefield."),
            stretch=1,
        )
        outer.addLayout(right, stretch=2)
        return sec

    # ------------------------------------------------------------------

    def _action_card(self, icon: str, label: str, desc: str) -> QFrame:
        """
        Build one "ACTION N" choice card for the Turn Order section.

        Parameters
        ----------
        icon : str
            Emoji displayed at the top of the card.
        label : str
            All-caps action label (e.g. ``"ACTION 1"``).
        desc : str
            Short description of the action.

        Returns
        -------
        QFrame
            Centred, styled card widget.
        """
        card = QFrame()
        card.setObjectName("TurnActionCard")
        card.setMinimumHeight(120)
        card.setStyleSheet(
            "QFrame#TurnActionCard {"
            f"  background: {_C_SURF_DIM};"
            "  border: 1px solid rgba(71, 71, 65, 0.50);"
            "  border-radius: 2px;"
            "}"
            "QFrame#TurnActionCard:hover {"
            f"  border-color: {_C_OUTLINE};"
            "}"
        )

        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 28px; background: transparent;")
        cl.addWidget(icon_lbl)

        cap_font = font("label-caps")
        cap_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        cap_lbl = QLabel(label)
        cap_lbl.setFont(cap_font)
        cap_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap_lbl.setStyleSheet(f"color: {_C_PRIMARY}; background: transparent;")
        cl.addWidget(cap_lbl)

        desc_font = font("body-base")
        desc_font.setPointSize(11)
        desc_lbl = QLabel(desc)
        desc_lbl.setFont(desc_font)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {_C_ON_VARIANT}; background: transparent;")
        cl.addWidget(desc_lbl)
        return card

    # ------------------------------------------------------------------
    # Public lifecycle helper
    # ------------------------------------------------------------------

    def reset_scroll(self) -> None:
        """
        Reset the scroll position to the top.

        Called by ``NavigationController._push_rules()`` each time the Rules
        screen becomes visible so users always start at the Objective section.
        """
        if self._scroll is not None:
            self._scroll.verticalScrollBar().setValue(0)