"""
modern_app_template.py
======================
Template PySide6 — look "web app moderne" avec sidebar dark.

Architecture :
  - MainWindow          : fenêtre principale, charge le QSS
  - Sidebar             : navigation latérale (boutons checkables)
  - ContentStack        : QStackedWidget, une page par section
  - PageBase            : classe de base pour les pages
  - DashboardPage       : exemple de dashboard avec cards + table
  - SettingsPage        : exemple de page formulaire

Usage :
  python modern_app_template.py

Dépendances :
  pip install PySide6

Le fichier style_dark_sidebar.qss doit être dans le même répertoire.
"""

import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QStackedWidget, QSizePolicy,
    QScrollArea, QGridLayout, QLineEdit, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QCheckBox, QSlider,
    QSpacerItem
)
from PySide6.QtCore import Qt, QSize, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QFont, QColor


# ─────────────────────────────────────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────

def load_stylesheet(filename: str) -> str:
    """Charge un fichier QSS depuis le répertoire du script."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    qss_path = os.path.join(base_dir, filename)
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""  # Fonctionne sans le fichier QSS (style par défaut)


def make_separator() -> QFrame:
    """Retourne un séparateur horizontal fin."""
    sep = QFrame()
    sep.setObjectName("sidebar_separator")
    sep.setFrameShape(QFrame.Shape.HLine)
    return sep


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSANT : CARD
# ─────────────────────────────────────────────────────────────────────────────

class Card(QWidget):
    """Widget "card" générique — fond arrondi, titre + contenu."""

    def __init__(self, dark: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("card_dark" if dark else "card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(8)

    def add_widget(self, widget: QWidget):
        self._layout.addWidget(widget)

    def add_layout(self, layout):
        self._layout.addLayout(layout)


class StatCard(Card):
    """Card affichant une valeur chiffrée + libellé — style KPI dashboard."""

    def __init__(self, title: str, value: str, label: str = "", dark: bool = True, parent=None):
        super().__init__(dark=dark, parent=parent)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("card_title")

        value_lbl = QLabel(value)
        value_lbl.setObjectName("card_value")

        self.add_widget(title_lbl)
        self.add_widget(value_lbl)

        if label:
            sub_lbl = QLabel(label)
            sub_lbl.setObjectName("card_label")
            self.add_widget(sub_lbl)


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSANT : SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

class NavButton(QPushButton):
    """Bouton de navigation sidebar, checkable."""

    def __init__(self, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("nav_button")
        self.setCheckable(True)
        self.setText(f"  {icon_text}  {label}")
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class Sidebar(QWidget):
    """
    Barre de navigation latérale.
    Émet 'page_changed(int)' quand l'utilisateur clique sur un item.
    """

    page_changed = Signal(int)

    # Définition des pages : (icône unicode, libellé)
    NAV_ITEMS = [
        ("⊞", "Dashboard"),
        ("⊙", "Projets"),
        ("♪", "Médias"),
        ("✉", "Messages"),
        ("☆", "Favoris"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._buttons: list[NavButton] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Logo / titre de l'app ──────────────────────────
        title = QLabel("◈  MonApp")
        title.setObjectName("app_title")
        layout.addWidget(title)
        layout.addWidget(make_separator())
        layout.addSpacing(8)

        # ── Boutons de navigation ──────────────────────────
        for index, (icon, label) in enumerate(self.NAV_ITEMS):
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda checked, i=index: self._on_nav_click(i))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addSpacing(8)
        layout.addWidget(make_separator())

        # ── Spacer pour pousser les items du bas ──────────
        layout.addStretch()

        # ── Items en bas de sidebar ────────────────────────
        for icon, label in [("⚙", "Paramètres"), ("?", "Aide")]:
            idx = len(self._buttons)
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda checked, i=idx: self._on_nav_click(i))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addSpacing(12)

        # Activer le premier bouton par défaut
        if self._buttons:
            self._buttons[0].setChecked(True)

    def _on_nav_click(self, index: int):
        """Décoche tous les boutons sauf celui cliqué, émet le signal."""
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
        self.page_changed.emit(index)

    def set_active(self, index: int):
        self._on_nav_click(index)


# ─────────────────────────────────────────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────────────────────────────────────────

class PageBase(QWidget):
    """Classe de base pour toutes les pages de contenu."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        # Layout principal avec padding
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(0)

        # ── En-tête de page ───────────────────────────────
        title_lbl = QLabel(title)
        title_lbl.setObjectName("page_title")
        outer.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setObjectName("page_subtitle")
            outer.addWidget(sub_lbl)

        outer.addSpacing(24)

        # Zone de scroll pour le contenu
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._content_widget = QWidget()
        self.content_layout = QVBoxLayout(self._content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)

        scroll.setWidget(self._content_widget)
        outer.addWidget(scroll)


