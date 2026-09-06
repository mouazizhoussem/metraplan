import uuid
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import QAction, QMenu, QStyle
from ui.icon_manager import IconManager
from core.app_logger import get_logger
_log = get_logger(__name__)


class ContextMenuManager:
    """Gestionnaire de menus contextuels specialises (version Surface)."""

    def __init__(self, main_window, canvas_view):
        self.main_window = main_window
        self.canvas_view = canvas_view
        self.icon_manager = IconManager(widget=canvas_view)

    # ------------------------------------------------------------------
    # API demandee
    # ------------------------------------------------------------------
    def build_surface_menu(self, surface_entity):
        """Construit le menu contextuel complet pour une surface."""
        menu = QMenu(self.canvas_view)
        menu.setToolTipsVisible(True)
        menu.setStyleSheet("QMenu { icon-size: 18px; }")

        selected = self.canvas_view.get_selected_entities() if hasattr(
            self.canvas_view, "get_selected_entities") else []
        has_selection = len(selected) > 0
        has_group = bool(getattr(surface_entity, "group_id", None))
        has_clipboard = bool(getattr(self.main_window, "clipboard_entity", None))

        # En-tête dynamique (style CAO) : infos de contexte non cliquables
        self._add_surface_header(menu, surface_entity)
        menu.addSeparator()

        # 1) Gestion de la surface
        a_add_group = self._make_action(
            menu, "Ajouter une surface au groupe M",
            icon_key="add_group",
            tip="Active le mode M pour ajouter une surface au groupe"
        )
        a_add_group.triggered.connect(
            lambda: self._cb_add_surface_to_group_m(surface_entity))
        menu.addAction(a_add_group)

        a_opening = self._make_action(
            menu, "Créer une ouverture",
            icon_key="opening",
            tip="Active automatiquement l'outil Ouverture"
        )
        a_opening.triggered.connect(lambda: self._cb_create_opening(surface_entity))
        menu.addAction(a_opening)

        a_perimeter = self._make_action(
            menu, "Créer un périmètre à partir de cette surface",
            icon_key="perimeter_from_surface",
            tip="Génère un périmètre à partir du contour de la surface"
        )
        a_perimeter.triggered.connect(
            lambda: self._cb_create_perimeter_from_surface(surface_entity))
        menu.addAction(a_perimeter)

        menu.addSeparator()

        # 2) Edition
        a_cut = self._make_action(menu, "Couper", icon_key="cut")
        a_cut.setShortcut(QKeySequence("Ctrl+X"))
        a_cut.setShortcutVisibleInContextMenu(True)
        a_cut.setEnabled(has_selection)
        a_cut.triggered.connect(self._cb_cut)
        menu.addAction(a_cut)

        a_copy = self._make_action(menu, "Copier", icon_key="copy")
        a_copy.setShortcut(QKeySequence("Ctrl+C"))
        a_copy.setShortcutVisibleInContextMenu(True)
        a_copy.setEnabled(has_selection)
        a_copy.triggered.connect(self._cb_copy)
        menu.addAction(a_copy)

        a_paste = self._make_action(menu, "Coller", icon_key="paste")
        a_paste.setShortcut(QKeySequence("Ctrl+V"))
        a_paste.setShortcutVisibleInContextMenu(True)
        a_paste.setEnabled(has_clipboard)
        a_paste.triggered.connect(self._cb_paste)
        menu.addAction(a_paste)

        a_delete = self._make_action(menu, "Supprimer", icon_key="delete")
        a_delete.setShortcut(QKeySequence(Qt.Key_Delete))
        a_delete.setShortcutVisibleInContextMenu(True)
        a_delete.setEnabled(has_selection)
        a_delete.triggered.connect(self._cb_delete)
        menu.addAction(a_delete)

        menu.addSeparator()

        # 3) Ordre d'affichage
        a_front = self._make_action(menu, "Mettre en avant", icon_key="bring_front")
        a_front.setShortcut(QKeySequence("Ctrl+J"))
        a_front.setShortcutVisibleInContextMenu(True)
        a_front.setEnabled(has_selection)
        a_front.triggered.connect(lambda: self._cb_bring_front(surface_entity))
        menu.addAction(a_front)

        a_back = self._make_action(menu, "Mettre en arrière", icon_key="send_back")
        a_back.setShortcut(QKeySequence("Ctrl+K"))
        a_back.setShortcutVisibleInContextMenu(True)
        a_back.setEnabled(has_selection)
        a_back.triggered.connect(lambda: self._cb_send_back(surface_entity))
        menu.addAction(a_back)

        menu.addSeparator()

        # 4) Selection
        a_select_group = self._make_action(
            menu, "Sélectionner le groupe", icon_key="select_group")
        a_select_group.setEnabled(has_group)
        a_select_group.triggered.connect(
            lambda: self._cb_select_group(surface_entity))
        menu.addAction(a_select_group)

        return menu

    def build_perimeter_menu(self, perimeter_entity):
        """Construit le menu contextuel complet pour un périmètre."""
        menu = QMenu(self.canvas_view)
        menu.setToolTipsVisible(True)
        menu.setStyleSheet("QMenu { icon-size: 18px; }")

        selected = self.canvas_view.get_selected_entities() if hasattr(
            self.canvas_view, "get_selected_entities") else []
        has_selection = len(selected) > 0
        has_clipboard = bool(getattr(self.main_window, "clipboard_entity", None))
        clicked_opening = self._is_opening_clicked(perimeter_entity)

        # En-tête dynamique
        self._add_perimeter_header(menu, perimeter_entity)
        menu.addSeparator()

        # 1) Gestion du périmètre
        a_insert_point = self._make_action(
            menu, "Insérer un point",
            icon_key="perimeter.insert_point.black",
            tip="Insère un point sur le segment le plus proche")
        a_insert_point.setShortcut(QKeySequence("I"))
        a_insert_point.setShortcutVisibleInContextMenu(True)
        a_insert_point.triggered.connect(
            lambda: self._cb_insert_point_on_perimeter(perimeter_entity))
        menu.addAction(a_insert_point)

        a_add_group = self._make_action(
            menu, "Ajouter un périmètre au groupe M",
            icon_key="perimeter.add_group",
            tip="Active le mode M pour ajouter un périmètre au groupe"
        )
        a_add_group.setShortcut(QKeySequence("M"))
        a_add_group.setShortcutVisibleInContextMenu(True)
        a_add_group.triggered.connect(
            lambda: self._cb_add_perimeter_to_group_m(perimeter_entity))
        menu.addAction(a_add_group)

        a_opening = self._make_action(
            menu, "Créer une ouverture linéaire",
            icon_key="perimeter.opening",
            tip="Active le mode création d'ouverture linéaire sur ce périmètre"
        )
        a_opening.setShortcut(QKeySequence("P"))
        a_opening.setShortcutVisibleInContextMenu(True)
        a_opening.triggered.connect(
            lambda: self._cb_create_linear_opening_on_perimeter(perimeter_entity))
        menu.addAction(a_opening)

        a_opening_height = self._make_action(
            menu, "Définir la hauteur de l'ouverture",
            icon_key="perimeter.opening_height",
            tip="Disponible si le clic droit est fait sur une ouverture linéaire"
        )
        a_opening_height.setShortcut(QKeySequence("H"))
        a_opening_height.setShortcutVisibleInContextMenu(True)
        a_opening_height.setEnabled(clicked_opening)
        a_opening_height.triggered.connect(
            lambda: self._cb_set_opening_height_at_click(perimeter_entity))
        menu.addAction(a_opening_height)

        menu.addSeparator()

        # 2) Édition (même base que Surface)
        a_cut = self._make_action(menu, "Couper", icon_key="perimeter.cut")
        a_cut.setShortcut(QKeySequence("Ctrl+X"))
        a_cut.setShortcutVisibleInContextMenu(True)
        a_cut.setEnabled(has_selection)
        a_cut.triggered.connect(self._cb_cut)
        menu.addAction(a_cut)

        a_copy = self._make_action(menu, "Copier", icon_key="perimeter.copy")
        a_copy.setShortcut(QKeySequence("Ctrl+C"))
        a_copy.setShortcutVisibleInContextMenu(True)
        a_copy.setEnabled(has_selection)
        a_copy.triggered.connect(self._cb_copy)
        menu.addAction(a_copy)

        a_paste = self._make_action(menu, "Coller", icon_key="perimeter.paste")
        a_paste.setShortcut(QKeySequence("Ctrl+V"))
        a_paste.setShortcutVisibleInContextMenu(True)
        a_paste.setEnabled(has_clipboard)
        a_paste.triggered.connect(self._cb_paste)
        menu.addAction(a_paste)

        a_delete = self._make_action(menu, "Supprimer", icon_key="perimeter.delete")
        a_delete.setShortcut(QKeySequence(Qt.Key_Delete))
        a_delete.setShortcutVisibleInContextMenu(True)
        a_delete.setEnabled(has_selection)
        a_delete.triggered.connect(self._cb_delete)
        menu.addAction(a_delete)

        menu.addSeparator()

        # 3) Ordre d'affichage (même base que Surface)
        a_front = self._make_action(menu, "Mettre en avant", icon_key="perimeter.bring_front")
        a_front.setShortcut(QKeySequence("Ctrl+J"))
        a_front.setShortcutVisibleInContextMenu(True)
        a_front.setEnabled(has_selection)
        a_front.triggered.connect(lambda: self._cb_bring_front(perimeter_entity))
        menu.addAction(a_front)

        a_back = self._make_action(menu, "Mettre en arrière", icon_key="perimeter.send_back")
        a_back.setShortcut(QKeySequence("Ctrl+K"))
        a_back.setShortcutVisibleInContextMenu(True)
        a_back.setEnabled(has_selection)
        a_back.triggered.connect(lambda: self._cb_send_back(perimeter_entity))
        menu.addAction(a_back)

        menu.addSeparator()

        # 4) Sélection (même logique que Surface)
        has_group = bool(getattr(perimeter_entity, "group_id", None))
        a_select_group = self._make_action(
            menu, "Sélectionner le groupe", icon_key="select_group")
        a_select_group.setEnabled(has_group)
        a_select_group.triggered.connect(
            lambda: self._cb_select_group(perimeter_entity))
        menu.addAction(a_select_group)

        return menu

    def build_counter_menu(self, counter_entity):
        """Construit le menu contextuel complet pour un compteur (PointEntity)."""
        menu = QMenu(self.canvas_view)
        menu.setToolTipsVisible(True)
        menu.setStyleSheet("QMenu { icon-size: 18px; }")

        selected = self.canvas_view.get_selected_entities() if hasattr(
            self.canvas_view, "get_selected_entities") else []
        has_selection = len(selected) > 0
        has_clipboard = bool(getattr(self.main_window, "clipboard_entity", None))
        has_group = bool(getattr(counter_entity, "group_id", None))

        # En-tête dynamique
        self._add_counter_header(menu, counter_entity)
        menu.addSeparator()

        # 1) Action spécifique compteur
        a_add_group = self._make_action(
            menu, "Ajouter un compteur au groupe M",
            icon_key="counter.add_group",
            tip="Active le mode M pour ajouter ce compteur au groupe"
        )
        a_add_group.setShortcut(QKeySequence("M"))
        a_add_group.setShortcutVisibleInContextMenu(True)
        a_add_group.triggered.connect(
            lambda: self._cb_add_counter_to_group_m(counter_entity))
        menu.addAction(a_add_group)

        menu.addSeparator()

        # 2) Édition
        a_cut = self._make_action(menu, "Couper", icon_key="counter.cut")
        a_cut.setShortcut(QKeySequence("Ctrl+X"))
        a_cut.setShortcutVisibleInContextMenu(True)
        a_cut.setEnabled(has_selection)
        a_cut.triggered.connect(self._cb_cut)
        menu.addAction(a_cut)

        a_copy = self._make_action(menu, "Copier", icon_key="counter.copy")
        a_copy.setShortcut(QKeySequence("Ctrl+C"))
        a_copy.setShortcutVisibleInContextMenu(True)
        a_copy.setEnabled(has_selection)
        a_copy.triggered.connect(self._cb_copy)
        menu.addAction(a_copy)

        a_paste = self._make_action(menu, "Coller", icon_key="counter.paste")
        a_paste.setShortcut(QKeySequence("Ctrl+V"))
        a_paste.setShortcutVisibleInContextMenu(True)
        a_paste.setEnabled(has_clipboard)
        a_paste.triggered.connect(self._cb_paste)
        menu.addAction(a_paste)

        a_delete = self._make_action(menu, "Supprimer", icon_key="counter.delete")
        a_delete.setShortcut(QKeySequence(Qt.Key_Delete))
        a_delete.setShortcutVisibleInContextMenu(True)
        a_delete.setEnabled(has_selection)
        a_delete.triggered.connect(self._cb_delete)
        menu.addAction(a_delete)

        menu.addSeparator()

        # 3) Ordre d'affichage
        a_front = self._make_action(menu, "Mettre en avant", icon_key="counter.bring_front")
        a_front.setShortcut(QKeySequence("Ctrl+J"))
        a_front.setShortcutVisibleInContextMenu(True)
        a_front.setEnabled(has_selection)
        a_front.triggered.connect(lambda: self._cb_bring_front(counter_entity))
        menu.addAction(a_front)

        a_back = self._make_action(menu, "Mettre en arrière", icon_key="counter.send_back")
        a_back.setShortcut(QKeySequence("Ctrl+K"))
        a_back.setShortcutVisibleInContextMenu(True)
        a_back.setEnabled(has_selection)
        a_back.triggered.connect(lambda: self._cb_send_back(counter_entity))
        menu.addAction(a_back)

        menu.addSeparator()

        # 4) Sélection
        a_select_group = self._make_action(
            menu, "Sélectionner le groupe", icon_key="select_group")
        a_select_group.setEnabled(has_group)
        a_select_group.triggered.connect(
            lambda: self._cb_select_group(counter_entity))
        menu.addAction(a_select_group)

        return menu

    def build_line_menu(self, line_entity):
        """Construit le menu contextuel pour une entité ligne (distance ou échelle)."""
        menu = QMenu(self.canvas_view)
        menu.setToolTipsVisible(True)
        menu.setStyleSheet("QMenu { icon-size: 18px; }")

        is_scale = getattr(line_entity, "is_scale_reference", False)
        name = getattr(line_entity, "name", "Distance")
        kind = "Échelle" if is_scale else "Distance"

        # En-tête
        title_action = QAction(f"{kind} : {name}", menu)
        title_action.setEnabled(False)
        menu.addAction(title_action)
        menu.addSeparator()

        if is_scale:
            a_modify = self._make_action(
                menu, "Modifier l'échelle",
                icon_key="scale",
                tip="Tracer une nouvelle ligne de référence pour recalibrer l'échelle"
            )
            a_modify.triggered.connect(lambda: self._cb_modify_scale(line_entity))
            menu.addAction(a_modify)
            menu.addSeparator()

        selected = self.canvas_view.get_selected_entities() if hasattr(
            self.canvas_view, "get_selected_entities") else []
        has_selection = len(selected) > 0

        a_delete = self._make_action(menu, "Supprimer", icon_key="delete")
        a_delete.setShortcut(QKeySequence(Qt.Key_Delete))
        a_delete.setShortcutVisibleInContextMenu(True)
        a_delete.setEnabled(has_selection or True)
        a_delete.triggered.connect(lambda: self._cb_delete_entity(line_entity))
        menu.addAction(a_delete)

        return menu

    def show_menu(self, event, clicked_entity=None):
        """
        Affiche le menu contextuel adapte.
        Retourne True si un menu a ete affiche.
        """
        entity = clicked_entity or self.main_window.get_selected_entity()
        self._last_context_scene_pos = self.canvas_view.mapToScene(event.pos())

        if entity and getattr(entity, "entity_type", "") in ("polygon", "surface"):
            menu = self.build_surface_menu(entity)
            menu.exec_(event.globalPos())
            return True
        if entity and getattr(entity, "entity_type", "") == "perimeter":
            menu = self.build_perimeter_menu(entity)
            menu.exec_(event.globalPos())
            return True
        if entity and getattr(entity, "entity_type", "") == "point":
            menu = self.build_counter_menu(entity)
            menu.exec_(event.globalPos())
            return True
        if entity and getattr(entity, "entity_type", "") == "line":
            menu = self.build_line_menu(entity)
            menu.exec_(event.globalPos())
            return True
        return False

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _cb_add_surface_to_group_m(self, surface_entity):
        try:
            self._select_entities([surface_entity])
            if hasattr(self.canvas_view, "activate_continue_measure_mode"):
                self.canvas_view.activate_continue_measure_mode()
                self.main_window.statusBar().showMessage(
                    "✅ Mode groupe M activé pour la surface", 3000)
                return
        except Exception as e:
            _log.warning(f"Erreur add_surface_to_group_m: {e}")
        self.main_window.statusBar().showMessage("❌ Impossible d'activer le groupe M", 3000)

    def _cb_add_counter_to_group_m(self, counter_entity):
        try:
            self._select_entities([counter_entity])
            if hasattr(self.canvas_view, "activate_continue_measure_mode"):
                self.canvas_view.activate_continue_measure_mode()
                self.main_window.statusBar().showMessage(
                    "✅ Mode groupe M activé pour le compteur", 3000)
                return
        except Exception as e:
            _log.warning(f"Erreur add_counter_to_group_m: {e}")
        self.main_window.statusBar().showMessage("❌ Impossible d'activer le groupe M", 3000)

    def _cb_add_perimeter_to_group_m(self, perimeter_entity):
        try:
            self._select_entities([perimeter_entity])
            if hasattr(self.canvas_view, "activate_continue_measure_mode"):
                self.canvas_view.activate_continue_measure_mode()
                self.main_window.statusBar().showMessage(
                    "✅ Mode groupe M activé pour le périmètre", 3000)
                return
        except Exception as e:
            _log.warning(f"Erreur add_perimeter_to_group_m: {e}")
        self.main_window.statusBar().showMessage("❌ Impossible d'activer le groupe M", 3000)

    def _cb_insert_point_on_perimeter(self, perimeter_entity):
        try:
            scene = getattr(self.canvas_view, "scene", None)
            if hasattr(perimeter_entity, "enable_editing") and not getattr(perimeter_entity, "is_editing", False):
                perimeter_entity.enable_editing(scene)

            cursor_pos = getattr(self, "_last_context_scene_pos", None)
            if cursor_pos is None:
                self.main_window.statusBar().showMessage("❌ Position du clic introuvable", 2500)
                return

            if hasattr(perimeter_entity, "insert_point_at_cursor") and perimeter_entity.insert_point_at_cursor(cursor_pos):
                if hasattr(self.main_window, "on_entity_modified"):
                    self.main_window.on_entity_modified(perimeter_entity)
                self.main_window.statusBar().showMessage("✅ Point inséré sur le périmètre", 2500)
            else:
                self.main_window.statusBar().showMessage(
                    "⚠️ Impossible d'insérer le point (curseur trop éloigné)", 3000)
        except Exception as e:
            _log.warning(f"Erreur insert_point_on_perimeter: {e}")
            self.main_window.statusBar().showMessage(f"❌ Erreur insertion point: {e}", 3000)

    def _cb_create_linear_opening_on_perimeter(self, perimeter_entity):
        try:
            self._select_entities([perimeter_entity])
            if hasattr(self.main_window, "start_linear_opening_on_selected_perimeter"):
                self.main_window.start_linear_opening_on_selected_perimeter()
            else:
                self.main_window.statusBar().showMessage(
                    "❌ Action indisponible: création d'ouverture", 3000)
        except Exception as e:
            _log.warning(f"Erreur create_linear_opening_on_perimeter: {e}")
            self.main_window.statusBar().showMessage(
                f"❌ Erreur ouverture linéaire: {e}", 3000)

    def _cb_set_opening_height_at_click(self, perimeter_entity):
        try:
            scene_pos = getattr(self, "_last_context_scene_pos", None)
            if scene_pos is None:
                self.main_window.statusBar().showMessage("❌ Position du clic introuvable", 2500)
                return

            if not hasattr(perimeter_entity, "_find_opening_at_position"):
                self.main_window.statusBar().showMessage(
                    "❌ Cette version du périmètre ne supporte pas l'édition d'ouverture", 3000)
                return

            opening_idx, opening = perimeter_entity._find_opening_at_position(scene_pos)
            if opening_idx is None:
                self.main_window.statusBar().showMessage(
                    "⚠️ Clic droit à faire sur une ouverture linéaire", 3000)
                return

            default_height = float(opening.get(
                'height', getattr(perimeter_entity, 'default_opening_height', 2.10)))
            if hasattr(self.main_window, "prompt_opening_height"):
                new_height = self.main_window.prompt_opening_height(default_value=default_height)
            else:
                new_height = None

            if new_height is None:
                return

            perimeter_entity.linear_openings[opening_idx]['height'] = max(0.0, float(new_height))
            if hasattr(perimeter_entity, 'draw'):
                perimeter_entity.draw(getattr(perimeter_entity, 'scene_ref', None) or getattr(self.canvas_view, 'scene', None))
            if hasattr(self.main_window, "on_entity_modified"):
                self.main_window.on_entity_modified(perimeter_entity)

            self.main_window.statusBar().showMessage(
                f"✅ Hauteur ouverture #{opening_idx + 1}: {float(new_height):.2f} m", 3000)
        except Exception as e:
            _log.warning(f"Erreur set_opening_height_at_click: {e}")
            self.main_window.statusBar().showMessage(
                f"❌ Erreur hauteur ouverture: {e}", 3000)

    def _cb_create_opening(self, surface_entity):
        try:
            self._select_entities([surface_entity])
            if hasattr(self.main_window, "activate_opening_tool"):
                self.main_window.activate_opening_tool()
            self.main_window.statusBar().showMessage(
                "✅ Outil ouverture activé", 2500)
        except Exception as e:
            _log.warning(f"Erreur create_opening: {e}")
            self.main_window.statusBar().showMessage(
                "❌ Impossible d'activer l'outil ouverture", 3000)

    def _cb_create_perimeter_from_surface(self, surface_entity):
        try:
            points = [QPointF(p.x(), p.y()) for p in getattr(surface_entity, "points", [])]
            if len(points) < 3:
                self.main_window.statusBar().showMessage(
                    "❌ Surface invalide pour créer un périmètre", 3000)
                return

            # Forcer la fermeture du contour (dernier segment vers le premier point).
            # PerimeterEntity trace les segments [i -> i+1], donc on ajoute explicitement
            # le premier point en fin de liste si besoin.
            if points:
                first = points[0]
                last = points[-1]
                if abs(first.x() - last.x()) > 1e-6 or abs(first.y() - last.y()) > 1e-6:
                    points.append(QPointF(first.x(), first.y()))

            from entities.perimeter_entity import PerimeterEntity
            ppm = getattr(surface_entity, "pixels_per_meter", getattr(self.canvas_view, "pixels_per_meter", 100))
            perimeter = PerimeterEntity(
                points=points,
                color=QColor(0, 0, 255, 160),
                width=2,
                pixels_per_meter=ppm,
                name=f"Périmètre de {getattr(surface_entity, 'name', 'Surface')}"
            )

            # Hériter dimensions utiles (quantitatif)
            perimeter.height = float(getattr(surface_entity, "height", 0.0) or 0.0)
            perimeter.thickness = float(getattr(surface_entity, "thickness", 0.0) or 0.0)

            # ── Assigner un group_id cohérent ──────────────────────────────
            # Si la surface source appartient à un groupe de surfaces, tous les
            # périmètres créés depuis ce même groupe partagent un group_id
            # dérivé (préfixe "perim_") → ils seront groupés immédiatement
            # sans avoir besoin de recharger la page.
            import uuid as _uuid
            surface_group_id = getattr(surface_entity, "group_id", None)
            if surface_group_id:
                perimeter.group_id = f"perim_{surface_group_id}"
            else:
                # Surface isolée : group_id unique (comportement précédent)
                perimeter.group_id = f"group_{_uuid.uuid4().hex[:8]}"
            perimeter.is_group_parent = True
            if not hasattr(perimeter, "child_entities"):
                perimeter.child_entities = []

            manager = getattr(self.canvas_view, "entity_manager", None)
            scene = getattr(self.canvas_view, "scene", None)
            if manager:
                entity_id = manager.add_entity(perimeter)
                perimeter.entity_id = entity_id
            if scene:
                perimeter.draw(scene)

            # ── Re-établir les liens de groupe immédiatement ──────────────
            # Sans cela, le regroupement n'était visible qu'après navigation
            # vers une autre page et retour.
            if manager and hasattr(self.main_window, '_rebuild_group_links'):
                all_ents = manager.get_all_entities()
                self.main_window._rebuild_group_links(all_ents)

            if hasattr(self.main_window, "on_entity_modified"):
                self.main_window.on_entity_modified(perimeter)
            self._select_entities([perimeter])
            self.main_window.statusBar().showMessage(
                "✅ Périmètre créé à partir de la surface", 3000)
        except Exception as e:
            _log.warning(f"Erreur create_perimeter_from_surface: {e}")
            self.main_window.statusBar().showMessage(
                f"❌ Erreur création périmètre: {e}", 3000)

    def _cb_modify_scale(self, scale_entity):
        """Supprime l'ancienne ligne d'échelle et réactive l'outil échelle."""
        try:
            # Supprimer l'ancienne entité d'échelle de la scène et du gestionnaire
            scene = getattr(self.canvas_view, "scene", None)
            manager = getattr(self.canvas_view, "entity_manager", None)
            if scale_entity:
                if scene and hasattr(scale_entity, "delete"):
                    try:
                        scale_entity.delete(scene)
                    except Exception:
                        pass
                # Neutraliser complètement l'entité pour qu'elle ne puisse plus se redessiner
                scale_entity.scene_ref = None
                scale_entity.line_item = None
                scale_entity.text_item = None
                scale_entity.text_bg = None
                if manager:
                    try:
                        manager.remove_entity(scale_entity)
                    except Exception:
                        pass

            # Réactiver l'outil échelle
            if hasattr(self.main_window, "activate_scale_tool"):
                self.main_window.activate_scale_tool()
            elif hasattr(self.canvas_view, "tool_manager"):
                tm = self.canvas_view.tool_manager
                if hasattr(tm, "activate_scale"):
                    tm.activate_scale()
            self.main_window.statusBar().showMessage(
                "📐 Tracez la nouvelle ligne de référence pour l'échelle", 4000)
        except Exception as e:
            _log.warning(f"Erreur modify_scale: {e}")
            self.main_window.statusBar().showMessage(f"❌ Erreur modification échelle: {e}", 3000)

    def _cb_delete_entity(self, entity):
        """Supprime une entité spécifique (ligne de distance ou d'échelle)."""
        try:
            scene = getattr(self.canvas_view, "scene", None)
            manager = getattr(self.canvas_view, "entity_manager", None)
            if scene and hasattr(entity, "delete"):
                entity.delete(scene)
            if manager:
                manager.remove_entity(entity)
            self.main_window.statusBar().showMessage("✅ Entité supprimée", 2000)
        except Exception as e:
            _log.warning(f"Erreur delete_entity: {e}")

    def _cb_cut(self):
        if hasattr(self.main_window, "cut_entity"):
            self.main_window.cut_entity()

    def _cb_copy(self):
        if hasattr(self.main_window, "copy_entity"):
            self.main_window.copy_entity()

    def _cb_paste(self):
        if hasattr(self.main_window, "paste_entity"):
            self.main_window.paste_entity()

    def _cb_delete(self):
        if hasattr(self.canvas_view, "delete_selected_entities"):
            self.canvas_view.delete_selected_entities()

    def _cb_bring_front(self, entity):
        self._shift_z(entity, to_front=True)

    def _cb_send_back(self, entity):
        self._shift_z(entity, to_front=False)

    def _cb_select_group(self, entity):
        group_id = getattr(entity, "group_id", None)
        if not group_id:
            self._select_entities([entity])
            return
        manager = getattr(self.canvas_view, "entity_manager", None)
        if not manager:
            return
        entities = []
        for ent in manager.get_all_entities():
            if getattr(ent, "group_id", None) == group_id:
                entities.append(ent)
        self._select_entities(entities)

    def _cb_select_same_type(self, entity):
        manager = getattr(self.canvas_view, "entity_manager", None)
        if not manager:
            return
        ent_type = getattr(entity, "entity_type", "")
        entities = [e for e in manager.get_all_entities() if getattr(e, "entity_type", "") == ent_type]
        self._select_entities(entities)

    def _cb_clear_selection(self):
        if hasattr(self.canvas_view, "scene") and self.canvas_view.scene:
            self.canvas_view.scene.clearSelection()
        manager = getattr(self.canvas_view, "entity_manager", None)
        if manager:
            for ent in manager.get_all_entities():
                if hasattr(ent, "set_selected"):
                    ent.set_selected(False)

    def _cb_move_to_same_group(self, target_entity):
        selected = self.canvas_view.get_selected_entities() if hasattr(self.canvas_view, "get_selected_entities") else []
        if not selected:
            return

        # Garantir un groupe cible existant
        target_group_id = getattr(target_entity, "group_id", None)
        if not target_group_id:
            target_group_id = f"group_{uuid.uuid4().hex[:8]}"
            target_entity.group_id = target_group_id
            target_entity.is_group_parent = True
            if not hasattr(target_entity, "child_entities"):
                target_entity.child_entities = []

        if not hasattr(target_entity, "child_entities"):
            target_entity.child_entities = []

        # Le nom du groupe suit le nom de l'entité parent
        group_name = getattr(target_entity, "name", None) or getattr(target_entity, "group_name", None)
        if group_name:
            target_entity.group_name = group_name

        for ent in selected:
            if ent is target_entity:
                continue
            if getattr(ent, "entity_type", "") not in ("polygon", "surface", "perimeter", "point"):
                continue
            ent.group_id = target_group_id
            ent.parent_entity = target_entity
            ent.is_group_parent = False
            if group_name:
                ent.group_name = group_name
            if ent not in target_entity.child_entities:
                target_entity.child_entities.append(ent)

        self.main_window.statusBar().showMessage("✅ Entités déplacées vers ce groupe", 2500)

    def _cb_move_to_new_group(self):
        selected = self.canvas_view.get_selected_entities() if hasattr(self.canvas_view, "get_selected_entities") else []
        groupables = [e for e in selected if getattr(e, "entity_type", "") in ("polygon", "surface", "perimeter", "point")]
        if not groupables:
            self.main_window.statusBar().showMessage("⚠️ Aucune entité groupable sélectionnée", 2500)
            return

        group_id = f"group_{uuid.uuid4().hex[:8]}"
        parent = groupables[0]
        parent.group_id = group_id
        parent.is_group_parent = True
        parent.parent_entity = None
        parent.child_entities = []

        # Le nom du groupe suit le nom du parent
        group_name = getattr(parent, "name", None) or ""
        if group_name:
            parent.group_name = group_name

        for child in groupables[1:]:
            child.group_id = group_id
            child.is_group_parent = False
            child.parent_entity = parent
            if group_name:
                child.group_name = group_name
            parent.child_entities.append(child)

        self.main_window.statusBar().showMessage(
            f"✅ Nouveau groupe créé ({len(groupables)} élément(s))", 3000)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_action(self, parent, text, icon=None, tip=None, icon_key=None):
        action = QAction(text, parent)
        if icon_key:
            action.setIcon(self.icon_manager.icon(icon_key))
        elif icon is not None and hasattr(parent, "style"):
            action.setIcon(parent.style().standardIcon(icon))
        if tip:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        return action

    def _is_opening_clicked(self, perimeter_entity):
        scene_pos = getattr(self, "_last_context_scene_pos", None)
        if scene_pos is None:
            return False
        if not hasattr(perimeter_entity, "_find_opening_at_position"):
            return False
        try:
            opening_idx, _ = perimeter_entity._find_opening_at_position(scene_pos)
            return opening_idx is not None
        except Exception:
            return False

    def _get_group_display_name(self, entity):
        """
        Retourne le nom lisible du groupe, toujours résolu dynamiquement
        depuis le nom actuel de l'entité parent — ainsi, si l'utilisateur
        renomme une entité, le nom de groupe se met à jour automatiquement.
        """
        group_id = getattr(entity, "group_id", None)
        if not group_id:
            return None

        # Toujours lire le nom courant du parent dans l'entity_manager
        # (pas de cache statique : le nom suit les renommages en temps réel)
        manager = getattr(self.canvas_view, "entity_manager", None)
        if manager:
            for ent in manager.get_all_entities():
                if getattr(ent, "group_id", None) == group_id and getattr(ent, "is_group_parent", False):
                    parent_name = getattr(ent, "name", None)
                    if parent_name:
                        return parent_name

        # Pour les compteurs : tous les points du même groupe portent le même nom
        entity_name = getattr(entity, "name", None)
        if entity_name:
            return entity_name

        return group_id  # fallback brut

    def _add_surface_header(self, menu, surface_entity):
        """Ajoute un en-tête informatif non cliquable en haut du menu Surface."""
        name = (getattr(surface_entity, "name", "") or "Surface").strip()
        group_txt = "Aucun"
        group_id = getattr(surface_entity, "group_id", None)
        if group_id:
            group_txt = self._get_group_display_name(surface_entity) or group_id

        title_action = QAction(f"Surface : {name}", menu)
        title_action.setEnabled(False)
        menu.addAction(title_action)

        meta_action = QAction(f"Groupe : {group_txt}", menu)
        meta_action.setEnabled(False)
        menu.addAction(meta_action)

    def _add_perimeter_header(self, menu, perimeter_entity):
        """Ajoute un en-tête informatif non cliquable en haut du menu Périmètre."""
        name = (getattr(perimeter_entity, "name", "") or "Périmètre").strip()
        group_txt = "Aucun"
        group_id = getattr(perimeter_entity, "group_id", None)
        if group_id:
            group_txt = self._get_group_display_name(perimeter_entity) or group_id

        title_action = QAction(f"Périmètre : {name}", menu)
        title_action.setEnabled(False)
        menu.addAction(title_action)

        meta_action = QAction(f"Groupe : {group_txt}", menu)
        meta_action.setEnabled(False)
        menu.addAction(meta_action)

    def _add_counter_header(self, menu, counter_entity):
        """Ajoute un en-tête informatif non cliquable en haut du menu Compteur."""
        base_name = (getattr(counter_entity, "name", "") or "Compteur").strip()
        num = getattr(counter_entity, "counter_number", None)
        display_name = f"{base_name} #{num}" if num else base_name

        group_txt = "Aucun"
        group_id = getattr(counter_entity, "group_id", None)
        if group_id:
            group_txt = self._get_group_display_name(counter_entity) or group_id

        title_action = QAction(f"Compteur : {display_name}", menu)
        title_action.setEnabled(False)
        menu.addAction(title_action)

        meta_action = QAction(f"Groupe : {group_txt}", menu)
        meta_action.setEnabled(False)
        menu.addAction(meta_action)

    def _select_entities(self, entities):
        if hasattr(self.canvas_view, "scene") and self.canvas_view.scene:
            self.canvas_view.scene.clearSelection()
        for ent in entities:
            if hasattr(ent, "set_selected"):
                ent.set_selected(True)
            for item in self._iter_entity_graphics(ent):
                try:
                    item.setSelected(True)
                except Exception:
                    pass

    def _iter_entity_graphics(self, entity):
        fields = (
            "surface_item", "path_item", "polygon_item", "line_item",
            "point_item", "text_item", "text_bg", "name_item"
        )
        items = []
        for f in fields:
            item = getattr(entity, f, None)
            if item:
                items.append(item)
        # Cas listes (perimeter text_items/text_bgs)
        for f in ("text_items", "text_bgs", "anchor_points"):
            arr = getattr(entity, f, None)
            if arr:
                for item in arr:
                    if item:
                        items.append(item)
        return items

    def _shift_z(self, entity, to_front=True):
        scene = getattr(self.canvas_view, "scene", None)
        if not scene:
            return
        try:
            entity_items = [
                it for it in self._iter_entity_graphics(entity)
                if it and hasattr(it, "zValue") and it.scene() is scene
            ]
            if not entity_items:
                return

            # Réordonne par rapport aux autres entités de dessin uniquement
            # (et non pas par rapport à tous les items de scène), afin d'éviter
            # qu'une surface parte derrière le fond PDF et "disparaisse".
            manager = getattr(self.canvas_view, "entity_manager", None)
            other_items = []
            if manager:
                for other in manager.get_all_entities():
                    if other is entity:
                        continue
                    for it in self._iter_entity_graphics(other):
                        if it and hasattr(it, "zValue") and it.scene() is scene:
                            other_items.append(it)

            entity_items_sorted = sorted(entity_items, key=lambda i: i.zValue())
            step = 0.01

            if to_front:
                if other_items:
                    base = max(it.zValue() for it in other_items) + step
                else:
                    base = max(it.zValue() for it in entity_items_sorted)
            else:
                min_visible_z = 0.1
                if other_items:
                    target_top = min(it.zValue() for it in other_items) - step
                    spread = step * (len(entity_items_sorted) - 1)
                    base = max(min_visible_z, target_top - spread)
                else:
                    # Aucun autre objet : ne pas forcer un z trop bas.
                    base = max(min_visible_z, min(it.zValue() for it in entity_items_sorted))

            for idx, item in enumerate(entity_items_sorted):
                item.setZValue(base + (idx * step))

            txt = "en avant" if to_front else "en arrière"
            self.main_window.statusBar().showMessage(f"✅ Surface mise {txt}", 2000)
        except Exception as e:
            _log.warning(f"Erreur shift_z: {e}")