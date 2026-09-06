import copy
from PyQt5.QtCore import Qt


def create_entity_snapshot(entity):
    """Crée un snapshot complet de l'entité passée en paramètre"""
    entity_type = getattr(entity, 'entity_type', 'unknown')
    entity_name = getattr(entity, 'name', 'Sans nom')

    data = {
        'entity_type': entity_type,
        'name': entity_name,
        'color': entity.color.name() if hasattr(entity, 'color') else '#000000',
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
                data['openings'].append({
                    'points': [(p.x(), p.y()) for p in opening.points],
                    'name': opening.name,
                    'color': opening.color.name(),
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

    elif entity_type == 'perimeter':
        # Capture les points si présents
        if hasattr(entity, 'points') and entity.points:
            data['points'] = [(p.x(), p.y()) for p in entity.points]

        # Attributs de groupe pour permettre le regroupement après Undo/Redo
        data['is_group_parent'] = getattr(entity, 'is_group_parent', False)
        data['group_id'] = getattr(entity, 'group_id', None)
        parent = getattr(entity, 'parent_entity', None)
        data['parent_entity_id'] = parent.entity_id if parent else None
        child_entities = getattr(entity, 'child_entities', [])
        data['child_entity_ids'] = [
            child.entity_id for child in child_entities] if child_entities else []

    else:
        data['unsupported'] = True

    return data


def restore_entity_connections(command, entity):
    """Restaure les métadonnées, événements et connexions après recréation"""
    entity_manager = command.entity_manager
    scene = command.scene

    if hasattr(entity, 'surface_item') and entity.surface_item:
        entity.surface_item.setData(0, "polygon_entity")
        entity.surface_item.setData(1, entity.entity_id)

    if hasattr(entity, 'path_item') and entity.path_item:
        entity.path_item.setData(0, "perimeter_entity")
        entity.path_item.setData(1, entity.entity_id)

    if hasattr(entity, 'line_item') and entity.line_item:
        entity.line_item.setData(0, "line_entity")
        entity.line_item.setData(1, entity.entity_id)

    if hasattr(entity, 'counter_items') and entity.counter_items:
        for item in entity.counter_items:
            item.setData(0, "counter_item")
            item.setData(1, entity.entity_id)
            if scene:
                scene.addItem(item)

    if hasattr(entity, 'surface_item') and entity.surface_item:
        entity.surface_item.setFlag(entity.surface_item.ItemIsMovable, True)
        entity.surface_item.setFlag(entity.surface_item.ItemIsSelectable, True)

    if hasattr(entity, 'path_item') and entity.path_item:
        entity.path_item.setFlag(entity.path_item.ItemIsMovable, True)
        entity.path_item.setFlag(entity.path_item.ItemIsSelectable, True)

    if hasattr(entity, 'line_item') and entity.line_item:
        entity.line_item.setFlag(entity.line_item.ItemIsMovable, True)
        entity.line_item.setFlag(entity.line_item.ItemIsSelectable, True)

    if hasattr(entity_manager, 'main_window'):
        main_window = entity_manager.main_window
        if hasattr(main_window, 'connect_entity_signals'):
            try:
                main_window.connect_entity_signals(entity)
            except Exception as e:
                pass

    if hasattr(entity, 'recalculate') and callable(getattr(entity, 'recalculate')):
        try:
            entity.recalculate()
        except Exception as e:
            pass

    if hasattr(entity, 'update_visual_with_openings'):
        try:
            entity.update_visual_with_openings()
        except Exception as e:
            pass


def recreate_entity_from_data(command, data):
    """Recrée une entité à partir d'un snapshot (utilise les factories existantes)."""
    # Import tardif pour éviter les cycles
    from entities.polygon_entity import PolygonEntity
    from entities.perimeter_entity import PerimeterEntity
    from entities.opening_entity import OpeningEntity
    from entities.line_entity import LineEntity
    # CounterEntity peut ne pas être présent selon la version du projet
    try:
        from entities.counter_entity import CounterEntity  # type: ignore
    except Exception:
        CounterEntity = None
    from PyQt5.QtCore import QPointF, Qt

    entity_type = data.get('entity_type', 'unknown')

    if entity_type == 'polygon':
        points = [QPointF(x, y) for x, y in data.get('points', [])]
        entity = PolygonEntity(points, data.get('pixels_per_meter', 1.0))
        entity.set_name(data.get('name', 'Sans nom'))
        if 'color' in data:
            from PyQt5.QtGui import QColor
            entity.set_color(QColor(data['color']))
        entity.fill_pattern = data.get('fill_pattern', Qt.SolidPattern)
        entity.is_perimeter = data.get('is_perimeter', False)
        entity.width = data.get('width', 2)
        entity.scene_ref = command.scene

        entity.is_group_parent = data.get('is_group_parent', False)
        entity.group_id = data.get('group_id', None)
        entity.child_entities = []
        entity._pending_parent_id = data.get('parent_entity_id', None)
        entity._pending_child_ids = data.get('child_entity_ids', [])

        for opening_data in data.get('openings', []):
            opening = OpeningEntity(
                [QPointF(x, y) for x, y in opening_data.get('points', [])],
                opening_data.get('pixels_per_meter', 1.0)
            )
            opening.name = opening_data.get('name', 'Ouverture')
            from PyQt5.QtGui import QColor
            opening.color = QColor(opening_data.get('color', '#000000'))
            opening.parent_surface = entity
            if command.scene:
                opening.draw(command.scene)
            if command.entity_manager:
                command.entity_manager.add_entity(opening)
            opening.parent_surface = entity
            if not hasattr(entity, 'openings'):
                entity.openings = []
            entity.openings.append(opening)

        if data.get('linear_openings'):
            entity.linear_openings = copy.deepcopy(data['linear_openings'])

        entity.draw(command.scene)
        return entity

    if entity_type == 'perimeter':
        points = [QPointF(x, y) for x, y in data.get('points', [])]
        entity = PerimeterEntity(
            points,
            color=data.get('color', '#0000ff'),
            width=data.get('width', 2),
            pixels_per_meter=data.get('pixels_per_meter', 1.0),
            name=data.get('name', 'Périmètre'))
        entity.scene_ref = command.scene
        entity.linear_openings = copy.deepcopy(data.get('linear_openings', []))

        # Restaurer les attributs de groupe (permet le regroupement après Undo/Redo)
        entity.is_group_parent = data.get('is_group_parent', False)
        entity.group_id = data.get('group_id', None)
        entity.child_entities = []
        entity._pending_parent_id = data.get('parent_entity_id', None)
        entity._pending_child_ids = data.get('child_entity_ids', [])

        entity.draw(command.scene)
        return entity

    if entity_type == 'opening':
        points = [QPointF(x, y) for x, y in data.get('points', [])]
        opening = OpeningEntity(
            points,
            data.get('pixels_per_meter', 1.0)
        )
        opening.name = data.get('name', 'Ouverture')
        from PyQt5.QtGui import QColor
        opening.color = QColor(data.get('color', '#000000'))
        return opening

    if entity_type == 'line':
        start = data.get('start_point')
        end = data.get('end_point')
        if start and end:
            entity = LineEntity(
                start_point=QPointF(start[0], start[1]),
                end_point=QPointF(end[0], end[1]),
                color=data.get('color', '#000000'),
                width=data.get('width', 2),
                pixels_per_meter=data.get('pixels_per_meter', 1.0),
                name=data.get('name', 'Ligne')
            )
            entity.reference_distance = data.get('reference_distance', 0)
            return entity

    if entity_type == 'counter':
        if CounterEntity is None:
            return None
        entity = CounterEntity()
        items = []
        for x, y in data.get('counter_items', []):
            pt = QPointF(x, y)
            items.append(pt)
        entity.counter_items = items
        entity.draw(command.scene)
        return entity

    return None


def restore_group_connections(command, entity):
    """Restaure les liens parent-enfant du groupe après recréation"""
    entity_manager = command.entity_manager
    if not entity_manager:
        return

    if hasattr(entity, '_pending_parent_id'):
        delattr(entity, '_pending_parent_id')
    if hasattr(entity, '_pending_child_ids'):
        delattr(entity, '_pending_child_ids')

    if not hasattr(entity, 'group_id') or not entity.group_id:
        return

    pending_links = getattr(entity_manager, '_pending_group_links', None)
    if pending_links is None:
        pending_links = {}
        entity_manager._pending_group_links = pending_links

    # Enfant
    if not getattr(entity, 'is_group_parent', False):
        parent = None
        for ent in entity_manager.entities.values():
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
            waiting_children = pending_links.setdefault(entity.group_id, [])
            if entity not in waiting_children:
                waiting_children.append(entity)
        return

    # Parent
    if getattr(entity, 'is_group_parent', False):
        if not hasattr(entity, 'child_entities'):
            entity.child_entities = []

        def _attach_child(child_entity):
            if child_entity not in entity.child_entities:
                entity.child_entities.append(child_entity)
            child_entity.parent_entity = entity

        for ent in entity_manager.entities.values():
            if (hasattr(ent, 'group_id') and ent.group_id == entity.group_id
                    and not getattr(ent, 'is_group_parent', False)
                    and ent != entity):
                _attach_child(ent)

        waiting_children = pending_links.pop(entity.group_id, [])
        for child in waiting_children:
            _attach_child(child)
