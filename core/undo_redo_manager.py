"""
Gestionnaire Undo/Redo pour l'application
"""
from PyQt5.QtCore import QObject, pyqtSignal
import copy


def create_entity_snapshot(entity):
    """Crée un snapshot complet de l'entité passée en paramètre"""
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QColor

    entity_type = getattr(entity, 'entity_type', 'unknown')
    entity_name = getattr(entity, 'name', 'Sans nom')

    # CORRIGER: Gérer entity.color qui peut être string ou QColor
    entity_color = '#000000'
    if hasattr(entity, 'color'):
        if isinstance(entity.color, str):
            entity_color = entity.color
        elif isinstance(entity.color, QColor):
            entity_color = entity.color.name(QColor.HexArgb)

    data = {
        'entity_type': entity_type,
        'name': entity_name,
        'color': entity_color,
        'pixels_per_meter': getattr(entity, 'pixels_per_meter', 1.0),
    }

    if hasattr(entity, 'points') and entity.points:
        data['points'] = [(p.x(), p.y()) for p in entity.points]
        data['fill_pattern'] = getattr(entity, 'fill_pattern', Qt.SolidPattern)
        data['is_perimeter'] = getattr(entity, 'is_perimeter', False)
        data['width'] = getattr(entity, 'width', 2)
        data['openings'] = []
        data['linear_openings'] = []

        data['is_group_parent'] = getattr(entity, 'is_group_parent', False)
        data['group_id'] = getattr(entity, 'group_id', None)
        parent = getattr(entity, 'parent_entity', None)
        data['parent_entity_id'] = parent.entity_id if parent else None
        child_entities = getattr(entity, 'child_entities', [])
        data['child_entity_ids'] = [
            child.entity_id for child in child_entities] if child_entities else []

        if entity_type == 'polygon' and hasattr(entity, 'openings') and entity.openings:
            for opening in entity.openings:
                # CORRIGER: Gérer opening.color qui peut être string ou QColor
                opening_color = '#ff0000'
                if hasattr(opening, 'color'):
                    if isinstance(opening.color, str):
                        opening_color = opening.color
                    elif isinstance(opening.color, QColor):
                        opening_color = opening.color.name(QColor.HexArgb)
                
                data['openings'].append({
                    'points': [(p.x(), p.y()) for p in opening.points],
                    'name': opening.name,
                    'color': opening_color,
                    'pixels_per_meter': opening.pixels_per_meter
                })

        if entity_type == 'perimeter' and hasattr(entity, 'linear_openings') and entity.linear_openings:
            data['linear_openings'] = copy.deepcopy(entity.linear_openings)

    elif hasattr(entity, 'start_point') and hasattr(entity, 'end_point'):
        data['start_point'] = (
            entity.start_point.x(), entity.start_point.y())
        data['end_point'] = (entity.end_point.x(), entity.end_point.y())
        data['width'] = getattr(entity, 'width', 2)

        if entity_type == 'line':
            data['reference_distance'] = getattr(
                entity, 'reference_distance', 0)

    elif entity_type == 'counter':
        if hasattr(entity, 'counter_items'):
            data['counter_items'] = [(item.x(), item.y())
                                     for item in entity.counter_items]
        else:
            data['counter_items'] = []

    else:
        data['unsupported'] = True

    return data


class Command:
    """Classe de base pour une commande réversible"""

    def __init__(self, description=""):
        self.description = description

    def execute(self):
        """Exécute la commande"""
        pass

    def undo(self):
        """Annule la commande"""
        pass

    def redo(self):
        """Refait la commande (par défaut = execute)"""
        self.execute()


