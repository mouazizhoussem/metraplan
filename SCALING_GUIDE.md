# Guide d'Intégration du Système d'Échelle Automatique

Ce guide explique comment utiliser le `ScaleManager` pour adapter automatiquement les éléments graphiques à la taille du plan chargé.

## 🎯 Principe de Fonctionnement

Le `ScaleManager` calcule automatiquement un ratio d'échelle basé sur la taille de l'image chargée par rapport à une taille de référence (2000×1500 pixels par défaut).

- **Petit plan** (800×600) → échelle ≈ 0.5 → éléments 2× plus petits
- **Plan moyen** (2000×1500) → échelle = 1.0 → taille normale
- **Grand plan** (4000×3000) → échelle ≈ 2.0 → éléments 2× plus grands

## 📦 Composants

### 1. `core/scale_manager.py`
Gestionnaire central avec toutes les méthodes de scaling.

### 2. Méthodes helper dans `BaseEntity`
Toutes les entités héritent de ces méthodes :
- `get_scaled_font_size(base_size)` - Scale les tailles de police
- `get_scaled_pen_width(base_width)` - Scale les épaisseurs de ligne
- `get_scaled_size(base_size)` - Scale les dimensions génériques
- `get_scaled_padding(base_padding)` - Scale les paddings
- `get_scaled_offset(base_offset)` - Scale les offsets

## 🔧 Comment Modifier une Entité Existante

### Exemple : Adapter les bulles de texte d'un périmètre

**AVANT** (taille fixe) :
```python
def draw_text(self, scene):
    for i in range(len(self.points) - 1):
        # ...
        text_item = QGraphicsTextItem(text)
        text_item.setDefaultTextColor(QColor(0, 0, 0))
        
        # Créer l'arrière-plan
        text_rect = text_item.boundingRect()
        margin = 2  # ❌ Taille fixe
        text_bg = scene.addRect(
            text_rect.adjusted(-margin, -margin, margin, margin),
            QPen(Qt.black),
            QBrush(QColor(255, 255, 255, 200))
        )
        
        # Décalage fixe
        offset = 15  # ❌ Taille fixe
```

**APRÈS** (échelle automatique) :
```python
def draw_text(self, scene):
    for i in range(len(self.points) - 1):
        # ...
        text_item = QGraphicsTextItem(text)
        text_item.setDefaultTextColor(QColor(0, 0, 0))
        
        # ✅ Utiliser l'échelle automatique pour la police
        if self.scale_manager:
            base_font = QFont("Arial", 10)
            scaled_font = self.scale_manager.scale_font(base_font)
            text_item.setFont(scaled_font)
        
        # Créer l'arrière-plan avec padding scalé
        text_rect = text_item.boundingRect()
        margin = self.get_scaled_padding(2)  # ✅ Scalé automatiquement
        text_bg = scene.addRect(
            text_rect.adjusted(-margin, -margin, margin, margin),
            QPen(Qt.black),
            QBrush(QColor(255, 255, 255, 200))
        )
        
        # Décalage scalé
        offset = self.get_scaled_offset(15)  # ✅ Scalé automatiquement
```

### Exemple : Adapter les épaisseurs de ligne

**AVANT** :
```python
self.path_item.setPen(QPen(self.color, 2))  # ❌ Épaisseur fixe
```

**APRÈS** :
```python
base_width = 2
scaled_width = self.get_scaled_pen_width(base_width)  # ✅ Scalé
self.path_item.setPen(QPen(self.color, scaled_width))
```

### Exemple : Adapter les tailles d'ancres (handles)

**AVANT** :
```python
self.anchor_size = 16  # ❌ Taille fixe
anchor = QGraphicsRectItem(-self.anchor_size/2, -self.anchor_size/2,
                           self.anchor_size, self.anchor_size)
```

**APRÈS** :
```python
base_size = 16
scaled_size = self.get_scaled_size(base_size)  # ✅ Scalé
anchor = QGraphicsRectItem(-scaled_size/2, -scaled_size/2,
                           scaled_size, scaled_size)
```

## 📋 Checklist d'Intégration

Pour chaque entité à adapter :

- [ ] **Polices** : Utiliser `get_scaled_font_size()` ou `get_scaled_font()`
- [ ] **Épaisseurs de ligne** : Utiliser `get_scaled_pen_width()`
- [ ] **Marges/Paddings** : Utiliser `get_scaled_padding()`
- [ ] **Offsets de position** : Utiliser `get_scaled_offset()`
- [ ] **Icônes/Symboles** : Utiliser `get_scaled_size()`
- [ ] **Ancres/Handles** : Utiliser `get_scaled_size()`

## 🎨 Entités à Adapter

### Priorité Haute
- ✅ `PerimeterEntity` - bulles de mesure, épaisseur ligne
- ✅ `PolygonEntity` - texte central, épaisseur contour
- ✅ `LineEntity` - bulle de distance, épaisseur
- ✅ `OpeningEntity` - bulles, handles
- ✅ `PointEntity` - taille du point, police du compteur

### Éléments UI
- [ ] `LegendWidget` - taille de la légende
- [ ] Bulles de mesure temporaires (pendant le dessin)
- [ ] Icônes d'outils

## 🔧 Ajustement Manuel

Si l'échelle automatique ne convient pas parfaitement, vous pouvez ajuster les facteurs de correction :

```python
# Dans main_window.py ou canvas_view.py
scale_manager = self.canvas_view.scale_manager

# Augmenter les polices de 20%
scale_manager.adjust_font_scale_factor(1.2)

# Réduire les lignes de 10%
scale_manager.adjust_pen_scale_factor(0.9)

# Augmenter les bulles de 15%
scale_manager.adjust_bubble_scale_factor(1.15)
```

## 🐛 Débogage

Pour voir les informations d'échelle actuelles :

```python
info = self.canvas_view.scale_manager.get_scale_info()
print(f"Échelle actuelle : {info['scale_factor']:.2f}")
print(f"Image : {info['current_width']}×{info['current_height']}")
print(f"Référence : {info['reference_width']}×{info['reference_height']}")
```

## 📊 Limites

- **Échelle minimale** : 0.3 (évite des éléments invisibles)
- **Échelle maximale** : 3.0 (évite des éléments démesurés)
- **Taille de police minimale** : 6pt (pour la lisibilité)
- **Épaisseur de ligne minimale** : 1px (pour la visibilité)

## 🚀 Activation

Le système s'active automatiquement lors du chargement d'une image :

```python
# Lors du load_image dans canvas_view.py
self.scale_manager.set_scale_from_image(image_width, image_height)
# → Toutes les entités sont automatiquement redessinées avec la nouvelle échelle
```

## 📝 Notes Importantes

1. **Compatibilité** : Le système est rétro-compatible. Si `scale_manager` n'est pas disponible, les tailles de base sont utilisées.

2. **Performance** : Le scaling est calculé une seule fois au chargement, pas à chaque frame.

3. **Cohérence** : Tous les éléments utilisent le même ratio, garantissant une apparence homogène.

4. **Personnalisation** : Vous pouvez définir des dimensions de référence personnalisées selon vos besoins.

---

**Créé le :** 2025-01-02  
**Version :** 1.0

