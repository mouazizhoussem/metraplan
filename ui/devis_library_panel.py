# ui/devis_library_panel.py
"""
Panneau Bibliothèque de Devis — onglet "Devis" du ruban.

Permet de visualiser, éditer, importer et sauvegarder
la bibliothèque de lots/items du devis.

Disposition :
  ┌────────────────────────────────────────────────────────────┐
  │ [+ Lot] [+ Item] [✏ Renommer] [🗑 Supprimer]  │  [💾 Modèle] [📂 Import Excel] [📤 Exporter] │
  ├────────────────────────────────────────────────────────────┤
  │  QTreeWidget éditable                                      │
  │  ▼ 01 – Terrassement                    ← lot             │
  │      01.01  Décapage terre végétale  m² ← item            │
  │  ▼ 04 – Maçonnerie  [custom]                              │
  │      04.C01  Brique personnalisée    m² [custom]          │
  └────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from typing import Optional, List

from PyQt5.QtCore import Qt, QTimer, QRect, QPoint
from PyQt5.QtGui import QFont, QColor, QBrush, QIcon, QPixmap, QPainter, QPen
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QFrame, QFileDialog, QMessageBox,
    QInputDialog, QComboBox, QMenu, QAction, QAbstractItemView,
    QHeaderView, QSplitter, QDialog, QFormLayout, QLineEdit,
    QDialogButtonBox, QRadioButton, QButtonGroup, QScrollArea,
    QSizePolicy,
)

from core.devis_manager import DevisManager, DevisLot, DevisItem


# ── Constantes visuelles ──────────────────────────────────────────────────────

_COL_HEADER = "#e3f2fd"
_COL_LOT     = "#dde8f5"
_COL_CUSTOM  = "#fff8e1"
_COL_TEXT_LOT = "#0d47a1"
_COL_TEXT_ITEM = "#2a3a5a"
_COL_CUSTOM_BADGE = "#e65100"

_UNITS = ["m²", "m³", "ml", "m", "U", "kg", "t", "ens.", "forfait"]


# ── QTreeWidget avec drag & drop contrôlé ────────────────────────────────────

class _ImportTree(QTreeWidget):
    """
    QTreeWidget spécialisé pour la prévisualisation d'import.
    Règles de déplacement :
      • Un ITEM (enfant) peut être glissé vers n'importe quel LOT.
      • Un LOT (racine) peut être réordonné parmi les autres lots.
      • Les items ne peuvent pas devenir des racines.
      • Les lots ne peuvent pas être imbriqués dans d'autres lots.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    def dropEvent(self, event):
        dragged = self.currentItem()
        if dragged is None:
            event.ignore()
            return

        target = self.itemAt(event.pos())
        drop_pos = self.dropIndicatorPosition()   # OnItem / AboveItem / BelowItem / OnViewport

        from PyQt5.QtWidgets import QAbstractItemView as _AIV

        dragged_is_lot  = dragged.parent() is None
        target_is_lot   = (target is not None) and (target.parent() is None)
        target_is_item  = (target is not None) and (target.parent() is not None)
        target_is_root  = target is None   # drop sur zone vide

        # ── Lot glissé ────────────────────────────────────────────────────────
        if dragged_is_lot:
            if target_is_root or target_is_lot:
                # Réordonner les lots — déplacement au niveau racine
                root = self.invisibleRootItem()
                idx  = root.indexOfChild(dragged)
                root.takeChild(idx)
                if target is None or drop_pos == _AIV.BelowItem:
                    dest = root.childCount() if target is None \
                           else root.indexOfChild(target) + 1
                else:
                    dest = root.indexOfChild(target) if target else 0
                root.insertChild(dest, dragged)
                self.setCurrentItem(dragged)
                event.accept()
                return
            else:
                event.ignore()
                return

        # ── Item glissé ───────────────────────────────────────────────────────
        if not dragged_is_lot:
            # Trouver le lot de destination
            if target_is_lot:
                dest_lot = target
            elif target_is_item:
                dest_lot = target.parent()
            else:
                event.ignore()
                return

            src_lot = dragged.parent()
            if src_lot is None:
                event.ignore()
                return

            # Retirer l'item de son lot source
            src_idx = src_lot.indexOfChild(dragged)
            src_lot.takeChild(src_idx)

            # Insérer dans le lot destination
            if target_is_lot:
                dest_lot.addChild(dragged)
            else:
                dest_idx = dest_lot.indexOfChild(target)
                if drop_pos == _AIV.BelowItem:
                    dest_idx += 1
                dest_lot.insertChild(dest_idx, dragged)

            dest_lot.setExpanded(True)
            self.setCurrentItem(dragged)
            # Mettre à jour le compteur d'articles du lot
            self._refresh_lot_counts(src_lot)
            self._refresh_lot_counts(dest_lot)
            event.accept()
            return

        event.ignore()

    def _refresh_lot_counts(self, lot_node: "QTreeWidgetItem"):
        """Met à jour le compteur affiché dans la colonne 2 du lot."""
        if lot_node:
            lot_node.setText(2, f"{lot_node.childCount()} article(s)")


# ── QTreeWidget du panneau Devis avec drag & drop persisté ───────────────────