class AddEntityCommand(Command):
    """Commande pour ajouter une entité"""

    def __init__(self, entity_manager, scene, entity_data, description="Ajouter entité"):
        super().__init__(description)
        self.entity_manager = entity_manager
        self.scene = scene
        self.entity_data = entity_data  # Snapshot de l'entité
        self.entity_id = None
        self.entity = None

    def execute(self):
        """Recrée et ajoute l'entité"""
        self.entity = self._recreate_entity_from_data(self.entity_data)

        if self.entity:
            # Désactiver temporairement l'historique pour éviter la boucle
            undo_manager = None
            if hasattr(self.entity_manager, 'main_window') and hasattr(self.entity_manager.main_window, 'undo_redo_manager'):
                undo_manager = self.entity_manager.main_window.undo_redo_manager
                undo_manager.set_enabled(False)

            # Ajouter l'entité
            self.entity_id = self.entity_manager.add_entity(self.entity)
            self.entity.entity_id = self.entity_id

            # Réactiver l'historique
            if undo_manager:
                undo_manager.set_enabled(True)

            # Dessiner sur la scène
            if self.scene:
                self.entity.draw(self.scene)
                # Restaurer les métadonnées et connexions après draw()
                self._restore_entity_connections(self.entity)
                # ✅ NOUVEAU : Restaurer les liens de groupe
                self._restore_group_connections(self.entity)

    def _restore_entity_connections(self, entity):
        """Restaure les métadonnées, événements et connexions après recréation"""
        # 1. Restaurer les métadonnées Qt sur l'item graphique
        if hasattr(entity, 'surface_item') and entity.surface_item:
            entity.surface_item.setData(0, "polygon_entity")
            entity.surface_item.setData(1, entity.entity_id)

        if hasattr(entity, 'path_item') and entity.path_item:
            entity.path_item.setData(0, "perimeter_entity")
            entity.path_item.setData(1, entity.entity_id)

        if hasattr(entity, 'line_item') and entity.line_item:
            entity.line_item.setData(0, "line_entity")
            entity.line_item.setData(1, entity.entity_id)

        # 2. Restaurer les événements de souris (pour le déplacement)
        if hasattr(entity, 'surface_item') and entity.surface_item:
            if hasattr(entity, 'mousePressEvent'):
                entity.surface_item.mousePressEvent = entity.mousePressEvent
            if hasattr(entity, 'mouseDoubleClickEvent'):
                entity.surface_item.mouseDoubleClickEvent = entity.mouseDoubleClickEvent

        # 3. Reconnecter le signal geometryChanged (si la main_window existe)
        if hasattr(self.entity_manager, 'main_window'):
            main_window = self.entity_manager.main_window
            if hasattr(main_window, 'connect_entity_signals'):
                try:
                    main_window.connect_entity_signals(entity)
                except Exception as e:
                    pass

        # 4. Pour les ouvertures, les rattacher à leur surface parent
        if hasattr(entity, 'entity_type') and entity.entity_type == 'opening':
            # Trouver la surface qui contient cette ouverture (par position)
            parent_surface = self._find_parent_surface_for_opening(entity)

            if parent_surface:
                # Établir la relation bidirectionnelle
                entity.parent_surface = parent_surface

                # Attacher l'ouverture à la surface
                if not hasattr(parent_surface, 'openings'):
                    parent_surface.openings = []

                # Vérifier si l'ouverture n'est pas déjà dans la liste
                if entity not in parent_surface.openings:
                    parent_surface.openings.append(entity)

                # Attacher graphiquement (setParentItem)
                if hasattr(entity, 'polygon_item') and entity.polygon_item:
                    if hasattr(parent_surface, 'surface_item') and parent_surface.surface_item:
                        entity.polygon_item.setParentItem(
                            parent_surface.surface_item)

                # Mettre à jour le visuel de la surface pour évider l'ouverture
                parent_surface.update_visual_with_openings()

                # Émettre le signal de changement
                if hasattr(parent_surface, 'geometryChanged'):
                    parent_surface.geometryChanged.emit()
            else:
                pass

        # 5. Pour les surfaces : restaurer les ouvertures comme enfants graphiques
        if hasattr(entity, 'entity_type') and entity.entity_type == 'polygon':
            if hasattr(entity, 'openings') and entity.openings and self.scene:

                # Dessiner chaque ouverture sur la scène AVANT de les attacher
                for idx, opening in enumerate(entity.openings):

                    # Dessiner l'ouverture pour créer son polygon_item
                    if not hasattr(opening, 'polygon_item') or not opening.polygon_item:
                        opening.draw(self.scene)
                    else:
                        pass

                    # Attacher l'ouverture à la surface comme enfant graphique
                    if hasattr(opening, 'polygon_item') and opening.polygon_item:
                        if hasattr(entity, 'surface_item') and entity.surface_item:
                            opening.polygon_item.setParentItem(
                                entity.surface_item)
                        else:
                            pass
                    else:
                        pass

                # Redessiner la surface avec les ouvertures évidées
                entity.update_visual_with_openings()

                # Émettre le signal de changement
                if hasattr(entity, 'geometryChanged'):
                    entity.geometryChanged.emit()
            elif hasattr(entity, 'openings') and entity.openings:
                pass

    def _restore_group_connections(self, entity):
        """Restaure les liens parent-enfant du groupe après recréation

        Utilise group_id au lieu d'entity_id car les entity_id changent lors du REDO.
        """
        if not self.entity_manager:
            return

        # Nettoyer les anciens attributs temporaires (obsolètes maintenant)
        if hasattr(entity, '_pending_parent_id'):
            delattr(entity, '_pending_parent_id')
        if hasattr(entity, '_pending_child_ids'):
            delattr(entity, '_pending_child_ids')

        # Si l'entité n'a pas de group_id, elle n'est pas dans un groupe
        if not hasattr(entity, 'group_id') or not entity.group_id:
            return

        # Préparer le cache des liens en attente sur l'entity_manager
        pending_links = getattr(self.entity_manager,
                                '_pending_group_links', None)
        if pending_links is None:
            pending_links = {}
            self.entity_manager._pending_group_links = pending_links


        # CAS 1 : C'est un enfant → chercher son parent par group_id
        if not getattr(entity, 'is_group_parent', False):
            parent = None
            for ent in self.entity_manager.entities.values():
                if (hasattr(ent, 'group_id') and ent.group_id == entity.group_id
                        and getattr(ent, 'is_group_parent', False)):
                    parent = ent
                    break

            if parent:
                entity.parent_entity = parent
                if not hasattr(parent, 'child_entities'):
                    parent.child_entities = []
                if entity not in parent.child_entities:
                    parent.child_entities.append(entity)
            else:
                # Parent pas encore recréé → stocker l'enfant en attente
                waiting_children = pending_links.setdefault(
                    entity.group_id, [])
                if entity not in waiting_children:
                    waiting_children.append(entity)

        # CAS 2 : C'est un parent → chercher ses enfants par group_id
        elif getattr(entity, 'is_group_parent', False):
            if not hasattr(entity, 'child_entities'):
                entity.child_entities = []

            def _attach_child(child_entity):
                if child_entity not in entity.child_entities:
                    entity.child_entities.append(child_entity)
                child_entity.parent_entity = entity

            # Enfants déjà présents dans l'entity_manager
            for ent in self.entity_manager.entities.values():
                if (hasattr(ent, 'group_id') and ent.group_id == entity.group_id
                    and not getattr(ent, 'is_group_parent', False)
                        and ent != entity):
                    _attach_child(ent)

            # Enfants recréés avant le parent (en attente)
            waiting_children = pending_links.pop(entity.group_id, [])
            if waiting_children:
                for child in waiting_children:
                    _attach_child(child)

    def undo(self):
        """Supprime l'entité (inverse de l'ajout)"""
        if self.entity_id and self.entity_manager:
            # Désactiver l'historique
            undo_manager = None
            if hasattr(self.entity_manager, 'main_window') and hasattr(self.entity_manager.main_window, 'undo_redo_manager'):
                undo_manager = self.entity_manager.main_window.undo_redo_manager
                undo_manager.set_enabled(False)

            # Supprimer d'abord les ouvertures orphelines liées à cette surface.
            # Les ouvertures sont intégrées dans le snapshot de la surface (pas de
            # commande undo séparée), mais elles ont été ajoutées individuellement à
            # l'entity_manager lors du redo/draw. Sans ce nettoyage elles s'accumulent
            # comme fantômes et causent des artefacts visuels à chaque cycle undo/redo.
            entity = self.entity_manager.get_entity(self.entity_id)
            if entity and hasattr(entity, 'openings') and entity.openings:
                for opening in list(entity.openings):
                    oid = getattr(opening, 'entity_id', None)
                    if oid and self.entity_manager.get_entity(oid):
                        self.entity_manager.remove_entity(oid, self.scene)

            # Supprimer l'entité principale
            self.entity_manager.remove_entity(self.entity_id, self.scene)

            # Réactiver l'historique
            if undo_manager:
                undo_manager.set_enabled(True)

    def _recreate_entity_from_data(self, data):
        """Recrée une entité à partir de ses données"""
        from PyQt5.QtCore import QPointF
        from PyQt5.QtGui import QColor
        from PyQt5.QtCore import Qt

        entity_type = data.get('entity_type')

        # Ne pas recréer les types non supportés
        if data.get('unsupported'):
            return None

        # Polygones (surfaces)
        if entity_type == 'polygon' and 'points' in data:
            from entities.polygon_entity import PolygonEntity
            entity = PolygonEntity(
                points=[QPointF(p[0], p[1]) for p in data['points']],
                pixels_per_meter=data['pixels_per_meter']
            )
            entity.name = data['name']
            entity.color = QColor(data['color'])
            entity.fill_pattern = data.get('fill_pattern', Qt.SolidPattern)
            entity.is_perimeter = data.get('is_perimeter', False)

            # ✅ NOUVEAU : Restaurer les attributs de groupe
            entity.is_group_parent = data.get('is_group_parent', False)
            entity.group_id = data.get('group_id', None)
            entity.child_entities = []  # Sera rempli lors de la reconnexion
            entity._pending_parent_id = data.get(
                'parent_entity_id', None)  # Stocké temporairement
            entity._pending_child_ids = data.get(
                'child_entity_ids', [])  # Stocké temporairement

            # ✅ DEBUG : Afficher ce qui est restauré
            if entity.is_group_parent or entity._pending_parent_id or entity._pending_child_ids:
                pass

            # Restaurer la référence à la scène AVANT d'ajouter les ouvertures
            entity.scene_ref = self.scene

            # ✅ DEBUG: Vérifier si les ouvertures sont dans le snapshot
            if 'openings' in data:
                pass

            # Restaurer les ouvertures
            if 'openings' in data and data['openings']:
                from entities.opening_entity import OpeningEntity


                # ✅ Désactiver l'historique temporairement
                undo_manager = None
                if hasattr(self.entity_manager, 'main_window') and hasattr(self.entity_manager.main_window, 'undo_redo_manager'):
                    undo_manager = self.entity_manager.main_window.undo_redo_manager
                    undo_manager.set_enabled(False)

                for idx, opening_data in enumerate(data['openings']):
                    try:

                        opening = OpeningEntity(
                            points=[QPointF(p[0], p[1])
                                    for p in opening_data['points']],
                            pixels_per_meter=opening_data['pixels_per_meter']
                        )
                        opening.name = opening_data['name']
                        opening.color = QColor(opening_data['color'])
                        opening.scene_ref = self.scene

                        # Dessiner l'ouverture AVANT de l'ajouter
                        if self.scene:
                            opening.draw(self.scene)

                        # Ajouter l'ouverture à l'entity_manager
                        if self.entity_manager:
                            opening_id = self.entity_manager.add_entity(
                                opening)
                            opening.entity_id = opening_id

                            # Restaurer les métadonnées Qt
                            if hasattr(opening, 'polygon_item') and opening.polygon_item:
                                opening.polygon_item.setData(
                                    0, "opening_entity")
                                opening.polygon_item.setData(1, opening_id)

                        # ✅ NE PAS appeler entity.add_opening() ici !
                        # Stocker simplement l'ouverture dans la liste
                        # L'attachement graphique sera fait dans _restore_entity_connections()
                        entity.openings.append(opening)
                        opening.parent_surface = entity

                    except Exception as e:
                        import traceback
                        traceback.print_exc()

                # ✅ Réactiver l'historique
                if undo_manager:
                    undo_manager.set_enabled(True)


            return entity

        # Périmètres
        elif entity_type == 'perimeter' and 'points' in data:
            from entities.perimeter_entity import PerimeterEntity
            entity = PerimeterEntity(
                points=[QPointF(p[0], p[1]) for p in data['points']],
                color=QColor(data.get('color', '#0000ff')),
                width=data.get('width', 2),
                pixels_per_meter=data.get('pixels_per_meter', 1.0),
                name=data.get('name', 'Périmètre')
            )

            # Restaurer les ouvertures linéaires
            if 'linear_openings' in data and data['linear_openings']:
                entity.linear_openings = copy.deepcopy(data['linear_openings'])

            # Restaurer les attributs de groupe pour conserver le regroupement après Undo/Redo
            entity.is_group_parent = data.get('is_group_parent', False)
            entity.group_id = data.get('group_id', None)
            entity.child_entities = []
            entity._pending_parent_id = data.get('parent_entity_id', None)
            entity._pending_child_ids = data.get('child_entity_ids', [])

            return entity

        # Lignes (échelle de référence, distance)
        elif entity_type == 'line' and 'start_point' in data and 'end_point' in data:
            from entities.line_entity import LineEntity
            entity = LineEntity(
                start_point=QPointF(
                    data['start_point'][0], data['start_point'][1]),
                end_point=QPointF(data['end_point'][0], data['end_point'][1]),
                color=QColor(data['color']),
                width=data.get('width', 2),
                pixels_per_meter=data['pixels_per_meter']
            )
            entity.name = data['name']

            # Restaurer la distance de référence pour l'échelle
            if 'reference_distance' in data:
                entity.reference_distance = data['reference_distance']

            return entity

        # Distances
        elif entity_type == 'distance' and 'start_point' in data and 'end_point' in data:
            try:
                from entities.distance_entity import DistanceEntity  # type: ignore
            except Exception:
                DistanceEntity = None
            if DistanceEntity is None:
                return None
            entity = DistanceEntity(
                start_point=QPointF(
                    data['start_point'][0], data['start_point'][1]),
                end_point=QPointF(data['end_point'][0], data['end_point'][1]),
                color=QColor(data.get('color', '#000000')),
                pixels_per_meter=data.get('pixels_per_meter', 1.0)
            )
            entity.name = data.get('name', 'Distance')
            return entity

        # Compteurs
        elif entity_type == 'counter' and 'counter_items' in data:
            try:
                from entities.counter_entity import CounterEntity  # type: ignore
            except Exception:
                CounterEntity = None
            if CounterEntity is None:
                return None
            entity = CounterEntity(
                color=QColor(data.get('color', '#000000')),
                pixels_per_meter=data.get('pixels_per_meter', 1.0)
            )
            entity.name = data.get('name', 'Compteur')

            # Restaurer les points de comptage
            for point_data in data['counter_items']:
                entity.add_counter_item(QPointF(point_data[0], point_data[1]))

            return entity

        # Ouvertures (surfaces)
        elif entity_type == 'opening' and 'points' in data:
            from entities.opening_entity import OpeningEntity
            entity = OpeningEntity(
                points=[QPointF(p[0], p[1]) for p in data['points']],
                pixels_per_meter=data['pixels_per_meter']
            )
            entity.name = data['name']
            entity.color = QColor(data['color'])
            return entity

        return None

    def _find_parent_surface_for_opening(self, opening):
        """Trouve la surface parent d'une ouverture basée sur la position"""
        if not hasattr(opening, 'points') or not opening.points:
            return None

        # Calculer le centre de l'ouverture
        opening_center_x = sum(p.x()
                               for p in opening.points) / len(opening.points)
        opening_center_y = sum(p.y()
                               for p in opening.points) / len(opening.points)

        # Parcourir toutes les surfaces pour trouver celle qui contient l'ouverture
        if hasattr(self.entity_manager, 'entities'):
            for entity_id, potential_surface in self.entity_manager.entities.items():
                if not hasattr(potential_surface, 'entity_type'):
                    continue

                if potential_surface.entity_type != 'polygon':
                    continue

                # Vérifier si le centre de l'ouverture est dans cette surface
                if self._point_in_polygon(opening_center_x, opening_center_y, potential_surface):
                    return potential_surface

        return None

    def _point_in_polygon(self, x, y, polygon_entity):
        """Vérifie si un point (x, y) est à l'intérieur d'un polygone"""
        if not hasattr(polygon_entity, 'points') or not polygon_entity.points:
            return False

        points = polygon_entity.points
        n = len(points)
        inside = False

        j = n - 1
        for i in range(n):
            xi, yi = points[i].x(), points[i].y()
            xj, yj = points[j].x(), points[j].y()

            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside

            j = i

        return inside


