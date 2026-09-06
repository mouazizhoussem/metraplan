from PyQt5.QtCore import QPointF


def get_ortho_point(last_point, current_pos):
    """Retourne le point orthogonal le plus proche (horizontal ou vertical) par rapport à last_point."""
    if last_point is None or current_pos is None:
        return current_pos

    dx = abs(current_pos.x() - last_point.x())
    dy = abs(current_pos.y() - last_point.y())
    if dx > dy:
        return QPointF(current_pos.x(), last_point.y())
    return QPointF(last_point.x(), current_pos.y())


def is_too_close(last_point, new_point, min_distance):
    """Vérifie si new_point est trop proche de last_point."""
    if last_point is None or new_point is None:
        return False
    dx = new_point.x() - last_point.x()
    dy = new_point.y() - last_point.y()
    return (dx * dx + dy * dy) ** 0.5 < min_distance


def build_rectangle_points(start_point, current_point):
    """Construit les 4 coins d'un rectangle à partir de deux points diagonaux."""
    if start_point is None or current_point is None:
        return []
    p1 = QPointF(start_point.x(), start_point.y())
    p2 = QPointF(current_point.x(), start_point.y())
    p3 = QPointF(current_point.x(), current_point.y())
    p4 = QPointF(start_point.x(), current_point.y())
    return [p1, p2, p3, p4]

