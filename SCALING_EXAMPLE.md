# Exemple Concret : Adapter PerimeterEntity au Système d'Échelle

Voici un exemple complet montrant comment modifier `PerimeterEntity` pour utiliser l'échelle automatique.

## 🎯 Modifications à Apporter

### 1. Méthode `draw_text()` - Bulles de mesure sur segments

**Localisation** : `entities/perimeter_entity.py`, ligne ~1000

**Changements** :

```python
# AVANT (lignes ~999-1024)
def draw_text(self, scene):
    # ...
    for i in range(len(self.points) - 1):
        # ...
        text_item = QGraphicsTextItem(text)
        text_item.setDefaultTextColor(QColor(0, 0, 0))
        
        text_rect = text_item.boundingRect()
        margin = 2  # ❌ Fixe
        text_bg = scene.addRect(
            text_rect.adjusted(-margin, -margin, margin, margin),
            QPen(Qt.black),
            QBrush(QColor(255, 255, 255, 200))
        )
        
        offset = 15  # ❌ Fixe
        # ...

# APRÈS (avec échelle automatique)
def draw_text(self, scene):
    # ...
    for i in range(len(self.points) - 1):
        # ...
        text_item = QGraphicsTextItem(text)
        text_item.setDefaultTextColor(QColor(0, 0, 0))
        
        # ✅ Appliquer un font scalé
        base_font = QFont("Arial", 10)
        if self.scale_manager:
            scaled_font = self.scale_manager.scale_font(base_font)
            text_item.setFont(scaled_font)
        
        text_rect = text_item.boundingRect()
        margin = self.get_scaled_padding(2)  # ✅ Scalé
        text_bg = scene.addRect(
            text_rect.adjusted(-margin, -margin, margin, margin),
            QPen(Qt.black),
            QBrush(QColor(255, 255, 255, 200))
        )
        
        offset = self.get_scaled_offset(15)  # ✅ Scalé
        # ...
```

### 2. Méthode `draw()` - Ligne principale du périmètre

**Localisation** : `entities/perimeter_entity.py`, ligne ~600

**Changements** :

```python
# AVANT
def draw(self, scene):
    # ...
    pen = QPen(self.color, self.width)  # ❌ Épaisseur fixe
    self.path_item.setPen(pen)
    # ...

# APRÈS
def draw(self, scene):
    # ...
    scaled_width = self.get_scaled_pen_width(self.width)  # ✅ Scalé
    pen = QPen(self.color, scaled_width)
    self.path_item.setPen(pen)
    # ...
```

### 3. Méthode `_make_segment_label()` - Bulles d'ouverture

**Localisation** : `entities/perimeter_entity.py`, ligne ~1841

**Changements** :

```python
# AVANT
def _make_segment_label(self, scene, p1, p2, text, z=1000, use_normal_offset=True, vertical_offset=0):
    txt = QGraphicsTextItem(text)
    txt.setDefaultTextColor(QColor(0, 0, 0))
    
    rect = txt.boundingRect()
    margin = 2  # ❌ Fixe
    w = rect.width() + margin * 2
    h = rect.height() + margin * 2
    
    bg = QGraphicsRectItem(0, 0, w, h)
    bg.setBrush(QBrush(QColor(255, 255, 255, 200)))
    bg.setPen(QPen(Qt.black))
    # ...
    
    if use_normal_offset and length:
        offset = 15  # ❌ Fixe
        # ...

# APRÈS
def _make_segment_label(self, scene, p1, p2, text, z=1000, use_normal_offset=True, vertical_offset=0):
    txt = QGraphicsTextItem(text)
    txt.setDefaultTextColor(QColor(0, 0, 0))
    
    # ✅ Font scalé
    base_font = QFont("Arial", 10)
    if self.scale_manager:
        txt.setFont(self.scale_manager.scale_font(base_font))
    
    rect = txt.boundingRect()
    margin = self.get_scaled_padding(2)  # ✅ Scalé
    w = rect.width() + margin * 2
    h = rect.height() + margin * 2
    
    bg = QGraphicsRectItem(0, 0, w, h)
    bg.setBrush(QBrush(QColor(255, 255, 255, 200)))
    bg.setPen(QPen(Qt.black))
    # ...
    
    if use_normal_offset and length:
        offset = self.get_scaled_offset(15)  # ✅ Scalé
        # ...
```