class RemoveEntityCommand(Command):
    """Commande pour supprimer une entité"""

    def __init__(self, entity_manager, scene, entity, description="Supprimer entité"):
        super().__init__(description)
        self.entity_manager = entity_manager
        self.scene = scene
        self.entity_id = entity.entity_id
        self.entity_data = create_entity_snapshot(entity)

    def execute(self):
        """Supprime l'entité"""
        if self.entity_id and self.entity_manager:
            entity = self.entity_manager.get_entity(self.entity_id)
            if entity:
                # Désactiver temporairement l'historique
                undo_manager = None
                if hasattr(self.entity_manager, 'main_window') and hasattr(self.entity_manager.main_window, 'undo_redo_manager'):
                    undo_manager = self.entity_manager.main_window.undo_redo_manager
                    undo_manager.set_enabled(False)

                # Supprimer les ouvertures liées avant la surface parente
                if hasattr(entity, 'openings') and entity.openings:
                    for opening in list(entity.openings):
                        oid = getattr(opening, 'entity_id', None)
                        if oid and self.entity_manager.get_entity(oid):
                            self.entity_manager.remove_entity(oid, self.scene)

                self.entity_manager.remove_entity(self.entity_id, self.scene)

                # Réactiver l'historique
                if undo_manager:
                    undo_manager.set_enabled(True)

    def undo(self):
        """Recrée l'entité supprimée"""
        add_command = AddEntityCommand(
            self.entity_manager, self.scene, self.entity_data)
        add_command.execute()


