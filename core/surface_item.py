from PyQt5.QtWidgets import QGraphicsPolygonItem, QGraphicsEllipseItem
from PyQt5.QtCore import Qt, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QColor, QBrush, QPolygonF


class SurfaceItem(QGraphicsPolygonItem):
    # NOUVEAU: Signal de sélection
    selected = pyqtSignal(object)

    def __init__(self, points, parent=None):
        super().__init__(QPolygonF(points), parent)
        self.points = points
        self.handles = []

        # NOUVEAU: Propriétés étendues
        self.nom = "Surface"
        self.couleur = QColor(0, 255, 0, 100)
        self.surface = 0.0
        self.perimetre = 0.0

        # Configuration visuelle
        self.setPen(QPen(QColor(0, 255, 0), 2))
        self.setBrush(QBrush(self.couleur))  # Utilise la couleur propriété
        self.setFlag(QGraphicsPolygonItem.ItemIsSelectable, True)

        # Calcul des propriétés géométriques
        self.calculer_proprietes_geometriques()

        # Création des handles simples
        self.create_simple_handles()

    def mousePressEvent(self, event):
        """NOUVEAU: Intercepte le clic pour émettre le signal de sélection"""
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.selected.emit(self)

    # NOUVEAU: Méthode pour calculer les propriétés géométriques
    def calculer_proprietes_geometriques(self):
        """Calcule la surface et le périmètre"""
        try:
            polygon = self.polygon()
            # Calcul simplifié - à adapter selon votre échelle
            self.perimetre = polygon.boundingRect().width() + polygon.boundingRect().height()
            self.surface = polygon.boundingRect().width() * polygon.boundingRect().height()
        except Exception as e:
            pass

    # NOUVEAU: Méthode pour récupérer les propriétés
    def get_properties(self):
        """Retourne toutes les propriétés sous forme de dictionnaire"""
        return {
            'nom': self.nom,
            'type': 'Surface',
            'couleur': self.couleur.name(),
            'surface': f"{self.surface:.2f} m²",
            'perimetre': f"{self.perimetre:.2f} m",
            'nombre_points': len(self.points),
            'nombre_handles': len(self.handles)
        }

    def create_simple_handles(self):
        """Crée des points d'édition simples"""
        try:
            # Supprimer les handles existants
            for handle in self.handles:
                if handle.scene():
                    handle.scene().removeItem(handle)
            self.handles = []

            # Créer des handles simples
            for i, point in enumerate(self.points):
                handle = QGraphicsEllipseItem(-4, -4, 8, 8, self)
                handle.setPos(point)
                handle.setBrush(QBrush(QColor(255, 0, 0)))
                handle.setPen(QPen(Qt.black, 1))
                handle.setZValue(1)
                self.handles.append(handle)

        except Exception as e:
            pass

    def update_polygon_with_points(self, points):
        """Mise à jour du polygone et des handles"""
        try:
            self.points = points
            self.setPolygon(QPolygonF(points))

            # NOUVEAU: Recalculer les propriétés
            self.calculer_proprietes_geometriques()

            # Mettre à jour la position des handles
            for i, point in enumerate(points):
                if i < len(self.handles):
                    self.handles[i].setPos(point)
                else:
                    handle = QGraphicsEllipseItem(-4, -4, 8, 8, self)
                    handle.setPos(point)
                    handle.setBrush(QBrush(QColor(255, 0, 0)))
                    handle.setPen(QPen(Qt.black, 1))
                    handle.setZValue(1)
                    self.handles.append(handle)

            # Supprimer les handles excédentaires
            while len(self.handles) > len(points):
                handle = self.handles.pop()
                if handle.scene():
                    handle.scene().removeItem(handle)

        except Exception as e:
            pass