### 4. Classe `PerimeterAnchorPoint` - Points d'ancrage

**Localisation** : `entities/perimeter_entity.py`, ligne ~238

**Changements** :

```python
# AVANT
class PerimeterAnchorPoint(QGraphicsRectItem):
    def __init__(self, x, y, index, parent_entity):
        self.visible_size = 16  # ❌ Fixe
        self.click_size = 40    # ❌ Fixe
        
        super().__init__(-self.visible_size/2, -self.visible_size/2,
                         self.visible_size, self.visible_size)
        # ...

# APRÈS
class PerimeterAnchorPoint(QGraphicsRectItem):
    def __init__(self, x, y, index, parent_entity):
        # Base sizes
        base_visible_size = 16
        base_click_size = 40
        
        # ✅ Tailles scalées
        if hasattr(parent_entity, 'scale_manager') and parent_entity.scale_manager:
            self.visible_size = parent_entity.scale_manager.scale_size(base_visible_size)
            self.click_size = parent_entity.scale_manager.scale_size(base_click_size)
        else:
            self.visible_size = base_visible_size
            self.click_size = base_click_size
        
        super().__init__(-self.visible_size/2, -self.visible_size/2,
                         self.visible_size, self.visible_size)
        # ...
        
        # ✅ Pen scalé
        if hasattr(parent_entity, 'get_scaled_pen_width'):
            pen_width = parent_entity.get_scaled_pen_width(3)
        else:
            pen_width = 3
        self.setPen(QPen(QColor(255, 255, 255), pen_width))
```

### 5. Méthode `draw_opening_segments()` - Segments d'ouverture

**Localisation** : `entities/perimeter_entity.py`, ligne ~2060

**Changements** :

```python
# AVANT
def draw_opening_segments(self, scene):
    # ...
    for idx, opening in enumerate(self.linear_openings):
        # ...
        pen = QPen(QColor(200, 0, 0), 2, Qt.DashLine)  # ❌ Épaisseur fixe
        line.setPen(pen)
        # ...

# APRÈS
def draw_opening_segments(self, scene):
    # ...
    for idx, opening in enumerate(self.linear_openings):
        # ...
        base_width = 2
        scaled_width = self.get_scaled_pen_width(base_width)  # ✅ Scalé
        pen = QPen(QColor(200, 0, 0), scaled_width, Qt.DashLine)
        line.setPen(pen)
        # ...
```

## 🧪 Test Rapide

Après avoir appliqué ces modifications, testez avec des plans de tailles différentes :

### Test 1 : Petit Plan (800×600)
- Charger un plan de 800×600 pixels
- Vérifier que les bulles et lignes sont plus petites
- Échelle attendue : ~0.5

### Test 2 : Plan Moyen (2000×1500)
- Charger un plan de 2000×1500 pixels
- Vérifier que tout est à taille normale
- Échelle attendue : 1.0

### Test 3 : Grand Plan (4000×3000)
- Charger un plan de 4000×3000 pixels
- Vérifier que les bulles et lignes sont plus grandes
- Échelle attendue : ~2.0

## 📊 Validation

Pour chaque taille de plan, vérifiez que :
- [ ] Les bulles de texte sont lisibles
- [ ] Les épaisseurs de ligne sont visibles
- [ ] Les points d'ancrage sont manipulables
- [ ] Les proportions restent cohérentes
- [ ] Aucun élément n'est trop grand ou trop petit

## 🐛 Débogage

Si les éléments ne scalent pas :

```python
# Dans PerimeterEntity.__init__(), ajouter :
print(f"Scale manager présent : {self.scale_manager is not None}")

# Dans draw_text(), ajouter :
if self.scale_manager:
    print(f"Facteur d'échelle actuel : {self.scale_manager.scale_factor}")
    margin_scaled = self.get_scaled_padding(2)
    print(f"Margin : 2 → {margin_scaled}")
```

## 🎯 Résultat Attendu

Avec ces modifications, `PerimeterEntity` devrait :
- S'adapter automatiquement à la taille du plan
- Garder des proportions cohérentes
- Rester lisible et manipulable sur tous les plans
- Ne plus avoir de problème de bulles trop grandes sur petits plans

---

**💡 Conseil** : Appliquez le même pattern à `PolygonEntity`, `LineEntity`, et `OpeningEntity` pour une cohérence totale.