class ModifyEntityCommand(Command):
    """Commande pour modifier une entité (ajouter ouverture, etc.)"""

    def __init__(self, entity_manager, scene, entity_id, modification_type, modification_data, description="Modifier entité"):
        super().__init__(description)
        self.entity_manager = entity_manager
        self.scene = scene
        self.entity_id = entity_id
        # 'add_opening', 'remove_opening', etc.
        self.modification_type = modification_type
        self.modification_data = modification_data
        self.old_state = None

    def execute(self):
        """Applique la modification"""
        entity = self.entity_manager.get_entity(self.entity_id)
        if not entity:
            return

        # Sauvegarder l'état ancien
        self.old_state = self._snapshot_openings(entity)

        # Appliquer la modification
        if self.modification_type == 'add_opening':
            from entities.opening_entity import OpeningEntity
            opening = self._recreate_opening(self.modification_data)
            entity.add_opening(opening)

        elif self.modification_type == 'remove_opening':
            opening_index = self.modification_data['index']
            if 0 <= opening_index < len(entity.openings):
                entity.openings.pop(opening_index)

        # Redessiner
        if self.scene:
            entity.draw(self.scene)

    def undo(self):
        """Annule la modification"""
        entity = self.entity_manager.get_entity(self.entity_id)
        if not entity or not self.old_state:
            return

        # Restaurer l'ancien état
        self._restore_openings(entity, self.old_state)

        # Redessiner
        if self.scene:
            entity.draw(self.scene)

    def _snapshot_openings(self, entity):
        """Sauvegarde les ouvertures"""
        from PyQt5.QtGui import QColor
        
        if not hasattr(entity, 'openings'):
            return []

        openings_list = []
        for opening in entity.openings:
            # CORRIGER: Gérer opening.color qui peut être string ou QColor
            opening_color = '#ff0000'
            if hasattr(opening, 'color'):
                if isinstance(opening.color, str):
                    opening_color = opening.color
                elif isinstance(opening.color, QColor):
                    opening_color = opening.color.name(QColor.HexArgb)
            
            openings_list.append({
                'points': [(p.x(), p.y()) for p in opening.points],
                'name': opening.name,
                'color': opening_color,
                'pixels_per_meter': opening.pixels_per_meter
            })
        
        return openings_list

    def _restore_openings(self, entity, openings_data):
        """Restaure les ouvertures"""
        entity.openings.clear()
        for opening_data in openings_data:
            opening = self._recreate_opening(opening_data)
            entity.openings.append(opening)

    def _recreate_opening(self, data):
        """Recrée une ouverture"""
        from PyQt5.QtCore import QPointF
        from PyQt5.QtGui import QColor
        from entities.opening_entity import OpeningEntity

        opening = OpeningEntity(
            points=[QPointF(p[0], p[1]) for p in data['points']],
            pixels_per_meter=data['pixels_per_meter']
        )
        opening.name = data['name']
        opening.color = QColor(data['color'])
        return opening


