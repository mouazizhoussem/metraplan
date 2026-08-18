from PyQt5.QtWidgets import QGraphicsView, QGraphicsPixmapItem, QRubberBand
from PyQt5.QtCore import Qt, QPoint, QPointF, QRect, QSize
from PyQt5.QtGui import QPixmap, QPolygonF, QColor

from core.canvas_scene import CanvasScene
from core.entity_manager import EntityManager
from tools.tool_manager import ToolManager
from core.ortho_manager import OrthoManager
from ui.legend_widget import LegendWidget
from core.scale_manager import ScaleManager
from ui.action_registry import ActionRegistry
from ui.tool_context_adapter import ToolContextAdapter
from ui.context_menu_service import ContextMenuService
from ui.context_menu_icons import create_icon_provider
from ui.context_menu_manager import ContextMenuManager


class CanvasView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent

        # Création de la scène
        self.scene = CanvasScene(self)
        self.setScene(self.scene)

        # Gestionnaire d'entités
        self.entity_manager = EntityManager()
        self.debug = False

        # Connecter les signaux pour mise à jour auto de la légende
        if hasattr(self.entity_manager, 'entity_added'):
            self.entity_manager.entity_added.connect(self.on_entity_added)
        if hasattr(self.entity_manager, 'entity_removed'):
            self.entity_manager.entity_removed.connect(self.on_entity_removed)

        # Widget de légende
        self.legend_widget = None
        self.legend_enabled = True

        # ✅ CORRECTION: Gestionnaire d'échelle AVANT les outils (pour SegmentLabelHelper)
        self.scale_manager = ScaleManager()
        self.scale_manager.scale_changed.connect(self.on_scale_changed)

        # Gestionnaire d'outils (après scale_manager pour que SegmentLabelHelper y ait accès)
        self.tool_manager = ToolManager(self)
        self._setup_tools()

        # Menu contextuel centralise (actions globales + actions outil)
        self.context_menu_service = None
        self._setup_context_menu_service()
        self.context_menu_manager = ContextMenuManager(self.parent_window, self)

        # INITIALISATION DE ORTHO_MANAGER
        self.ortho_manager = OrthoManager()

        # État du canvas
        self.pixmap = None
        self.image_item = None
        self.openings = []
        self.mode = "idle"

        # Initialisation de pixels_per_meter avec valeur par défaut
        self.pixels_per_meter = 100

        # Variables pour le déplacement avec la molette (pan)
        self._pan = False
        self._pan_start = QPoint()
        # Mode pan activé depuis le bouton ruban (clic gauche panné)
        self._pan_mode_active = False

        # Variables pour le déplacement d'entités
        self._drag_button = None  # Bouton ayant initié le drag
        self._dragging_entity = False
        self._dragged_entity = None
        self._drag_start_pos = None
        self._entity_initial_points = None
        self._last_drag_pos = None
        self._click_start_pos = None
        self._click_start_time = None
        self._potential_drag_entity = None
        self.last_left_click_scene_pos = None

        # Attributs pour la fonctionnalité "Mesurer à nouveau" (touche M)
        self.last_entity_created = None
        self.last_surface_properties = None
        self.last_perimeter_properties = None

        # Configuration de la sélection
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setInteractive(True)

        # Activer le focus pour recevoir les événements clavier
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

        # Activer le suivi de la souris
        self.setMouseTracking(True)
        if hasattr(self, 'viewport'):
            self.viewport().setMouseTracking(True)

        # Gestion des limites de zoom
        self.current_zoom = 1.0  # Zoom absolu courant (transform m11)
        self.base_zoom = 1.0     # Zoom de base après fitInView
        self.MIN_ZOOM = 0.2      # Facteur min relatif à base_zoom
        self.MAX_ZOOM = 20.0     # Facteur max relatif à base_zoom

    def _setup_context_menu_service(self):
        """Initialise le service de menu contextuel."""
        try:
            registry = ActionRegistry(self.parent_window, self, self.tool_manager)
            adapter = ToolContextAdapter(self.parent_window, self, self.tool_manager)
            self.context_menu_service = ContextMenuService(
                parent_widget=self,
                registry=registry,
                context_adapter=adapter,
                icon_provider=create_icon_provider(self)
            )
        except Exception as e:
            self.context_menu_service = None

    def _setup_tools(self):
        """Initialise tous les outils avec le gestionnaire"""
        tools_to_register = [
            "surface", "distance", "counter", "scale", "perimeter", "opening"
        ]

        for tool_name in tools_to_register:
            success = self.tool_manager.register_tool(tool_name, tool_name)
            if not success:
                pass

    def setCursor(self, cursor):
        """Applique le curseur sur le viewport (zone interactive réelle)."""
        super().setCursor(cursor)
        self.viewport().setCursor(cursor)

    def set_mode(self, mode):
        """Change le mode actif de la vue (outil courant)"""
        self.mode = mode

        # Mapping des modes aux noms d'outils
        mode_to_tool = {
            "polygon": "surface",
            "surface": "surface",
            "distance": "distance",
            "counter": "counter",
            "scale": "scale",
            "perimeter": "perimeter",
            "opening": "opening",
            "idle": None
        }

        tool_name = mode_to_tool.get(mode)

        if tool_name:
            success = self.tool_manager.activate_tool(tool_name)
            if not success:
                pass
        elif mode == "idle":
            self.tool_manager.deactivate_all_tools()
            # Remettre le curseur flèche si on n'est pas en mode pan
            if not self._pan_mode_active:
                self.setCursor(Qt.ArrowCursor)
        else:
            pass

    def load_image(self, file_path):
        """Charge une image et initialise la légende"""
        try:
            pixmap = QPixmap(file_path)
            return self.display_pixmap(pixmap)
        except Exception as e:
            return False

    def display_pixmap(self, pixmap):
        """Affiche un QPixmap dans la scène (image ou page PDF)"""
        if not pixmap or pixmap.isNull():
            return False

        self.pixmap = pixmap

        # Ajouter l'image à la scène
        if self.image_item:
            self.scene.removeItem(self.image_item)

        self.image_item = QGraphicsPixmapItem(self.pixmap)
        self.scene.addItem(self.image_item)

        # Ajuster la vue
        self.scene.setSceneRect(self.image_item.boundingRect())
        self.fitInView(self.image_item, Qt.KeepAspectRatio)
        # Mettre à jour le zoom de base pour les limites
        self.base_zoom = self.transform().m11()
        self.current_zoom = self.base_zoom

        # ✅ NOUVEAU: Calculer et appliquer l'échelle automatique basée sur la taille de l'image
        image_width = self.pixmap.width()
        image_height = self.pixmap.height()
        self.scale_manager.set_scale_from_image(image_width, image_height)

        # Créer et afficher la légende
        self.create_legend()

        return True

    def create_legend(self):
        """Crée ou met à jour la légende"""
        if not self.legend_enabled:
            return

        # Supprimer l'ancienne légende si elle existe
        if self.legend_widget:
            self.scene.removeItem(self.legend_widget)

        # Créer une nouvelle légende
        self.legend_widget = LegendWidget(self.entity_manager, self.scale_manager)
        self.scene.addItem(self.legend_widget)

        # Positionner au coin supérieur-gauche du plan chargé
        if self.image_item:
            self.legend_widget.snap_to_plan_corner(self.image_item.boundingRect())
        else:
            view_rect = self.mapToScene(self.viewport().rect()).boundingRect()
            self.legend_widget.setPos(view_rect.topLeft() + QPointF(20, 20))

    def update_legend(self):
        """Met à jour le contenu de la légende"""
        if self.legend_widget:
            self.legend_widget.update_legend()

    def on_entity_added(self, entity):
        """Callback quand une entité est ajoutée"""
        if self.debug:
            pass
        self.update_legend()

        # ✅ NOUVEAU : Enregistrer dans l'historique Undo/Redo
        if hasattr(self, 'undo_redo_manager') and entity:
            from core.undo_redo_manager import RemoveEntityCommand
            # On enregistre une commande de suppression (inverse d'ajouter)
            command = RemoveEntityCommand(
                self.entity_manager,
                self.scene,
                entity,
                description=f"Créer '{entity.name}'"
            )
            self.undo_redo_manager.push_command(command)

    def on_entity_removed(self, entity_id):
        """Callback quand une entité est supprimée"""
        if self.debug:
            pass
        self.update_legend()

    def toggle_legend(self):
        """Affiche/masque la légende"""
        if self.legend_widget:
            self.legend_widget.setVisible(not self.legend_widget.isVisible())

    def clear_scene(self):
        """Nettoie la scène et toutes les entités"""
        self.entity_manager.clear_all(self.scene)
        self.tool_manager.deactivate_all_tools()

        # Nettoyage complet de tous les éléments restants
        all_items = list(self.scene.items())
        for item in all_items:
            if item != self.image_item:
                try:
                    # Vérifier que l'item appartient à la scène avant suppression
                    if item.scene() and item.scene() == self.scene:
                        self.scene.removeItem(item)
                except (RuntimeError, AttributeError) as e:
                    pass
                except Exception as e:
                    pass

    def wheelEvent(self, event):
        """Gère le zoom avec la molette de la souris - avec limites"""
        zoom_factor = 1.08

        if event.angleDelta().y() > 0:
            # Zoom IN
            new_zoom = self.current_zoom * zoom_factor
            max_zoom = self.base_zoom * self.MAX_ZOOM
            if new_zoom <= max_zoom:
                self.scale(zoom_factor, zoom_factor)
                self.current_zoom = new_zoom
        else:
            # Zoom OUT
            new_zoom = self.current_zoom / zoom_factor
            min_zoom = self.base_zoom * self.MIN_ZOOM
            if new_zoom >= min_zoom:
                self.scale(1 / zoom_factor, 1 / zoom_factor)
                self.current_zoom = new_zoom

        event.accept()

    def zoom_in(self):
        """Zoom avant - avec limite"""
        zoom_factor = 1.1
        new_zoom = self.current_zoom * zoom_factor
        if new_zoom <= self.base_zoom * self.MAX_ZOOM:
            self.scale(zoom_factor, zoom_factor)
            self.current_zoom = new_zoom

    def zoom_out(self):
        """Zoom arrière - avec limite"""
        zoom_factor = 1.1
        new_zoom = self.current_zoom / zoom_factor
        if new_zoom >= self.base_zoom * self.MIN_ZOOM:
            self.scale(1 / zoom_factor, 1 / zoom_factor)
            self.current_zoom = new_zoom

    def fit_in_view(self):
        """Ajuste la vue pour tout afficher"""
        if self.image_item:
            self.fitInView(self.image_item, Qt.KeepAspectRatio)
            # Mettre à jour le zoom de base selon le transform courant
            self.base_zoom = self.transform().m11()
            self.current_zoom = self.base_zoom

    def reset_zoom(self):
        """Réinitialise le zoom à 100%"""
        if self.current_zoom == 0:
            return
        factor = self.base_zoom / self.current_zoom
        self.scale(factor, factor)
        self.current_zoom = self.base_zoom

    def zoom_to_percent(self, pct: int):
        """Zoom à un pourcentage de la taille de base (100% = taille d'ajustement initiale)."""
        if self.base_zoom == 0 or self.current_zoom == 0:
            return
        target = self.base_zoom * pct / 100.0
        factor = target / self.current_zoom
        self.scale(factor, factor)
        self.current_zoom = target

    def start_crop_selection(self, on_crop_done):
        """Active le mode recadrage — rubber band bleu, sans sélectionner d'items.
        on_crop_done(viewport_rect: QRect) est appelé à la fin du tracé."""
        self._crop_mode = True
        self._crop_callback = on_crop_done
        self._crop_rb_origin = None
        self._crop_rubberband = QRubberBand(QRubberBand.Rectangle, self)
        # Style distinctif (bleu) pour distinguer du zoom (vert par défaut)
        self._crop_rubberband.setStyleSheet(
            "QRubberBand { border: 2px dashed #1976d2; background: rgba(25,118,210,30); }")
        self.setDragMode(self.NoDrag)
        self.setCursor(Qt.CrossCursor)

    def _stop_crop_selection(self):
        """Désactive le mode recadrage et nettoie le rubber band."""
        self._crop_mode = False
        self._crop_callback = None
        if getattr(self, '_crop_rubberband', None):
            self._crop_rubberband.hide()
            self._crop_rubberband = None
        self._crop_rb_origin = None
        self.setCursor(Qt.ArrowCursor)

    def start_zoom_selection(self):
        """Active le mode zoom par sélection — rubber band personnalisé, sans sélectionner d'items."""
        self._zoom_selection_mode = True
        self._zoom_rb_origin = None
        self._zoom_rubberband = QRubberBand(QRubberBand.Rectangle, self)
        self.setDragMode(self.NoDrag)
        self.setCursor(Qt.CrossCursor)

    def _stop_zoom_selection(self):
        """Désactive le mode zoom par sélection et nettoie le rubber band."""
        self._zoom_selection_mode = False
        if getattr(self, '_zoom_rubberband', None):
            self._zoom_rubberband.hide()
            self._zoom_rubberband = None
        self._zoom_rb_origin = None
        self.setCursor(Qt.ArrowCursor)

    def set_pan_mode(self, enabled: bool):
        """Active/désactive le mode pan au clic gauche (utilisé par le bouton ruban)."""
        self._pan_mode_active = enabled
        if enabled:
            self.setCursor(Qt.OpenHandCursor)
        else:
            self._pan = False
            self.setCursor(Qt.ArrowCursor)

    def _apply_zoom_selection(self, viewport_rect: QRect):
        """Zoom sur le rectangle (coordonnées viewport)."""
        if viewport_rect.isNull() or viewport_rect.width() < 5 or viewport_rect.height() < 5:
            return
        scene_rect = self.mapToScene(viewport_rect).boundingRect()
        if scene_rect.isValid():
            self.fitInView(scene_rect, Qt.KeepAspectRatio)
            self.current_zoom = self.transform().m11()

    def mousePressEvent(self, event):
        """Gère les clics de souris avec gestion du pan"""
        scene_pos = self.mapToScene(event.pos())

        # ── Mode recadrage : démarrer le rubber band bleu ─────────────────────
        if event.button() == Qt.LeftButton and getattr(self, '_crop_mode', False):
            self._crop_rb_origin = event.pos()
            self._crop_rubberband.setGeometry(QRect(self._crop_rb_origin, QSize()))
            self._crop_rubberband.show()
            event.accept()
            return

        # ── Mode zoom par sélection : démarrer le rubber band ─────────────────
        if event.button() == Qt.LeftButton and getattr(self, '_zoom_selection_mode', False):
            self._zoom_rb_origin = event.pos()
            self._zoom_rubberband.setGeometry(QRect(self._zoom_rb_origin, QSize()))
            self._zoom_rubberband.show()
            event.accept()
            return

        # Mémoriser la dernière position de clic gauche pour le collage contextuel.
        if event.button() == Qt.LeftButton:
            self.last_left_click_scene_pos = QPointF(scene_pos)

        # Clic hors de la légende → quitter le mode redimensionnement
        if (event.button() == Qt.LeftButton
                and self.legend_widget
                and self.legend_widget._resize_mode):
            from ui.legend_widget import _ResizeHandle
            items_at = self.scene.items(scene_pos)
            on_legend = any(
                item is self.legend_widget or isinstance(item, _ResizeHandle)
                for item in items_at
            )
            if not on_legend:
                self.legend_widget.exit_resize_mode()

        # Clic hors d'un widget redimensionnable → quitter leur mode resize
        if event.button() == Qt.LeftButton:
            items_at = self.scene.items(scene_pos)

            from ui.note_widget import NoteWidget, _NoteHandle
            for note in [i for i in self.scene.items() if isinstance(i, NoteWidget)]:
                if note._resize_mode:
                    on_note = any(
                        item is note or isinstance(item, _NoteHandle)
                        for item in items_at
                    )
                    if not on_note:
                        note.exit_resize_mode()

            from ui.marker_widget import MarkerWidget, _MarkerHandle
            for mk in [i for i in self.scene.items() if isinstance(i, MarkerWidget)]:
                if mk._resize_mode:
                    on_mk = any(
                        item is mk or isinstance(item, _MarkerHandle)
                        for item in items_at
                    )
                    if not on_mk:
                        mk.exit_resize_mode()

        # PRIORITÉ 1: Gestion du pan (clic milieu OU clic gauche en mode pan)
        if event.button() == Qt.MiddleButton or (
                event.button() == Qt.LeftButton and self._pan_mode_active):
            self._pan = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        # Vérifier si une entité est en mode création d'ouverture
        if event.button() == Qt.LeftButton:
            if hasattr(self, 'entity_manager') and self.entity_manager:
                for entity in self.entity_manager.get_all_entities():
                    # Vérifier si c'est un PerimeterEntity en mode création d'ouverture
                    if (hasattr(entity, 'opening_creation_mode') and
                        entity.opening_creation_mode and
                        hasattr(entity, 'is_editing') and
                            entity.is_editing):

                        # Appeler la méthode de gestion des clics
                        if hasattr(entity, 'handle_opening_click'):
                            entity.handle_opening_click(scene_pos, event)
                            event.accept()
                            return

        # Détecter si on clique sur un handle
        items = self.scene.items(scene_pos)
        for item in items:
            # Imports pour vérifier le type
            from entities.perimeter_entity import PerimeterAnchorPoint
            from entities.polygon_entity import AnchorPoint as PolygonAnchorPoint
            from entities.line_entity import LineAnchorPoint
            from entities.opening_entity import AnchorPoint as OpeningAnchorPoint

            if isinstance(item, (PerimeterAnchorPoint, PolygonAnchorPoint, LineAnchorPoint, OpeningAnchorPoint)):
                super().mousePressEvent(event)
                return

        # Délégation au gestionnaire d'outils
        if self._is_tool_active():
            if self.tool_manager.handle_mouse_press(event, scene_pos):
                return

        # Clic sur une entité existante (pour sélection/déplacement)
        entity = self._get_entity_at_position(scene_pos)
        if entity:
            # Clic droit sur entité: afficher le menu contextuel si disponible
            if event.button() == Qt.RightButton:
                # Priorité au menu specialise Surface si on clique une surface
                if self.context_menu_manager and self.context_menu_manager.show_menu(event, entity):
                    event.accept()
                elif self.context_menu_service and self.context_menu_service.exec_if_needed(event.globalPos()):
                    event.accept()
                else:
                    event.ignore()
                return
            # 🔒 Bloquer toute sélection/drag si autre bouton que gauche
            if event.button() != Qt.LeftButton:
                event.ignore()
                return

            # ── MarkerEntity : laisser Qt gérer le drag via ItemIsMovable ─────
            if getattr(entity, 'entity_type', '') == 'marker':
                self._select_entity(entity)
                mw = getattr(self, 'parent_window', None)
                if mw and hasattr(mw, 'properties_dock') and mw.properties_dock:
                    mw.properties_dock.display_entity_properties(entity)
                super().mousePressEvent(event)
                return

            # ✅ NOUVEAU: Vérifier si l'entité peut être sélectionnée (calque actif, non verrouillé)
            entity_id = getattr(entity, 'entity_id', None)
            if entity_id and not self.can_select_entity(entity_id):
                # L'entité ne peut pas être sélectionnée
                event.ignore()
                if hasattr(self, 'parent_window') and hasattr(self.parent_window, 'statusBar'):
                    self.parent_window.statusBar().showMessage(
                        "⚠️ Cette entité ne peut pas être sélectionnée (calque inactif ou verrouillé)", 2000
                    )
                return
            
            # Vérifier si l'entité est en mode édition (handles actifs)
            if hasattr(entity, 'is_editing') and entity.is_editing:
                # Les handles sont actifs, ne pas déplacer l'entité
                # Laisser les handles gérer l'événement
                event.ignore()
                return

            # Stocker l'entité et la position du clic pour détecter le mouvement
            self._drag_button = event.button()  # mémoriser le bouton
            self._potential_drag_entity = entity
            self._click_start_pos = event.pos()
            from PyQt5.QtCore import QTime
            self._click_start_time = QTime.currentTime()
            # Mémoriser la sélection courante pour un drag multi
            try:
                self._pre_click_selection = self.get_selected_entities()
            except Exception:
                self._pre_click_selection = None

            # Sélectionner l'entité immédiatement
            self._select_entity(entity)

            # Ne pas accepter l'événement tout de suite, attendre de voir si c'est un mouvement
            event.accept()
            return

        # Gérer le clic droit générique
        if event.button() == Qt.RightButton:
            if self.context_menu_manager and self.context_menu_manager.show_menu(event, None):
                event.accept()
            elif self.context_menu_service and self.context_menu_service.exec_if_needed(event.globalPos()):
                event.accept()
            else:
                event.ignore()
            return

        # Clic gauche dans le vide (pas d'entité ciblée) :
        # sortir automatiquement du mode édition (handles) pour éviter
        # d'imposer ESC à chaque fois.
        if event.button() == Qt.LeftButton and not self._is_tool_active():
            if self._exit_edit_mode_on_empty_click():
                event.accept()
                return

        super().mousePressEvent(event)

    def _exit_edit_mode_on_empty_click(self) -> bool:
        """
        Désactive le mode édition des entités en cours (surfaces/périmètres/lignes/ouvertures)
        quand l'utilisateur clique dans le vide du canvas.
        Retourne True si au moins une entité a quitté le mode édition.
        """
        manager = getattr(self, "entity_manager", None)
        if not manager:
            return False

        exited = False
        for entity in manager.get_all_entities():
            if not getattr(entity, "is_editing", False):
                continue
            if hasattr(entity, "disable_editing"):
                try:
                    entity.disable_editing(self.scene)
                    exited = True
                except Exception as e:
                    pass

        if exited and hasattr(self, "parent_window") and self.parent_window:
            if hasattr(self.parent_window, "measure_label"):
                self.parent_window.measure_label.setText("Mode édition désactivé")
        return exited

    def mouseMoveEvent(self, event):
        # ── Mode recadrage : mettre à jour le rubber band bleu ─────────────────
        if getattr(self, '_crop_mode', False) and getattr(self, '_crop_rb_origin', None):
            self._crop_rubberband.setGeometry(
                QRect(self._crop_rb_origin, event.pos()).normalized()
            )
            event.accept()
            return

        # ── Mode zoom par sélection : mettre à jour le rubber band ─────────────
        if getattr(self, '_zoom_selection_mode', False) and getattr(self, '_zoom_rb_origin', None):
            self._zoom_rubberband.setGeometry(
                QRect(self._zoom_rb_origin, event.pos()).normalized()
            )
            event.accept()
            return

        # Gestion du pan
        if self._pan:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return

        # Re-enforcer le curseur main quand mode pan actif (sans glisser)
        if self._pan_mode_active:
            self.viewport().setCursor(Qt.OpenHandCursor)

        # Détecter si on est en train de commencer un déplacement
        if (self._potential_drag_entity and
            self._click_start_pos and
                not self._dragging_entity and
                self._drag_button == Qt.LeftButton):

            # Vérifier si l'entité est toujours disponible et pas en mode édition
            entity = self._potential_drag_entity
            # Bloquer si l'entité elle-même est en édition OU si une de ses ouvertures l'est
            entity_editing = hasattr(entity, 'is_editing') and entity.is_editing
            opening_editing = (
                hasattr(entity, 'openings')
                and any(
                    getattr(op, 'is_editing', False)
                    for op in entity.openings
                )
            )
            if entity_editing or opening_editing:
                # En mode édition (entité ou ouverture), ne pas déplacer
                self._potential_drag_entity = None
                self._click_start_pos = None
            else:
                # Calculer la distance depuis le clic initial
                delta_pos = event.pos() - self._click_start_pos
                distance = (delta_pos.x()**2 + delta_pos.y()**2) ** 0.5

                # Si le mouvement est suffisant (seuil de 5 pixels), commencer le déplacement
                if distance > 5:
                    scene_pos = self.mapToScene(self._click_start_pos)
                    self._start_entity_drag(entity, scene_pos)
                    self._potential_drag_entity = None
                    self._click_start_pos = None

        # Gérer le déplacement d'entité
        if self._dragging_entity and self._dragged_entity:
            # Vérifier que ni l'entité ni ses ouvertures ne sont en mode édition
            dragged_editing = (
                hasattr(self._dragged_entity, 'is_editing')
                and self._dragged_entity.is_editing
            )
            dragged_opening_editing = (
                hasattr(self._dragged_entity, 'openings')
                and any(
                    getattr(op, 'is_editing', False)
                    for op in self._dragged_entity.openings
                )
            )
            if dragged_editing or dragged_opening_editing:
                # Annuler le déplacement si l'entité ou une ouverture est en mode édition
                self._cancel_entity_drag()
                event.accept()
                return

            scene_pos = self.mapToScene(event.pos())
            self._update_entity_drag(scene_pos)
            event.accept()
            return

        if self.image_item is None:
            return

        original_pos = self.mapToScene(event.pos())
        pos = original_pos

        # CORRECTION: Appliquer le mode ortho pour tous les outils, y compris l'outil échelle
        apply_ortho = False
        if (self.ortho_manager and self.ortho_manager.is_ortho_enabled() and
                hasattr(self.tool_manager, 'current_tool') and self.tool_manager.current_tool):

            # CORRECTION: Permettre le mode ortho pour tous les outils, y compris l'échelle
            apply_ortho = True

        # Appliquer le mode ortho si activé
        if apply_ortho:
            # Récupérer le dernier point de référence de l'outil
            last_point = None
            tool = self.tool_manager.current_tool

            # Vérifier différents attributs selon l'outil
            if hasattr(tool, 'points') and tool.points:
                last_point = tool.points[-1]
            elif hasattr(tool, 'start_point') and tool.start_point:
                last_point = tool.start_point
            elif hasattr(tool, 'last_point') and tool.last_point:
                last_point = tool.last_point

            # Appliquer la contrainte ortho si on a un point de référence
            if last_point:
                # Calculer les deltas
                delta_x = abs(original_pos.x() - last_point.x())
                delta_y = abs(original_pos.y() - last_point.y())

                # Déterminer l'axe dominant avec un seuil pour éviter les oscillations
                ortho_threshold = 5  # pixels
                if abs(delta_x - delta_y) < ortho_threshold:
                    # Trop proche, ne pas contraindre pour éviter les oscillations
                    pass
                elif delta_x > delta_y:
                    # Mouvement horizontal dominant - contraindre à l'axe Y
                    pos = QPointF(original_pos.x(), last_point.y())
                else:
                    # Mouvement vertical dominant - contraindre à l'axe X
                    pos = QPointF(last_point.x(), original_pos.y())

        # Délégation au gestionnaire d'outils (seulement si le pan n'est pas actif)
        if self.tool_manager.handle_mouse_move(event, pos):
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Gère le relâchement de souris"""
        if self._pan and event.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._pan = False
            # En mode pan actif, revenir à la main ouverte ; sinon flèche normale
            self.setCursor(Qt.OpenHandCursor if self._pan_mode_active else Qt.ArrowCursor)
            event.accept()
            return

        # ── Mode recadrage rubber-band ─────────────────────────────────────────
        if event.button() == Qt.LeftButton and getattr(self, '_crop_mode', False):
            rb_rect = None
            if getattr(self, '_crop_rubberband', None) and getattr(self, '_crop_rb_origin', None):
                rb_rect = QRect(self._crop_rb_origin, event.pos()).normalized()
            callback = getattr(self, '_crop_callback', None)
            self._stop_crop_selection()
            if rb_rect and not rb_rect.isNull() and callback:
                callback(rb_rect)
            event.accept()
            return

        # Mode zoom par sélection rubber-band
        if event.button() == Qt.LeftButton and getattr(self, '_zoom_selection_mode', False):
            rb_rect = None
            if getattr(self, '_zoom_rubberband', None) and getattr(self, '_zoom_rb_origin', None):
                rb_rect = QRect(self._zoom_rb_origin, event.pos()).normalized()
            self._stop_zoom_selection()
            if rb_rect and not rb_rect.isNull():
                self._apply_zoom_selection(rb_rect)
            event.accept()
            return

        # Gérer le relâchement du clic gauche
        if event.button() == Qt.LeftButton:
            # Si on était en train de déplacer une entité, terminer le déplacement
            if self._dragging_entity:
                self._finish_entity_drag()
                event.accept()
                return
            # Réinitialiser le bouton de drag
            self._drag_button = None

            # Si on avait une entité potentiellement sélectionnée mais pas de mouvement,
            # c'était juste un clic simple de sélection (déjà fait dans mousePressEvent)
            if self._potential_drag_entity:
                self._potential_drag_entity = None
                self._click_start_pos = None
                self._click_start_time = None
            self._pre_click_selection = None

        # Délégation au gestionnaire d'outils (seulement si le pan n'est pas actif)
        if not self._pan:
            scene_pos = self.mapToScene(event.pos())
            if self.tool_manager.handle_mouse_release(event, scene_pos):
                return

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Gère le double-clic sur la vue"""
        scene_pos = self.mapToScene(event.pos())

        # Vérifier si on double-clique sur un item existant
        items = self.scene.items(scene_pos)

        # Trier par Z-value (du plus haut au plus bas)
        items = sorted(items, key=lambda item: item.zValue()
                       if hasattr(item, 'zValue') else 0, reverse=True)

        for item in items:
            # Vérifier que l'item a la méthode data avant utilisation
            if not hasattr(item, 'data'):
                continue

            # Si c'est une ligne, polygone ou ouverture, laisser l'entité gérer
            try:
                data_type = item.data(0)
                if data_type in ("line_entity", "polygon_entity", "opening_entity"):

                    # Transmettre l'événement à l'entité
                    entity_id = item.data(1)
                    if entity_id:
                        entity = self.entity_manager.get_entity(entity_id)
                        if entity:
                            if hasattr(entity, 'mouseDoubleClickEvent'):
                                entity.mouseDoubleClickEvent(event)
                                if event.isAccepted():
                                    return
            except (TypeError, AttributeError) as e:
                continue

        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        """Gère les touches du clavier"""
        # Si un QGraphicsTextItem est en cours d'édition (ex : outil Note),
        # laisser tous les événements clavier passer directement sans interception.
        focused = self.scene.focusItem() if self.scene else None
        if focused is not None and hasattr(focused, 'textInteractionFlags'):
            if focused.textInteractionFlags() & Qt.TextEditorInteraction:
                super().keyPressEvent(event)
                return

        # Touche M pour mode "Mesurer à nouveau"
        if event.key() == Qt.Key_M:
            self.activate_continue_measure_mode()
            event.accept()
            return

        if event.key() == Qt.Key_Escape:
            # Désactiver complètement l'outil
            self.cancel_all_tools()
            event.accept()
            return

        if event.key() == Qt.Key_Delete:
            self.delete_selected_entities()
            event.accept()
            return

        # Touche P : ouverture linéaire sur le périmètre sélectionné
        if event.key() == Qt.Key_P:
            perimeter = None
            # 1) Chercher un périmètre marqué selected=True dans le gestionnaire d'entités
            if hasattr(self, 'entity_manager') and self.entity_manager:
                for ent in self.entity_manager.get_all_entities():
                    if (getattr(ent, 'entity_type', '') == 'perimeter'
                            and getattr(ent, 'selected', False)):
                        perimeter = ent
                        break
            # 2) Fallback : entité affichée dans le panneau des propriétés
            if perimeter is None:
                mw = getattr(self, 'parent_window', None)
                if mw and hasattr(mw, 'properties_dock') and mw.properties_dock:
                    ent = getattr(mw.properties_dock, 'current_entity', None)
                    if ent and getattr(ent, 'entity_type', '') == 'perimeter':
                        perimeter = ent
            # 3) Lancer la création d'ouverture sur le périmètre trouvé
            if perimeter is not None:
                mw = getattr(self, 'parent_window', None)
                if mw:
                    if (hasattr(mw, 'context_menu_manager')
                            and mw.context_menu_manager
                            and hasattr(mw.context_menu_manager,
                                        '_cb_create_linear_opening_on_perimeter')):
                        mw.context_menu_manager._cb_create_linear_opening_on_perimeter(
                            perimeter)
                    elif hasattr(mw, 'start_linear_opening_on_selected_perimeter'):
                        perimeter.set_selected(True)
                        mw.start_linear_opening_on_selected_perimeter()
            else:
                mw = getattr(self, 'parent_window', None)
                if mw and hasattr(mw, 'statusBar'):
                    mw.statusBar().showMessage(
                        "❌ Sélectionnez d'abord un périmètre (P)", 3000)
            event.accept()
            return

        # Gestion du mode ortho avec la touche O
        if event.key() == Qt.Key_O:
            if hasattr(self, 'ortho_manager') and self.ortho_manager:
                new_state = self.ortho_manager.toggle_ortho()
                # Mettre à jour l'interface
                if hasattr(self.parent_window, 'update_ortho_indicator'):
                    self.parent_window.update_ortho_indicator(new_state)
                if hasattr(self.parent_window, "measure_label"):
                    status = "ACTIVÉ" if new_state else "DÉSACTIVÉ"
                    self.parent_window.measure_label.setText(
                        f"Mode Ortho {status}")
                event.accept()
                return

        # Délégation au gestionnaire d'outils
        if self.tool_manager.handle_key_press(event):
            return

        super().keyPressEvent(event)

    def activate_continue_measure_mode(self):
        """Active le mode pour continuer à mesurer (touche M)"""

        selected_entities = self.get_selected_entities()
        source_entity = None

        if selected_entities:
            for entity in selected_entities:
                if hasattr(entity, 'entity_type') and entity.entity_type == 'point':
                    source_entity = entity
                    break

        # ✅ Mode ajout pour Compteur (point)
        if source_entity and getattr(source_entity, 'entity_type', '') == 'point':
            manager = getattr(self, 'entity_manager', None)
            name = getattr(source_entity, 'name', 'Compteur')
            group_id = getattr(source_entity, 'group_id', None)

            if manager:
                if not group_id:
                    group_id = manager.ensure_point_group(name)
                group_points = manager.get_points_by_group(group_id)
            else:
                group_points = []

            leader = group_points[0] if group_points else source_entity

            tool = self.tool_manager.get_tool('counter')
            if tool:
                tool.preconfigured_name = getattr(leader, 'name', name)
                tool.preconfigured_color = getattr(
                    leader, 'color', QColor(255, 0, 0, 200))
                tool.preconfigured_shape = getattr(leader, 'shape', 'circle')
                tool.preconfigured_size = getattr(leader, 'size', 14)
                tool.group_mode = True
                tool.group_id = group_id

                success = self.tool_manager.activate_tool('counter')
                if success:
                    count = len(group_points) if group_points else 1
                    if hasattr(self.parent_window, "measure_label"):
                        self.parent_window.measure_label.setText(
                            f"➕ Ajouter à '{tool.preconfigured_name}' ({count}) - Cliquez pour ajouter"
                        )
                    if hasattr(self.parent_window, 'counter_action'):
                        self.parent_window.counter_action.setChecked(True)
                else:
                    pass
            else:
                pass
            return

        # ✅ Mode ajout pour surfaces / périmètres
        source_entity = None

        if selected_entities:
            for entity in selected_entities:
                # ✅ AMÉLIORATION: Gérer surfaces ET périmètres
                if hasattr(entity, 'entity_type') and entity.entity_type in ['surface', 'polygon', 'perimeter']:
                    source_entity = entity
                    entity_type_label = 'Surface' if entity.entity_type in [
                        'surface', 'polygon'] else 'Périmètre'

                    # IMPORTANT: Si c'est un enfant, TOUJOURS utiliser le parent
                    if hasattr(entity, 'parent_entity') and entity.parent_entity is not None:
                        source_entity = entity.parent_entity
                    elif hasattr(entity, 'is_group_parent') and entity.is_group_parent:
                        pass
                    else:
                        pass
                    break

        # Si pas de sélection, utiliser la dernière entité créée (surface ou périmètre)
        if not source_entity and hasattr(self, 'last_entity_created') and self.last_entity_created:
            # ✅ AMÉLIORATION: Gérer surfaces ET périmètres
            if hasattr(self.last_entity_created, 'entity_type') and \
               self.last_entity_created.entity_type in ['surface', 'polygon', 'perimeter']:
                source_entity = self.last_entity_created
                # Vérifier aussi si la dernière créée est un enfant
                if hasattr(source_entity, 'parent_entity') and source_entity.parent_entity is not None:
                    source_entity = source_entity.parent_entity

        if not source_entity:
            if hasattr(self.parent_window, "measure_label"):
                self.parent_window.measure_label.setText(
                    "⚠️ Sélectionnez d'abord une surface ou un périmètre à laquelle/auquel ajouter")
            return

        # Marquer comme parent si pas déjà fait
        if not getattr(source_entity, 'is_group_parent', False):
            source_entity.is_group_parent = True
            import uuid
            source_entity.group_id = f"group_{uuid.uuid4().hex[:8]}"
            if not hasattr(source_entity, 'child_entities'):
                source_entity.child_entities = []

        # Le nom du groupe suit le nom de l'entité source
        if not getattr(source_entity, 'group_name', None):
            source_entity.group_name = getattr(source_entity, 'name', None) or ""

        # ✅ AMÉLIORATION: Déterminer le type d'entité et l'outil à utiliser
        is_perimeter = getattr(source_entity, 'entity_type', '') == 'perimeter'
        tool_name = 'perimeter' if is_perimeter else 'surface'
        entity_label = 'Périmètre' if is_perimeter else 'Surface'

        # Extraire les propriétés (l'affichage des mesures suit le groupe)
        properties = {
            'name': getattr(source_entity, 'name', entity_label),
            'color': getattr(source_entity, 'color', QColor(0, 0, 255) if is_perimeter else QColor(0, 255, 0, 100)),
            'width': getattr(source_entity, 'width', 2),
            'show_measure': getattr(source_entity, 'show_measure', False),
            'group_id': source_entity.group_id,
            'parent_entity': source_entity
        }

        # Pour les surfaces uniquement
        if not is_perimeter:
            properties['pattern'] = getattr(
                source_entity, 'fill_pattern', Qt.SolidPattern)

        # IMPORTANT: Obtenir l'outil AVANT de l'activer
        tool = self.tool_manager.get_tool(tool_name)

        if tool:
            # Pré-configurer les propriétés AVANT activation
            tool.preconfigured_name = properties['name']
            tool.preconfigured_color = properties['color']
            tool.preconfigured_show_measure = properties['show_measure']

            if not is_perimeter:
                # Propriétés spécifiques aux surfaces
                tool.preconfigured_pattern = properties['pattern']
            else:
                # Propriétés spécifiques aux périmètres
                if hasattr(tool, 'preconfigured_width'):
                    tool.preconfigured_width = properties['width']

            # Activer le mode groupe AVANT activation
            tool.group_mode = True
            tool.group_id = properties['group_id']
            tool.parent_entity = properties['parent_entity']

            # Maintenant activer l'outil (ne devrait pas ouvrir le dialogue)
            success = self.tool_manager.activate_tool(tool_name)

            if success:
                count = len(source_entity.child_entities) + 1

                if hasattr(self.parent_window, "measure_label"):
                    self.parent_window.measure_label.setText(
                        f"➕ Ajouter à '{properties['name']}' ({count}) - Dessinez | ESC pour quitter"
                    )

                # Cocher le bouton approprié dans l'interface
                if hasattr(self.parent_window, f'{tool_name}_action'):
                    getattr(self.parent_window,
                            f'{tool_name}_action').setChecked(True)
            else:
                pass
        else:
            pass

    def cancel_current_measurement_only(self):
        """Annule uniquement la mesure en cours sans désactiver l'outil"""

        current_tool = self.tool_manager.current_tool

        if current_tool and hasattr(current_tool, 'cancel'):
            # Annuler la mesure en cours
            current_tool.cancel()

            # Message selon le type d'outil
            if hasattr(current_tool, 'preconfigured_name') and current_tool.preconfigured_name:
                if hasattr(self.parent_window, "measure_label"):
                    self.parent_window.measure_label.setText(
                        f"❌ Mesure annulée - '{current_tool.preconfigured_name}' toujours actif")
            else:
                if hasattr(self.parent_window, "measure_label"):
                    self.parent_window.measure_label.setText(
                        "❌ Mesure annulée - Outil toujours actif")
        else:
            # Si pas d'outil actif, comportement normal (tout désactiver)
            self.cancel_all_tools()

    def cancel_all_tools(self):
        """Désactive complètement tous les outils (ancien comportement ESC)"""
        self.tool_manager.deactivate_all_tools()

        if hasattr(self.parent_window, "measure_label"):
            self.parent_window.measure_label.setText("Outil désactivé")

        # Décocher toutes les actions d'outils
        if hasattr(self.parent_window, 'tool_actions'):
            for action in self.parent_window.tool_actions:
                action.setChecked(False)

    def store_created_entity_properties(self, entity):
        """Mémorise les propriétés d'une entité nouvellement créée"""
        if hasattr(entity, 'entity_type') and entity.entity_type in ['surface', 'polygon']:
            self.last_entity_created = entity
            self.last_surface_properties = {
                'name': getattr(entity, 'name', 'Surface'),
                'color': getattr(entity, 'color', QColor(0, 255, 0, 100)),
                'pattern': getattr(entity, 'fill_pattern', Qt.SolidPattern),
                'show_measure': getattr(entity, 'show_measure', False)
            }

    def _is_tool_active(self):
        """Vérifie si un outil est actuellement actif"""
        return (hasattr(self, 'tool_manager') and
                self.tool_manager and
                self.tool_manager.current_tool is not None)

    def _get_entity_at_position(self, scene_pos):
        """Retourne l'entité à la position donnée"""
        if not hasattr(self, 'scene') or not self.scene:
            return None

        items = self.scene.items(scene_pos)
        for item in items:
            if hasattr(item, 'data'):
                try:
                    entity_id = item.data(1)
                    if entity_id and hasattr(self, 'entity_manager'):
                        entity = self.entity_manager.get_entity(entity_id)
                        if entity:
                            return entity
                except (TypeError, AttributeError):
                    continue
        return None

    def _select_entity(self, entity):
        """Sélectionne une entité"""
        if not entity:
            return

        if hasattr(self.scene, 'entitySelected'):
            self.scene.entitySelected.emit(entity)

        if hasattr(entity, 'set_selected'):
            entity.set_selected(True)

    def _start_entity_drag(self, entity, scene_pos):
        """Démarre le déplacement d'une entité"""
        # Refuser le déplacement si une ouverture de cette entité est en mode édition
        if hasattr(entity, 'openings') and any(
            getattr(op, 'is_editing', False) for op in entity.openings
        ):
            return
        self._dragging_entity = True
        self._dragged_entity = entity
        self._drag_start_pos = scene_pos
        self._last_drag_pos = scene_pos
        self._dragged_entities = None
        self._drag_initial_state = None

        selected = self.get_selected_entities() if hasattr(self, 'get_selected_entities') else []
        pre_selected = getattr(self, '_pre_click_selection', None)
        if pre_selected and entity in pre_selected and len(pre_selected) > 1:
            self._dragged_entities = pre_selected
        elif selected and entity in selected:
            self._dragged_entities = selected
        else:
            self._dragged_entities = [entity]

        self._drag_initial_state = {}
        for ent in self._dragged_entities:
            if hasattr(ent, 'points'):
                self._drag_initial_state[id(ent)] = {
                    'points': [QPointF(p) for p in ent.points]
                }
            elif hasattr(ent, 'position'):
                self._drag_initial_state[id(ent)] = {
                    'position': QPointF(ent.position)
                }

    def _update_entity_drag(self, scene_pos):
        """Met à jour la position pendant le déplacement"""
        if not self._dragged_entity or not self._last_drag_pos:
            return

        delta = scene_pos - self._last_drag_pos
        self._last_drag_pos = scene_pos

        for ent in (self._dragged_entities or [self._dragged_entity]):
            if hasattr(ent, 'move_by'):
                ent.move_by(delta.x(), delta.y())
            elif hasattr(ent, 'points'):
                for i, point in enumerate(ent.points):
                    ent.points[i] = QPointF(point.x() + delta.x(),
                                            point.y() + delta.y())
                if hasattr(ent, 'draw') and hasattr(ent, 'scene_ref'):
                    ent.draw(ent.scene_ref)

    def _finish_entity_drag(self):
        """Termine le déplacement d'une entité"""
        if self._dragged_entity:
            for ent in (self._dragged_entities or [self._dragged_entity]):
                if hasattr(ent, 'geometryChanged'):
                    ent.geometryChanged.emit()

        self._dragging_entity = False
        self._dragged_entity = None
        self._drag_start_pos = None
        self._last_drag_pos = None
        self._entity_initial_points = None
        self._dragged_entities = None
        self._drag_initial_state = None
        self._pre_click_selection = None

    def _cancel_entity_drag(self):
        """Annule le déplacement en cours"""
        if self._dragged_entity and self._drag_initial_state:
            for ent in (self._dragged_entities or [self._dragged_entity]):
                state = self._drag_initial_state.get(id(ent), {})
                if 'points' in state and hasattr(ent, 'points'):
                    ent.points = state['points']
                    if hasattr(ent, 'draw') and hasattr(ent, 'scene_ref'):
                        ent.draw(ent.scene_ref)
                elif 'position' in state and hasattr(ent, 'position'):
                    ent.position = state['position']
                    if hasattr(ent, 'point_item') and ent.point_item:
                        ent.point_item.setPos(ent.position)
                    if hasattr(ent, '_update_text_positions'):
                        ent._update_text_positions()

        self._dragging_entity = False
        self._dragged_entity = None
        self._drag_start_pos = None
        self._last_drag_pos = None
        self._entity_initial_points = None
        self._dragged_entities = None
        self._drag_initial_state = None
        self._pre_click_selection = None

    def get_selected_entities(self):
        """Retourne la liste des entités sélectionnées"""
        selected = []

        # ✅ NOUVEAU : Utiliser la sélection Qt native (plus fiable)
        if hasattr(self, 'scene') and self.scene:
            selected_items = self.scene.selectedItems()

            for item in selected_items:
                if hasattr(item, 'data'):
                    try:
                        entity_id = item.data(1)
                        if entity_id and hasattr(self, 'entity_manager'):
                            entity = self.entity_manager.get_entity(entity_id)
                            if entity:
                                # Éviter les doublons
                                if entity not in selected:
                                    selected.append(entity)
                    except (TypeError, AttributeError):
                        continue

        # ✅ FALLBACK : Si aucune sélection Qt, vérifier via is_selected() (ancienne méthode)
        if not selected and hasattr(self, 'entity_manager') and self.entity_manager:
            for entity in self.entity_manager.get_all_entities():
                if hasattr(entity, 'is_selected') and callable(entity.is_selected):
                    try:
                        if entity.is_selected():
                            selected.append(entity)
                    except Exception as e:
                        pass

        return selected

    def delete_selected_entities(self):
        """Supprime les entités sélectionnées"""
        selected = self.get_selected_entities()

        if not selected:
            if hasattr(self, 'parent_window'):
                self.parent_window.statusBar().showMessage(
                    "⚠️ Aucune entité sélectionnée", 2000
                )
            return

        # ✅ NOUVEAU : Confirmation si multiple sélection
        count = len(selected)
        if count > 1:
            if hasattr(self, 'parent_window'):
                self.parent_window.statusBar().showMessage(
                    f"🗑️ Suppression de {count} entités...", 2000
                )

        # ✅ NOUVEAU : Enregistrer chaque suppression dans l'historique Undo/Redo
        if hasattr(self, 'parent_window') and hasattr(self.parent_window, 'undo_redo_manager'):
            from core.undo_redo_manager import RemoveEntityCommand

            for entity in selected:
                if hasattr(entity, 'entity_id'):
                    # Créer la commande AVANT de supprimer
                    command = RemoveEntityCommand(
                        self.entity_manager,
                        self.scene,
                        entity,
                        description=f"Supprimer '{entity.name}'"
                    )
                    # Enregistrer (sera exécutée par remove_entity ci-dessous)
                    self.parent_window.undo_redo_manager.push_command(command)

        # ✅ Supprimer toutes les entités sélectionnées
        for i, entity in enumerate(selected, 1):
            if hasattr(entity, 'entity_id') and hasattr(self, 'entity_manager'):
                entity_name = getattr(entity, 'name', 'Sans nom')
                self.entity_manager.remove_entity(entity.entity_id, self.scene)

        # ✅ Nettoyer les items orphelins
        if hasattr(self, 'clean_orphaned_items'):
            self.clean_orphaned_items()

        # ✅ NOUVEAU : Afficher un message de confirmation
        if hasattr(self, 'parent_window'):
            if count == 1:
                self.parent_window.statusBar().showMessage(
                    f"✅ '{selected[0].name}' supprimé", 2000
                )
            else:
                self.parent_window.statusBar().showMessage(
                    f"✅ {count} entités supprimées", 2000
                )


    def clean_orphaned_items(self):
        """Nettoie les items graphiques orphelins"""
        if not hasattr(self, 'scene') or not self.scene:
            return

        items_to_remove = []
        for item in self.scene.items():
            if item == self.image_item:
                continue

            if hasattr(item, 'data'):
                try:
                    entity_id = item.data(1)
                    if entity_id and hasattr(self, 'entity_manager'):
                        entity = self.entity_manager.get_entity(entity_id)
                        if not entity:
                            items_to_remove.append(item)
                except (TypeError, AttributeError):
                    pass

        for item in items_to_remove:
            try:
                if item.scene() == self.scene:
                    self.scene.removeItem(item)
            except (RuntimeError, AttributeError):
                pass
    
    def can_select_entity(self, entity_id):
        """Vérifie si une entité peut être sélectionnée."""
        return True
    
    def on_scale_changed(self, new_scale):
        """
        Appelé quand l'échelle change.
        Redessine toutes les entités avec la nouvelle échelle.
        """
        if self.debug:
            pass
        
        # Redessiner toutes les entités avec la nouvelle échelle
        if hasattr(self, 'entity_manager'):
            entities = self.entity_manager.get_all_entities()
            if self.debug:
                pass
            
            for i, entity in enumerate(entities):
                if hasattr(entity, 'draw') and hasattr(entity, 'scene_ref'):
                    try:
                        entity_type = getattr(entity, 'entity_type', 'entity')
                        entity_name = getattr(entity, 'name', '?')
                        if self.debug:
                            pass
                        
                        # Si l'entité est en mode édition, recréer les anchor points
                        was_editing = getattr(entity, 'is_editing', False)
                        if was_editing:
                            if self.debug:
                                pass
                            if hasattr(entity, 'disable_editing'):
                                entity.disable_editing(entity.scene_ref)
                        
                        # Redessiner l'entité
                        if self.debug:
                            pass
                        entity.draw(entity.scene_ref)
                        
                        # Réactiver le mode édition si nécessaire
                        if was_editing and hasattr(entity, 'enable_editing'):
                            if self.debug:
                                pass
                            entity.enable_editing(entity.scene_ref)
                        
                        if self.debug:
                            pass
                    except Exception as e:
                        if self.debug:
                            pass
        
        # Mettre à jour la légende si elle existe
        if hasattr(self, 'legend_widget') and self.legend_widget:
            if self.debug:
                pass
            self.create_legend()
        
        # Rafraîchir la vue
        if hasattr(self, 'scene'):
            if self.debug:
                pass
            self.scene.update()

        if self.debug:
            pass