class DashboardPage(PageBase):
    """Page Dashboard : cards KPI + boutons + tableau exemple."""

    def __init__(self, parent=None):
        super().__init__(
            "Dashboard",
            "Vue d'ensemble de ton activité",
            parent
        )
        self._build()

    def _build(self):
        # ── Rangée de KPI cards ───────────────────────────
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        stats = [
            ("Projets", "12", "↑ 3 ce mois"),
            ("Fichiers", "284", "↑ 48 cette semaine"),
            ("Durée totale", "4h 32m", "Aujourd'hui"),
            ("Rendus", "7", "En attente : 2"),
        ]
        for title, value, label in stats:
            card = StatCard(title, value, label)
            cards_layout.addWidget(card)

        self.content_layout.addLayout(cards_layout)

        # ── Section avec boutons ──────────────────────────
        btn_card = Card(dark=True)
        btn_lbl = QLabel("Actions rapides")
        btn_lbl.setObjectName("card_title")
        btn_card.add_widget(btn_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        for label, name in [
            ("Nouveau projet", "btn_primary"),
            ("Importer", "btn_secondary"),
            ("Annuler", "btn_ghost"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_row.addWidget(btn)

        btn_row.addStretch()
        btn_card.add_layout(btn_row)
        self.content_layout.addWidget(btn_card)

        # ── Tableau exemple ───────────────────────────────
        table_card = Card(dark=False)
        table_lbl = QLabel("Projets récents")
        table_lbl.setObjectName("card_title")
        table_card.add_widget(table_lbl)

        table = QTableWidget(5, 4)
        table.setHorizontalHeaderLabels(["Nom", "Statut", "Durée", "Date"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setMinimumHeight(180)

        sample_data = [
            ("Voyage en Bretagne", "✅ Terminé", "2 min 30s", "2026-04-10"),
            ("Portrait famille", "⏳ En cours", "45s", "2026-04-12"),
            ("Anniversaire Jules", "✅ Terminé", "1 min 15s", "2026-04-08"),
            ("Vacances 2025", "⚙ Rendu", "3 min 05s", "2026-04-14"),
            ("Test générique", "✏ Brouillon", "—", "2026-04-15"),
        ]
        for row, (name, status, duration, date) in enumerate(sample_data):
            for col, text in enumerate([name, status, duration, date]):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                table.setItem(row, col, item)

        table_card.add_widget(table)
        self.content_layout.addWidget(table_card)

        # ── Barre de progression exemple ──────────────────
        prog_card = Card(dark=True)
        prog_card.add_widget(QLabel("Stockage utilisé"))

        prog_bar = QProgressBar()
        prog_bar.setValue(67)
        prog_bar.setTextVisible(False)
        prog_bar.setMaximumHeight(8)
        prog_card.add_widget(prog_bar)

        prog_lbl = QLabel("6.7 Go / 10 Go utilisés")
        prog_lbl.setObjectName("label_secondary")
        prog_card.add_widget(prog_lbl)

        self.content_layout.addWidget(prog_card)
        self.content_layout.addStretch()


class GenericPage(PageBase):
    """Page générique — placeholder pour les sections non implémentées."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(title, subtitle, parent)

        card = Card(dark=True)
        msg = QLabel(f"Section « {title} » — à implémenter")
        msg.setObjectName("label_secondary")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.add_widget(msg)

        self.content_layout.addWidget(card)
        self.content_layout.addStretch()


class SettingsPage(PageBase):
    """Page Paramètres — exemple de formulaire structuré."""

    def __init__(self, parent=None):
        super().__init__("Paramètres", "Configuration de l'application", parent)
        self._build()

    def _build(self):
        # ── Profil ────────────────────────────────────────
        card = Card(dark=True)
        card.add_widget(self._section_label("Profil"))

        for label_text, placeholder in [
            ("Nom", "Ton nom"),
            ("Email", "ton@email.com"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(100)
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            row.addWidget(lbl)
            row.addWidget(field)
            card.add_layout(row)

        self.content_layout.addWidget(card)

        # ── Préférences ───────────────────────────────────
        card2 = Card(dark=False)
        card2.add_widget(self._section_label("Préférences"))

        cb = QCheckBox("Activer les notifications")
        card2.add_widget(cb)

        combo_row = QHBoxLayout()
        combo_lbl = QLabel("Thème")
        combo_lbl.setFixedWidth(100)
        combo = QComboBox()
        combo.addItems(["Dark (défaut)", "Light", "Auto"])
        combo_row.addWidget(combo_lbl)
        combo_row.addWidget(combo)
        combo_row.addStretch()
        card2.add_layout(combo_row)

        slider_row = QHBoxLayout()
        slider_lbl = QLabel("Volume")
        slider_lbl.setFixedWidth(100)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(75)
        slider.setMaximumWidth(200)
        slider_row.addWidget(slider_lbl)
        slider_row.addWidget(slider)
        slider_row.addStretch()
        card2.add_layout(slider_row)

        self.content_layout.addWidget(card2)

        # ── Actions ───────────────────────────────────────
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Sauvegarder")
        save_btn.setObjectName("btn_primary")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.setObjectName("btn_ghost")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        self.content_layout.addLayout(btn_row)
        self.content_layout.addStretch()

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("card_title")
        return lbl


# ─────────────────────────────────────────────────────────────────────────────
# FENÊTRE PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """
    Fenêtre principale.
    Structure : Sidebar (gauche) | ContentStack (droite)
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MonApp — Template PySide6")
        self.resize(1200, 750)
        self.setMinimumSize(800, 560)

        # Charger le stylesheet
        qss = load_stylesheet("style_dark_sidebar.qss")
        if qss:
            self.setStyleSheet(qss)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central_widget")
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────
        self._sidebar = Sidebar()
        self._sidebar.page_changed.connect(self._switch_page)
        main_layout.addWidget(self._sidebar)

        # ── Stack des pages ───────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setObjectName("content_area")

        # Pages dans le même ordre que Sidebar.NAV_ITEMS + items du bas
        self._pages = [
            DashboardPage(),
            GenericPage("Projets", "Gestion de tes projets vidéo"),
            GenericPage("Médias", "Bibliothèque de fichiers médias"),
            GenericPage("Messages", "Notifications et journal"),
            GenericPage("Favoris", "Éléments marqués"),
            SettingsPage(),
            GenericPage("Aide", "Documentation et support"),
        ]

        for page in self._pages:
            self._stack.addWidget(page)

        main_layout.addWidget(self._stack)

    def _switch_page(self, index: int):
        if index < self._stack.count():
            self._stack.setCurrentIndex(index)


# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)

    # Police par défaut (optionnel)
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