class UndoRedoManager(QObject):
    """Gestionnaire de l'historique Undo/Redo"""

    # Signaux pour notifier des changements d'état
    canUndoChanged = pyqtSignal(bool)
    canRedoChanged = pyqtSignal(bool)
    historyChanged = pyqtSignal()

    def __init__(self, max_history=50):
        super().__init__()
        self.max_history = max_history
        self.undo_stack = []
        self.redo_stack = []
        self._enabled = True

    def snapshot_entity_geometry(self, entity):
        """Expose la création de snapshot pour d'autres composants"""
        try:
            return create_entity_snapshot(entity)
        except Exception as e:
            return None

    def execute_command(self, command):
        """Exécute une commande et l'ajoute à l'historique"""
        if not self._enabled:
            return

        command.execute()
        self.undo_stack.append(command)

        # Limiter la taille de l'historique
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

        # Vider la pile redo (nouvelle action = on ne peut plus redo)
        self.redo_stack.clear()

        self._emit_state_changed()

    def push_command(self, command):
        """Ajoute une commande déjà exécutée à l'historique"""
        if not self._enabled:
            return

        self.undo_stack.append(command)

        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

        self.redo_stack.clear()
        self._emit_state_changed()

    def undo(self):
        """Annule la dernière commande"""
        if not self.can_undo():
            return False

        command = self.undo_stack.pop()

        try:
            command.undo()
            self.redo_stack.append(command)
        except Exception as e:
            import traceback
            traceback.print_exc()
            # Remettre la commande dans la pile en cas d'erreur
            self.undo_stack.append(command)
            return False

        self._emit_state_changed()
        return True

    def redo(self):
        """Refait la dernière commande annulée"""
        if not self.can_redo():
            return False

        command = self.redo_stack.pop()

        try:
            command.redo()
            self.undo_stack.append(command)
        except Exception as e:
            import traceback
            traceback.print_exc()
            # Remettre la commande dans la pile en cas d'erreur
            self.redo_stack.append(command)
            return False

        self._emit_state_changed()
        return True

    def can_undo(self):
        """Vérifie si on peut annuler"""
        return len(self.undo_stack) > 0

    def can_redo(self):
        """Vérifie si on peut refaire"""
        return len(self.redo_stack) > 0

    def clear(self):
        """Vide l'historique"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._emit_state_changed()

    def set_enabled(self, enabled):
        """Active/désactive l'enregistrement de l'historique"""
        self._enabled = enabled

    def _emit_state_changed(self):
        """Émet les signaux de changement d'état"""
        self.canUndoChanged.emit(self.can_undo())
        self.canRedoChanged.emit(self.can_redo())
        self.historyChanged.emit()

    def get_undo_text(self):
        """Retourne le texte de la prochaine action à annuler"""
        if self.can_undo():
            return f"Annuler {self.undo_stack[-1].description}"
        return "Annuler"

    def get_redo_text(self):
        """Retourne le texte de la prochaine action à refaire"""
        if self.can_redo():
            return f"Refaire {self.redo_stack[-1].description}"
        return "Refaire"


