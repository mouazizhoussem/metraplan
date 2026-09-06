from PyQt5.QtCore import QPointF


def _shoelace_area(points):
    """Calcule l'aire signée (px²) via la formule de Shoelace."""
    if not points or len(points) < 3:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        area += points[i].x() * points[j].y()
        area -= points[j].x() * points[i].y()
    return abs(area) / 2.0


def polygon_area(points, pixels_per_meter):
    """Aire en m² d'un polygone défini par des QPointF."""
    ppm = pixels_per_meter or 1.0
    if ppm <= 0:
        ppm = 1.0
    area_px2 = _shoelace_area(points)
    return area_px2 / (ppm ** 2)


def net_area_with_openings(entity):
    """Surface nette d'une surface (aire - ouvertures)."""
    total = polygon_area(getattr(entity, "points", []),
                         getattr(entity, "pixels_per_meter", 1.0))
    openings = getattr(entity, "openings", []) or []
    openings_area = sum(
        polygon_area(getattr(op, "points", []),
                     getattr(op, "pixels_per_meter", getattr(entity, "pixels_per_meter", 1.0)))
        for op in openings
    )
    return max(0.0, total - openings_area)


def total_area_with_children(entity):
    """Aire totale brute de l'entité et de ses enfants éventuels."""
    total = polygon_area(getattr(entity, "points", []),
                         getattr(entity, "pixels_per_meter", 1.0))
    for child in getattr(entity, "child_entities", []) or []:
        if hasattr(child, "calculate_total_area"):
            total += child.calculate_total_area()
        else:
            total += polygon_area(getattr(child, "points", []),
                                  getattr(child, "pixels_per_meter", getattr(entity, "pixels_per_meter", 1.0)))
    return total


def total_group_area(entity):
    """Aire nette du parent + aires nettes des enfants (groupes)."""
    parent = net_area_with_openings(entity)
    children_total = 0.0
    for child in getattr(entity, "child_entities", []) or []:
        if hasattr(child, "calculate_net_area"):
            children_total += child.calculate_net_area()
        else:
            children_total += net_area_with_openings(child)
    return parent + children_total