class _DevisLibTree(QTreeWidget):
    """
    QTreeWidget principal du panneau Devis avec drag & drop.
    Stratégie : intercepter le drop, appliquer le changement dans
    DevisManager, puis laisser devis_structure_changed reconstruire
    l'arbre proprement (pas de manipulation visuelle manuelle).
    """

    def __init__(self, dm, parent=None):
        super().__init__(parent)
        self._dm = dm
        self._dragged_item  = None
        self._drop_line_pos = None   # (y: int, x1: int, x2: int) ou None
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)   # on dessine le nôtre
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    # ── Dessin de la ligne d'indicateur ──────────────────────────────────────

    def _compute_drop_line(self, event) -> tuple:
        """
        Retourne (y, x1, x2, label) où tracer la ligne bleue, ou None.
        label est utilisé pour le feedback visuel (au-dessus / en-dessous / dans).
        """
        target   = self.itemAt(event.pos())
        dragged  = self._dragged_item or self.currentItem()
        if not dragged or not target or target is dragged:
            return None

        d_data = dragged.data(0, Qt.UserRole)
        t_data = target.data(0, Qt.UserRole)
        if not d_data or not t_data:
            return None

        dragged_is_lot = d_data[0] == "lot"
        target_is_lot  = t_data[0] == "lot"
        target_is_item = t_data[0] == "item"

        if dragged_is_lot and not target_is_lot:
            return None

        vp   = self.viewport()
        rect = self.visualItemRect(target)
        x1   = rect.left() + 4
        x2   = vp.width() - 4
        drop_pos = self.dropIndicatorPosition()

        from PyQt5.QtWidgets import QAbstractItemView as _AIV
        if drop_pos == _AIV.AboveItem:
            y = rect.top()
        elif drop_pos == _AIV.BelowItem:
            y = rect.bottom()
        else:
            # OnItem : ligne en bas pour les lots, en bas pour les items
            y = rect.bottom()

        return (y, x1, x2)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drop_line_pos:
            y, x1, x2 = self._drop_line_pos
            painter = QPainter(self.viewport())
            pen = QPen(QColor("#1565c0"), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawLine(x1, y, x2, y)
            # Petit cercle au début de la ligne (style Windows Explorer)
            painter.setBrush(QColor("#1565c0"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(x1, y), 4, 4)
            painter.end()

    # ── Drag events ──────────────────────────────────────────────────────────

    def startDrag(self, actions):
        self._dragged_item  = self.currentItem()
        self._drop_line_pos = None
        # On supporte Copy ET Move : notre dropEvent fixe l'action à CopyAction
        # pour empêcher Qt de supprimer l'item source automatiquement.
        super().startDrag(Qt.CopyAction | Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.source() is self:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        target  = self.itemAt(event.pos())
        dragged = self._dragged_item or self.currentItem()

        if not dragged or not target or target is dragged:
            self._drop_line_pos = None
            self.viewport().update()
            event.ignore()
            return

        d_data = dragged.data(0, Qt.UserRole)
        t_data = target.data(0, Qt.UserRole)
        if not d_data or not t_data:
            self._drop_line_pos = None
            self.viewport().update()
            event.ignore()
            return

        dragged_is_lot = d_data[0] == "lot"
        target_is_lot  = t_data[0] == "lot"

        if dragged_is_lot and not target_is_lot:
            self._drop_line_pos = None
            self.viewport().update()
            event.ignore()
            return

        line = self._compute_drop_line(event)
        self._drop_line_pos = line
        self.viewport().update()
        event.accept()

    def dragLeaveEvent(self, event):
        self._drop_line_pos = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        from PyQt5.QtWidgets import QAbstractItemView as _AIV

        # Effacer la ligne bleue immédiatement
        self._drop_line_pos = None
        self.viewport().update()

        dragged = self._dragged_item or self.currentItem()
        self._dragged_item = None
        target  = self.itemAt(event.pos())

        if not dragged or not target or target is dragged:
            event.ignore()
            return

        d_data = dragged.data(0, Qt.UserRole)
        t_data = target.data(0, Qt.UserRole)
        if not d_data or not t_data:
            event.ignore()
            return

        drop_pos       = self.dropIndicatorPosition()
        dragged_is_lot = d_data[0] == "lot"
        target_is_lot  = t_data[0] == "lot"
        target_is_item = t_data[0] == "item"

        # ── Lot → réordonner ─────────────────────────────────────────────────
        if dragged_is_lot:
            if not target_is_lot:
                event.ignore()
                return
            root     = self.invisibleRootItem()
            src_idx  = root.indexOfChild(dragged)
            dest_idx = root.indexOfChild(target)
            if drop_pos == _AIV.BelowItem:
                dest_idx += 1
            if src_idx == dest_idx:
                event.ignore()
                return
            self._dm.reorder_lot(d_data[1], dest_idx)
            # CopyAction : empêche Qt de supprimer lui-même l'item source
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return

        # ── Item → déplacer vers un autre lot ────────────────────────────────
        if not dragged_is_lot:
            src_lot_id  = d_data[1]
            item_id     = d_data[2] if len(d_data) > 2 else None
            if not item_id:
                event.ignore()
                return

            if target_is_lot:
                dest_lot_id = t_data[1]
                dest_idx    = -1
            elif target_is_item:
                dest_lot_id  = t_data[1]
                dest_item_id = t_data[2]
                dest_lot_obj = self._dm.get_lot(dest_lot_id)
                if dest_lot_obj:
                    ids = [it.id for it in dest_lot_obj.items]
                    if dest_item_id in ids:
                        dest_idx = ids.index(dest_item_id)
                        if drop_pos == _AIV.BelowItem:
                            dest_idx += 1
                    else:
                        dest_idx = -1
                else:
                    dest_idx = -1
            else:
                event.ignore()
                return

            self._dm.move_item_to_lot(item_id, src_lot_id, dest_lot_id, dest_idx)
            # CopyAction : empêche Qt de supprimer lui-même l'item source
            # après que DevisManager + _refresh_tree l'ont déjà retiré/réinséré
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return

        event.ignore()


# ── Dialogue de prévisualisation d'import ────────────────────────────────────

class ImportPreviewDialog(QDialog):
    """
    Dialogue affiché après l'analyse du fichier Excel.
    Montre un arbre interactif de tous les lots et articles détectés.
    L'utilisateur peut :
      • cocher/décocher chaque lot et chaque article individuellement
      • choisir entre fusionner ou remplacer la bibliothèque existante
      • confirmer ou annuler l'import
    """

    def __init__(self, lots: List[DevisLot], msg: str, parent=None):
        super().__init__(parent)
        self._lots = lots
        self.setWindowTitle("Prévisualisation de l'import Excel")
        self.setMinimumSize(720, 540)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 10)

        # ── Message de résumé ─────────────────────────────────────────────────
        lbl_msg = QLabel(msg)
        lbl_msg.setStyleSheet(
            "font-size:12px; color:#1b5e20; font-weight:bold; padding:4px 0;")
        lbl_msg.setWordWrap(True)
        root.addWidget(lbl_msg)

        # Bandeau d'aide double
        hints_frame = QFrame()
        hints_frame.setStyleSheet(
            "QFrame { background:#fff8e1; border:1px solid #ffe082; border-radius:4px; }")
        hints_layout = QHBoxLayout(hints_frame)
        hints_layout.setContentsMargins(10, 5, 10, 5)
        hints_layout.setSpacing(16)
        for txt in [
            "☑  Cochez / décochez les lots et articles",
            "🖱  Glissez un article vers un autre lot pour le déplacer",
            "↕  Glissez un lot pour le réordonner",
        ]:
            lbl = QLabel(txt)
            lbl.setStyleSheet("font-size:11px; color:#5d4037;")
            hints_layout.addWidget(lbl)
        hints_layout.addStretch()
        root.addWidget(hints_frame)

        # ── Arbre de prévisualisation ─────────────────────────────────────────
        self._tree = _ImportTree()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["N°  /  Désignation", "Unité", "Articles"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._tree.setAlternatingRowColors(False)
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(20)
        self._tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #c8d4e8; border-radius:4px;
                background:#ffffff; font-size:12px;
            }
            QTreeWidget::item { padding:3px 4px; }
            QTreeWidget::item:selected { background:#bbdefb; color:#0d47a1; }
            QTreeWidget::item:hover { background:#e3f2fd; }
            QHeaderView::section {
                background:#e3f2fd; color:#0d47a1; font-weight:bold;
                font-size:11px; border:none; border-right:1px solid #c8d4e8;
                padding:4px 6px;
            }
        """)
        self._tree.itemChanged.connect(self._on_item_changed)

        lot_font  = QFont(); lot_font.setBold(True); lot_font.setPointSize(11)
        item_font = QFont(); item_font.setPointSize(10)
        sub_font  = QFont(); sub_font.setPointSize(9); sub_font.setItalic(True)

        self._blocking = False
        for lot in lots:
            lot_node = QTreeWidgetItem(self._tree)
            lot_node.setText(0, f"  {lot.id}  –  {lot.label}")
            lot_node.setText(2, f"{len(lot.items)} article(s)")
            lot_node.setFont(0, lot_font)
            lot_node.setForeground(0, QBrush(QColor("#0d47a1")))
            lot_node.setBackground(0, QBrush(QColor("#dde8f5")))
            lot_node.setBackground(1, QBrush(QColor("#dde8f5")))
            lot_node.setBackground(2, QBrush(QColor("#dde8f5")))
            lot_node.setCheckState(0, Qt.Checked)
            lot_node.setData(0, Qt.UserRole, ("lot", lot))
            lot_node.setExpanded(True)

            for it in lot.items:
                is_sub = it.label.startswith("  ")
                it_node = QTreeWidgetItem(lot_node)
                it_node.setText(0, f"      {it.id}   {it.label.strip()}")
                it_node.setText(1, it.unit)
                it_node.setFont(0, sub_font if is_sub else item_font)
                it_node.setForeground(0, QBrush(QColor(
                    "#7b1fa2" if is_sub else "#333333")))
                if is_sub:
                    it_node.setForeground(0, QBrush(QColor("#7b1fa2")))
                it_node.setCheckState(0, Qt.Checked)
                it_node.setData(0, Qt.UserRole, ("item", it))

        root.addWidget(self._tree, 1)

        # ── Boutons Tout cocher / Tout décocher ───────────────────────────────
        row_check = QHBoxLayout()
        for label, state in [("✅  Tout sélectionner", Qt.Checked),
                              ("☐  Tout désélectionner", Qt.Unchecked)]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setStyleSheet(
                "QPushButton { border:1px solid #b0c4de; border-radius:4px; "
                "padding:2px 10px; font-size:11px; background:#eef2fa; }"
                "QPushButton:hover { background:#d0e4ff; }")
            btn.clicked.connect(lambda _, s=state: self._check_all(s))
            row_check.addWidget(btn)
        row_check.addStretch()
        root.addLayout(row_check)

        # ── Mode d'import ─────────────────────────────────────────────────────
        mode_frame = QFrame()
        mode_frame.setStyleSheet(
            "QFrame { background:#f5f5f5; border:1px solid #ddd; border-radius:4px; }")
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(12, 6, 12, 6)
        mode_layout.addWidget(QLabel("Mode d'import :"))
        self._rb_merge   = QRadioButton("Fusionner avec la bibliothèque existante")
        self._rb_replace = QRadioButton("Remplacer toute la bibliothèque")
        self._rb_merge.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._rb_merge)
        grp.addButton(self._rb_replace)
        mode_layout.addWidget(self._rb_merge)
        mode_layout.addWidget(self._rb_replace)
        mode_layout.addStretch()
        root.addWidget(mode_frame)

        # ── Boutons OK / Annuler ──────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Importer la sélection")
        btns.button(QDialogButtonBox.Ok).setStyleSheet(
            "QPushButton { background:#1976d2; color:white; border-radius:4px; "
            "padding:5px 16px; font-weight:bold; }"
            "QPushButton:hover { background:#1565c0; }")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── Logique de cochage ────────────────────────────────────────────────────

    def _on_item_changed(self, node: QTreeWidgetItem, col: int):
        if col != 0 or self._blocking:
            return
        self._blocking = True
        data = node.data(0, Qt.UserRole)
        if data and data[0] == "lot":
            # Propager à tous les enfants
            state = node.checkState(0)
            for i in range(node.childCount()):
                node.child(i).setCheckState(0, state)
        elif data and data[0] == "item":
            # Mettre à jour l'état du lot parent
            parent = node.parent()
            if parent:
                states = {parent.child(i).checkState(0)
                          for i in range(parent.childCount())}
                if states == {Qt.Checked}:
                    parent.setCheckState(0, Qt.Checked)
                elif states == {Qt.Unchecked}:
                    parent.setCheckState(0, Qt.Unchecked)
                else:
                    parent.setCheckState(0, Qt.PartiallyChecked)
        self._blocking = False

    def _check_all(self, state):
        self._blocking = True
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            lot_node = root.child(i)
            lot_node.setCheckState(0, state)
            for j in range(lot_node.childCount()):
                lot_node.child(j).setCheckState(0, state)
        self._blocking = False

    # ── Résultat ──────────────────────────────────────────────────────────────

    def get_selected_lots(self) -> List[DevisLot]:
        """
        Retourne les lots/items tels qu'ils apparaissent dans l'arbre
        après les éventuels déplacements par drag & drop.
        Seuls les éléments cochés sont inclus.
        """
        from core.devis_manager import DevisLot, DevisItem
        result = []
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            lot_node = root.child(i)
            if lot_node.checkState(0) == Qt.Unchecked:
                continue
            orig_lot = lot_node.data(0, Qt.UserRole)[1]
            new_lot  = DevisLot(id=orig_lot.id, label=orig_lot.label,
                                is_custom=True)
            for j in range(lot_node.childCount()):
                it_node = lot_node.child(j)
                if it_node.checkState(0) == Qt.Checked:
                    # L'item peut avoir été déplacé depuis un autre lot
                    orig_item = it_node.data(0, Qt.UserRole)[1]
                    new_lot.items.append(orig_item)
            # Inclure le lot même s'il n'a plus d'items (lot vide accepté)
            result.append(new_lot)
        return result

    @property
    def merge(self) -> bool:
        return self._rb_merge.isChecked()


# ── Widget principal ──────────────────────────────────────────────────────────

class DevisLibraryPanel(QWidget):
    """
    Panneau de gestion de la bibliothèque de devis.
    Connecté à DevisManager via le signal devis_structure_changed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dm = DevisManager.instance()
        self._last_sel = None   # mémorise la sélection même si focus perdu
        self._dm.devis_structure_changed.connect(self._on_library_changed)
        self._build_ui()
        self._refresh_tree()

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Barre d'outils haute
        root.addWidget(self._build_toolbar())

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:#c8d4e8; border:none; max-height:1px;")
        root.addWidget(sep)

        # Zone principale
        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(8, 8, 8, 8)
        bv.setSpacing(6)

        # Aide
        hint = QLabel(
            "Double-cliquez sur un lot ou un item pour le renommer. "
            "Clic droit pour plus d'options."
        )
        hint.setStyleSheet("font-size:10px; color:#78909c; font-style:italic;")
        bv.addWidget(hint)

        # Bandeau drag & drop
        dnd_hint = QLabel(
            "🖱  Glissez un article vers un autre lot · "
            "Glissez un lot pour le réordonner")
        dnd_hint.setStyleSheet(
            "font-size:10px; color:#5d4037; background:#fff8e1;"
            "border:1px solid #ffe082; border-radius:3px; padding:3px 8px;")
        bv.addWidget(dnd_hint)

        # Arbre avec drag & drop
        self._tree = _DevisLibTree(self._dm)
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Désignation", "Unité", "Type"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(20)
        self._tree.setAlternatingRowColors(False)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.currentItemChanged.connect(self._on_tree_selection_changed)
        self._tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #c8d4e8;
                border-radius: 4px;
                font-size: 12px;
                background: #ffffff;
            }
            QTreeWidget::item { padding: 3px 4px; }
            QTreeWidget::item:selected { background: #bbdefb; color: #0d47a1; }
            QTreeWidget::item:hover    { background: #e3f2fd; }
            QTreeView::drop-indicator  { background: #1976d2; height: 2px; }
            QHeaderView::section {
                background: #e3f2fd; color: #0d47a1;
                font-weight: bold; font-size: 11px;
                border: none; border-right: 1px solid #c8d4e8;
                padding: 4px 6px;
            }
        """)
        bv.addWidget(self._tree, 1)

        # Barre de statut bas
        self._status = QLabel("")
        self._status.setStyleSheet(
            "font-size:11px; color:#607080; padding:4px 8px;"
            "border-top:1px solid #c8d4e8;")
        bv.addWidget(self._status)

        root.addWidget(body, 1)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet("background:#dde3ee; border-bottom:1px solid #c8d4e8;")
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(4)

        btn_qss = """
        QPushButton {
            border: 1px solid #b0c4de; border-radius: 5px;
            padding: 4px 10px; font-size: 12px;
            color: #2a3a5a; background: #eef2fa; min-width: 80px;
        }
        QPushButton:hover   { background: #d0e4ff; border-color: #1976d2; }
        QPushButton:pressed { background: #bbdefb; }
        """
        green_qss = btn_qss.replace("#eef2fa", "#e8f5e9").replace(
            "#2a3a5a", "#1b5e20").replace("#d0e4ff", "#c8e6c9").replace(
            "#bbdefb", "#a5d6a7")
        red_qss = btn_qss.replace("#eef2fa", "#ffebee").replace(
            "#2a3a5a", "#b71c1c").replace("#d0e4ff", "#ffcdd2").replace(
            "#bbdefb", "#ef9a9a")
        amber_qss = btn_qss.replace("#eef2fa", "#fff8e1").replace(
            "#2a3a5a", "#e65100").replace("#d0e4ff", "#ffe082").replace(
            "#bbdefb", "#ffd54f")

        self._btn_add_lot = QPushButton("➕ Lot")
        self._btn_add_lot.setStyleSheet(green_qss)
        self._btn_add_lot.setToolTip("Ajouter un nouveau lot")
        self._btn_add_lot.clicked.connect(self._add_lot)
        h.addWidget(self._btn_add_lot)

        self._btn_add_item = QPushButton("➕ Item")
        self._btn_add_item.setStyleSheet(green_qss)
        self._btn_add_item.setToolTip("Ajouter un item au lot sélectionné")
        self._btn_add_item.clicked.connect(self._add_item)
        h.addWidget(self._btn_add_item)

        self._btn_rename = QPushButton("✏ Renommer")
        self._btn_rename.setStyleSheet(btn_qss)
        self._btn_rename.setToolTip("Renommer le lot ou l'item sélectionné")
        self._btn_rename.clicked.connect(self._rename_selected)
        h.addWidget(self._btn_rename)

        self._btn_delete = QPushButton("🗑 Supprimer")
        self._btn_delete.setStyleSheet(red_qss)
        self._btn_delete.setToolTip("Supprimer le lot ou l'item sélectionné")
        self._btn_delete.clicked.connect(self._delete_selected)
        h.addWidget(self._btn_delete)

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color:#b0c4de; max-width:1px; margin:4px 6px;")
        h.addWidget(sep)

        self._btn_import = QPushButton("📂 Import Excel")
        self._btn_import.setStyleSheet(amber_qss)
        self._btn_import.setToolTip("Importer des lots/items depuis un fichier Excel (.xlsx)")
        self._btn_import.clicked.connect(self._import_excel)
        h.addWidget(self._btn_import)

        self._btn_load = QPushButton("📁 Charger modèle")
        self._btn_load.setStyleSheet(btn_qss)
        self._btn_load.setToolTip("Charger un modèle de devis (.devis ou .json)")
        self._btn_load.clicked.connect(self._load_model)
        h.addWidget(self._btn_load)

        self._btn_save = QPushButton("💾 Enregistrer")
        self._btn_save.setStyleSheet(btn_qss)
        self._btn_save.setToolTip("Enregistrer comme modèle par défaut")
        self._btn_save.clicked.connect(self._save_model)
        h.addWidget(self._btn_save)

        self._btn_export = QPushButton("📤 Exporter")
        self._btn_export.setStyleSheet(btn_qss)
        self._btn_export.setToolTip("Exporter la bibliothèque dans un fichier .devis")
        self._btn_export.clicked.connect(self._export_model)
        h.addWidget(self._btn_export)

        h.addStretch()

        self._lbl_counts = QLabel("")
        self._lbl_counts.setStyleSheet("font-size:11px; color:#607080;")
        h.addWidget(self._lbl_counts)

        return bar

    # ── Peuplement de l'arbre ─────────────────────────────────────────────────

    def _refresh_tree(self):
        # Sauvegarder la sélection courante pour la restaurer après rebuild
        saved_sel = self._last_sel or self._current_selection()
        self._tree.blockSignals(True)
        self._tree.clear()

        bold_lot  = QFont(); bold_lot.setBold(True); bold_lot.setPointSize(11)
        small     = QFont(); small.setPointSize(10)
        badge_font = QFont(); badge_font.setPointSize(8); badge_font.setItalic(True)

        for lot in self._dm.lots:
            lot_item = QTreeWidgetItem(self._tree)
            lot_item.setText(0, f"  {lot.id} – {lot.label}")
            lot_item.setText(1, "")
            lot_item.setText(2, "Custom" if lot.is_custom else "Standard")
            lot_item.setFont(0, bold_lot)
            lot_item.setForeground(0, QBrush(QColor(_COL_TEXT_LOT)))
            if lot.is_custom:
                lot_item.setBackground(0, QBrush(QColor(_COL_CUSTOM)))
                lot_item.setForeground(2, QBrush(QColor(_COL_CUSTOM_BADGE)))
            else:
                lot_item.setBackground(0, QBrush(QColor(_COL_LOT)))
            lot_item.setData(0, Qt.UserRole, ("lot", lot.id))
            lot_item.setExpanded(True)

            for it in lot.items:
                it_item = QTreeWidgetItem(lot_item)
                it_item.setText(0, f"    {it.id}   {it.label}")
                it_item.setText(1, it.unit)
                it_item.setText(2, "Custom" if it.is_custom else "")
                it_item.setFont(0, small)
                it_item.setForeground(0, QBrush(QColor(_COL_TEXT_ITEM)))
                if it.is_custom:
                    it_item.setBackground(0, QBrush(QColor("#fffde7")))
                    it_item.setForeground(2, QBrush(QColor(_COL_CUSTOM_BADGE)))
                it_item.setData(0, Qt.UserRole, ("item", lot.id, it.id))

        # Restaurer la sélection après le rebuild
        if saved_sel:
            self._restore_selection(saved_sel)

        self._tree.blockSignals(False)
        n_lots  = len(self._dm.lots)
        n_items = sum(len(l.items) for l in self._dm.lots)
        self._lbl_counts.setText(f"{n_lots} lot(s)  ·  {n_items} item(s)")

    # ── Sélection courante ────────────────────────────────────────────────────

    def _restore_selection(self, sel_data: tuple):
        """Remet en surbrillance l'item correspondant à sel_data après un rebuild."""
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            lot_node = root.child(i)
            lot_d = lot_node.data(0, Qt.UserRole)
            if sel_data[0] == "lot" and lot_d and lot_d[1] == sel_data[1]:
                self._tree.setCurrentItem(lot_node)
                return
            for j in range(lot_node.childCount()):
                it_node = lot_node.child(j)
                it_d = it_node.data(0, Qt.UserRole)
                if (sel_data[0] == "item" and it_d
                        and it_d[1] == sel_data[1] and it_d[2] == sel_data[2]):
                    self._tree.setCurrentItem(it_node)
                    return

    def _on_tree_selection_changed(self, current, _previous):
        """Mémorise la sélection dès qu'elle change dans l'arbre."""
        if current:
            data = current.data(0, Qt.UserRole)
            if data:
                self._last_sel = data

    def _current_selection(self):
        """
        Retourne (type, lot_id, item_id) ou None.
        Utilise _last_sel pour rester fiable même si l'arbre a perdu
        le focus lors du clic sur un bouton de la barre d'outils.
        """
        # Essayer d'abord l'item courant du widget
        sel = self._tree.currentItem()
        if sel:
            data = sel.data(0, Qt.UserRole)
            if data:
                self._last_sel = data
                return data
        # Fallback : dernière sélection mémorisée
        return self._last_sel

    # ── Dialogues personnalisés ───────────────────────────────────────────────

    def _next_lot_id(self) -> str:
        """Retourne le prochain identifiant de lot disponible."""
        existing = set()
        for lot in self._dm.lots:
            try:
                existing.add(int(lot.id))
            except ValueError:
                pass
        n = 1
        while n in existing:
            n += 1
        return str(n).zfill(2)

    def _next_item_suffix(self, lot_id: str) -> str:
        """Retourne le prochain suffixe disponible pour un lot donné."""
        lot = self._dm.get_lot(lot_id)
        if not lot:
            return "01"
        existing = set()
        prefix = f"{lot_id}."
        for it in lot.items:
            if it.id.startswith(prefix):
                suffix = it.id[len(prefix):]
                try:
                    existing.add(int(suffix))
                except ValueError:
                    pass
        n = 1
        while n in existing:
            n += 1
        return str(n).zfill(2)

    def _show_add_lot_dialog(self) -> tuple:
        """Dialogue de création d'un lot avec ID suggéré."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Nouveau lot")
        dlg.setFixedWidth(360)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        form = QFormLayout(dlg)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 8)

        next_id = self._next_lot_id()
        ed_id = QLineEdit(next_id)
        ed_id.setPlaceholderText("ex : 18")
        ed_id.setMaximumWidth(80)
        form.addRow("N° du lot :", ed_id)

        ed_label = QLineEdit()
        ed_label.setPlaceholderText("ex : Menuiserie extérieure")
        form.addRow("Nom du lot :", ed_label)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Ajouter")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        ed_label.setFocus()
        if dlg.exec_() != QDialog.Accepted:
            return "", ""
        return ed_id.text().strip(), ed_label.text().strip()

    def _show_add_item_dialog(self, lot_id: str) -> tuple:
        """
        Dialogue de création d'un item.
        Affiche le préfixe du lot fixe et demande uniquement le suffixe.
        """
        lot = self._dm.get_lot(lot_id)
        lot_label = lot.label if lot else lot_id

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Ajouter un item — Lot {lot_id} – {lot_label}")
        dlg.setFixedWidth(440)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        form = QFormLayout(dlg)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 8)

        # Ligne N° : préfixe fixe + suffixe éditable
        suffix_default = self._next_item_suffix(lot_id)
        row_id = QHBoxLayout()
        lbl_prefix = QLabel(f"<b>{lot_id}.</b>")
        lbl_prefix.setStyleSheet("font-size:13px; color:#0d47a1;")
        ed_suffix = QLineEdit(suffix_default)
        ed_suffix.setPlaceholderText("01")
        ed_suffix.setMaximumWidth(70)
        row_id.addWidget(lbl_prefix)
        row_id.addWidget(ed_suffix)
        row_id.addStretch()
        form.addRow("N° de l'item :", row_id)

        ed_label = QLineEdit()
        ed_label.setPlaceholderText("ex : Porte métallique 2 vantaux")
        form.addRow("Désignation :", ed_label)

        combo_unit = QComboBox()
        combo_unit.addItems(_UNITS)
        combo_unit.setEditable(True)
        form.addRow("Unité :", combo_unit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Ajouter")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        ed_label.setFocus()
        if dlg.exec_() != QDialog.Accepted:
            return "", "", ""

        suffix  = ed_suffix.text().strip()
        full_id = f"{lot_id}.{suffix}" if suffix else ""
        label   = ed_label.text().strip()
        unit    = combo_unit.currentText().strip()
        return full_id, label, unit

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_lot(self):
        # Déterminer après quel lot insérer selon la sélection courante
        sel = self._current_selection()
        if sel and sel[0] == "lot":
            after_lot = sel[1]
        elif sel and sel[0] == "item":
            after_lot = sel[1]   # lot qui contient l'item sélectionné
        else:
            after_lot = ""

        lot_id, label = self._show_add_lot_dialog()
        if not label:
            return
        if not lot_id:
            lot_id = self._next_lot_id()
        # Vérifier unicité
        if self._dm.get_lot(lot_id):
            QMessageBox.warning(
                self, "ID déjà utilisé",
                f"Le lot « {lot_id} » existe déjà. Choisissez un autre numéro.")
            return
        self._dm.add_lot(lot_id, label, insert_after=after_lot)
        pos_msg = f"après lot « {after_lot} »" if after_lot else "en fin de liste"
        self._set_status(f"Lot {lot_id} – {label} ajouté ({pos_msg}).")

    def _add_item(self):
        sel = self._current_selection()
        if sel and sel[0] == "lot":
            lot_id     = sel[1]
            after_item = ""            # on insère à la fin du lot
        elif sel and sel[0] == "item":
            lot_id     = sel[1]
            after_item = sel[2]        # on insère juste après l'item sélectionné
        else:
            lot_id     = None
            after_item = ""

        if not lot_id:
            lots = self._dm.lots
            if not lots:
                QMessageBox.information(self, "Aucun lot",
                                        "Créez d'abord un lot.")
                return
            names = [f"{l.id} – {l.label}" for l in lots]
            choice, ok = QInputDialog.getItem(
                self, "Choisir un lot", "Lot :", names, editable=False)
            if not ok:
                return
            lot_id = lots[names.index(choice)].id

        full_id, label, unit = self._show_add_item_dialog(lot_id)
        if not label:
            return

        # Vérifier unicité de l'ID
        if full_id and self._dm.get_item(lot_id, full_id):
            QMessageBox.warning(
                self, "ID déjà utilisé",
                f"L'item « {full_id} » existe déjà dans ce lot.")
            return

        self._dm.add_item(lot_id, label, unit, item_id=full_id,
                          insert_after=after_item)
        pos_msg = f"après « {after_item} »" if after_item else "en fin de lot"
        self._set_status(
            f"Item {full_id or ''} – {label} ajouté au lot {lot_id} ({pos_msg}).")

    def _rename_selected(self):
        sel = self._current_selection()
        if not sel:
            return
        if sel[0] == "lot":
            lot = self._dm.get_lot(sel[1])
            if not lot:
                return
            new_label, ok = QInputDialog.getText(
                self, "Renommer le lot",
                f"Nouveau nom pour « {lot.label} » :", text=lot.label)
            if ok and new_label.strip():
                self._dm.rename_lot(sel[1], new_label.strip())
        elif sel[0] == "item":
            item = self._dm.get_item(sel[1], sel[2])
            if not item:
                return
            new_label, ok = QInputDialog.getText(
                self, "Renommer l'item",
                f"Nouveau nom pour « {item.label} » :", text=item.label)
            if not ok or not new_label.strip():
                return
            new_unit, ok2 = QInputDialog.getItem(
                self, "Unité", "Unité :", _UNITS,
                current=_UNITS.index(item.unit) if item.unit in _UNITS else 0,
                editable=True)
            self._dm.rename_item(sel[1], sel[2],
                                  new_label.strip(),
                                  new_unit.strip() if ok2 else item.unit)

    def _delete_selected(self):
        sel = self._current_selection()
        if not sel:
            return

        if sel[0] == "lot":
            lot = self._dm.get_lot(sel[1])
            if not lot:
                return
            reply = QMessageBox.question(
                self, "Supprimer le lot",
                f"Supprimer le lot « {lot.label} » et ses {len(lot.items)} item(s) ?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._dm.remove_lot(sel[1])
                self._set_status(f"Lot « {lot.label} » supprimé.")

        elif sel[0] == "item":
            item = self._dm.get_item(sel[1], sel[2])
            if not item:
                return
            # Vérifier si utilisé dans des affectations
            used_in = [
                ga.group_name
                for ga in self._dm.all_assignments()
                for ai in ga.items
                if ai.lot_id == sel[1] and ai.item_id == sel[2]
            ]
            if used_in:
                reply = QMessageBox.warning(
                    self, "Item utilisé",
                    f"L'item « {item.label} » est affecté à :\n"
                    + "\n".join(f"  • {n}" for n in used_in[:5])
                    + ("\n  …" if len(used_in) > 5 else "")
                    + "\n\nSupprimer quand même ?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return
            self._dm.remove_item(sel[1], sel[2])
            self._set_status(f"Item « {item.label} » supprimé.")

    def _on_double_click(self, item: QTreeWidgetItem, col: int):
        self._rename_selected()

    def _on_context_menu(self, pos):
        sel = self._current_selection()
        menu = QMenu(self)
        if sel:
            if sel[0] == "lot":
                menu.addAction("➕ Insérer un lot après", self._add_lot)
                menu.addAction("➕ Ajouter un item dans ce lot", self._add_item)
                menu.addAction("✏ Renommer le lot", self._rename_selected)
                menu.addSeparator()
                menu.addAction("⬆ Monter", lambda: self._dm.move_lot(sel[1], -1))
                menu.addAction("⬇ Descendre", lambda: self._dm.move_lot(sel[1], 1))
                menu.addSeparator()
                menu.addAction("🗑 Supprimer le lot", self._delete_selected)
            elif sel[0] == "item":
                menu.addAction("➕ Insérer un item après", self._add_item)
                menu.addAction("✏ Renommer l'item", self._rename_selected)
                menu.addSeparator()
                menu.addAction("⬆ Monter", lambda: self._dm.move_item(sel[1], sel[2], -1))
                menu.addAction("⬇ Descendre", lambda: self._dm.move_item(sel[1], sel[2], 1))
                menu.addSeparator()
                menu.addAction("🗑 Supprimer l'item", self._delete_selected)
        menu.addSeparator()
        menu.addAction("➕ Nouveau lot", self._add_lot)
        menu.exec_(self._tree.viewport().mapToGlobal(pos))

    # ── Import / Export ───────────────────────────────────────────────────────

    def _import_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer un devis Excel",
            "", "Fichiers Excel (*.xlsx *.xls *.xlsm)")
        if not path:
            return

        lots, msg = self._dm.import_from_excel(path)
        if not lots:
            # Afficher le message diagnostique sur plusieurs lignes
            box = QMessageBox(QMessageBox.Warning, "Import impossible", msg, parent=self)
            box.setDetailedText(msg)
            box.exec_()
            return

        # Ouvrir le dialogue de prévisualisation interactif
        dlg = ImportPreviewDialog(lots, msg, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return

        selected = dlg.get_selected_lots()
        if not selected:
            QMessageBox.information(self, "Import annulé",
                                    "Aucun lot sélectionné — import annulé.")
            return

        n_lots  = len(selected)
        n_items = sum(len(l.items) for l in selected)
        self._dm.apply_imported_lots(selected, merge=dlg.merge)
        self._set_status(
            f"{n_lots} lot(s) et {n_items} article(s) importés avec succès.")

    def _save_model(self):
        reply = QMessageBox.question(
            self, "Enregistrer comme modèle par défaut",
            "Écraser le modèle par défaut (devis_model.json) ?\n"
            "Ce modèle sera utilisé pour tous les nouveaux projets.",
            QMessageBox.Save | QMessageBox.Cancel)
        if reply == QMessageBox.Save:
            ok = self._dm.save_library()
            if ok:
                self._set_status("Modèle par défaut mis à jour.")
                QMessageBox.information(self, "Sauvegardé",
                                        "Le modèle par défaut a été mis à jour.")
            else:
                QMessageBox.critical(self, "Erreur",
                                     "Impossible de sauvegarder le modèle.")

    def _export_model(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la bibliothèque",
            "mon_devis.devis",
            "Modèles de devis (*.devis);;JSON (*.json)")
        if not path:
            return
        ok = self._dm.save_library(path)
        if ok:
            self._set_status(f"Exporté : {path}")
            QMessageBox.information(self, "Export réussi",
                                    f"Bibliothèque exportée :\n{path}")
        else:
            QMessageBox.critical(self, "Erreur", "Impossible d'exporter.")

    def _load_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Charger un modèle de devis",
            "", "Modèles de devis (*.devis *.json)")
        if not path:
            return
        reply = QMessageBox.question(
            self, "Charger un modèle",
            "Remplacer toute la bibliothèque par ce modèle ?",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        ok = self._dm.load_library_from_file(path)
        if ok:
            self._set_status(f"Modèle chargé : {path}")
        else:
            QMessageBox.critical(self, "Erreur",
                                 "Impossible de charger ce fichier.")

    # ── Mise à jour ───────────────────────────────────────────────────────────

    def _on_library_changed(self):
        """Slot connecté au signal DevisManager.devis_structure_changed."""
        self._refresh_tree()

    def _set_status(self, msg: str):
        self._status.setText(msg)
        QTimer.singleShot(5000, lambda: self._status.setText(""))