class PropertyChangeCommand(Command):
    """Commande générique pour enregistrer tout changement de propriété d'une entité"""

    def __init__(self, entity_manager, scene, entity_id, property_name, old_value, new_value, description="Modifier propriété"):
        super().__init__(description)
        self.entity_manager = entity_manager
        self.scene = scene
        self.entity_id = entity_id
        self.property_name = property_name
        self.old_value = old_value
        self.new_value = new_value

    def execute(self):
        """Applique le changement (pour Redo)"""
        entity = self.entity_manager.get_entity(self.entity_id)
        if not entity:
            return

        self._apply_property_change(entity, self.new_value)

    def undo(self):
        """Annule le changement"""
        entity = self.entity_manager.get_entity(self.entity_id)
        if not entity:
            return

        self._apply_property_change(entity, self.old_value)

    def _apply_property_change(self, entity, value):
        """Applique un changement de propriété"""
        from PyQt5.QtGui import QColor
        from PyQt5.QtCore import QPointF

        # Désactiver temporairement l'historique pour éviter les boucles
        undo_manager = None
        if hasattr(self.entity_manager, 'main_window') and hasattr(self.entity_manager.main_window, 'undo_redo_manager'):
            undo_manager = self.entity_manager.main_window.undo_redo_manager
            undo_manager.set_enabled(False)

        try:
            # Changement de couleur
            if self.property_name == 'color':
                if hasattr(entity, 'set_color'):
                    entity.set_color(QColor(value))
                else:
                    entity.color = QColor(value)

                # Redessiner
                if hasattr(entity, 'draw') and hasattr(entity, 'scene_ref'):
                    entity.draw(entity.scene_ref)

                # Mettre à jour légende et relevé
                if hasattr(self.entity_manager, 'main_window'):
                    main_window = self.entity_manager.main_window
                    if hasattr(main_window.canvas_view, 'update_legend'):
                        main_window.canvas_view.update_legend()
                    if hasattr(main_window, 'update_quantities_table'):
                        main_window.update_quantities_table()

            # Changement de nom
            elif self.property_name == 'name':
                entity.name = value

                # Mettre à jour légende et relevé
                if hasattr(self.entity_manager, 'main_window'):
                    main_window = self.entity_manager.main_window
                    if hasattr(main_window.canvas_view, 'update_legend'):
                        main_window.canvas_view.update_legend()
                    if hasattr(main_window, 'update_quantities_table'):
                        main_window.update_quantities_table()
                    if hasattr(main_window, 'update_properties_entities_list'):
                        main_window.update_properties_entities_list()

            # Changement de position (déplacement)
            elif self.property_name == 'position':
                if hasattr(entity, 'points'):
                    # Pour polygones/périmètres : déplacer tous les points
                    entity.points = [QPointF(p[0], p[1]) for p in value]
                elif hasattr(entity, 'start_point') and hasattr(entity, 'end_point'):
                    # Pour lignes
                    entity.start_point = QPointF(
                        value['start'][0], value['start'][1])
                    entity.end_point = QPointF(
                        value['end'][0], value['end'][1])

                # Redessiner
                if hasattr(entity, 'draw') and self.scene:
                    entity.draw(self.scene)

                # Mettre à jour les calculs
                if hasattr(entity, 'calculate_area'):
                    entity.calculate_area()
                if hasattr(entity, 'geometryChanged'):
                    entity.geometryChanged.emit()

        finally:
            # Réactiver l'historique
            if undo_manager:
                undo_manager.set_enabled(True)
