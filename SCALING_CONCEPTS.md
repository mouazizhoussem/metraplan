# Concepts d'Échelle dans l'Application

## ⚠️ Distinction Importante : Deux Types d'Échelle

L'application utilise **deux systèmes d'échelle distincts** qui ne doivent pas être confondus :

---

## 1️⃣ Échelle Métrique (Calibration)

### 🎯 Objectif
Établir la correspondance entre **pixels** et **unités réelles** (mètres) sur le plan.

### 📊 Concept
```
Échelle Métrique = Pixels / Mètres Réels
```

**Exemple** : Si 100 pixels représentent 1 mètre réel → `pixels_per_meter = 100`

### 🔧 Implémentation
- **Attribut** : `canvas_view.pixels_per_meter`
- **Outil** : `ScaleTool` (calibration avec une distance connue)
- **Utilisation** : Calcul des mesures réelles (distances, surfaces, volumes)

### 📝 Exemple d'Usage
```python
# Dans canvas_view.py
self.pixels_per_meter = 100  # 100 pixels = 1 mètre

# Calcul d'une distance réelle
distance_pixels = 250
distance_meters = distance_pixels / self.pixels_per_meter  # = 2.5 m
```

### 🎨 Interface Utilisateur
- **Outil Règle** : L'utilisateur trace une ligne et indique la distance réelle
- **Dialogue** : "Cette ligne mesure X mètres en réalité"
- **Résultat** : `pixels_per_meter` est calculé automatiquement

---

## 2️⃣ Échelle Visuelle (Adaptation Graphique)

### 🎯 Objectif
Adapter la **taille des éléments graphiques** (bulles, lignes, icônes) à la **taille du plan** pour qu'ils restent lisibles.

### 📊 Concept
```
Échelle Visuelle = √(Taille_Image / Taille_Référence)
```

**Exemple** : 
- Petit plan (800×600) → facteur 0.5 → bulles 2× plus petites
- Grand plan (4000×3000) → facteur 2.0 → bulles 2× plus grandes

### 🔧 Implémentation
- **Classe** : `ScaleManager` (`core/scale_manager.py`)
- **Calcul** : Automatique lors du chargement de l'image
- **Utilisation** : Scaling des fonts, pen widths, paddings, offsets

### 📝 Exemple d'Usage
```python
# Dans une entité (PerimeterEntity, etc.)
base_font_size = 10
scaled_font_size = self.get_scaled_font_size(base_font_size)
# Sur un petit plan : 5pt
# Sur un plan normal : 10pt
# Sur un grand plan : 20pt
```

### 🎨 Résultat Visuel
- Les bulles de texte sont proportionnelles à la taille du plan
- Tout reste lisible, peu importe la résolution de l'image

---

## 📋 Tableau Comparatif

| Aspect | Échelle Métrique | Échelle Visuelle |
|---|---|---|
| **Objectif** | Mesures réelles précises | Lisibilité graphique |
| **Unité** | pixels/mètre | ratio sans unité |
| **Variable** | `pixels_per_meter` | `scale_factor` |
| **Classe** | Aucune (attribut direct) | `ScaleManager` |
| **Outil** | `ScaleTool` (Règle) | Automatique |
| **Modifiable par l'utilisateur** | ✅ Oui (calibration) | ❌ Non (auto) |
| **Affecte les mesures** | ✅ Oui | ❌ Non |
| **Affecte l'affichage** | ❌ Non | ✅ Oui |

---

## 🔄 Relation Entre les Deux

Ces deux échelles sont **indépendantes** et **complémentaires** :

### Échelle Métrique → Mesures Réelles
```python
# Calcul d'une distance en mètres
distance_m = distance_px / self.pixels_per_meter
text = f"{distance_m:.2f} m"
```

### Échelle Visuelle → Affichage de la Bulle
```python
# Taille de la police pour afficher la mesure
font_size = self.get_scaled_font_size(10)
font = QFont("Arial", font_size)
text_item.setFont(font)
```

---

## 💡 Scénario Complet

### Situation
Un utilisateur charge un **grand plan** (4000×3000) d'un bâtiment.

### Étape 1 : Chargement du Plan
```python
# Échelle visuelle calculée automatiquement
scale_manager.set_scale_from_image(4000, 3000)
# → scale_factor ≈ 2.0
```

**Résultat** : Les bulles, lignes et icônes seront 2× plus grandes pour rester lisibles.

### Étape 2 : Calibration Métrique
L'utilisateur utilise l'outil Règle :
- Trace une ligne de 500 pixels
- Indique "5 mètres en réalité"
- `pixels_per_meter = 500 / 5 = 100`

**Résultat** : Les mesures affichées seront précises (1m réel = 100px).

### Étape 3 : Création d'un Périmètre
L'utilisateur trace un périmètre de 2000 pixels.

**Calcul de la mesure réelle** (échelle métrique) :
```python
longueur_m = 2000 / 100 = 20 mètres
text = "20.00 m"
```

**Affichage de la bulle** (échelle visuelle) :
```python
font_size = scale_manager.scale_font_size(10)  # ≈ 20pt (car scale_factor ≈ 2.0)
padding = scale_manager.scale_bubble_padding(2)  # ≈ 4px
```

**Résultat Final** :
- ✅ La mesure affichée est **précise** : "20.00 m"
- ✅ La bulle est **lisible** : police 20pt, bien proportionnée au plan

---

## 🐛 Erreurs Courantes

### ❌ Erreur 1 : Confondre les Deux
```python
# MAUVAIS : Utiliser scale_manager pour les mesures réelles
distance_m = distance_px / scale_manager.scale_factor  # ❌ Incorrect !
```

```python
# BON : Utiliser pixels_per_meter
distance_m = distance_px / self.pixels_per_meter  # ✅ Correct
```

### ❌ Erreur 2 : Appliquer l'Échelle Visuelle aux Coordonnées
```python
# MAUVAIS : Scaler les positions des points
scaled_x = point.x() * scale_manager.scale_factor  # ❌ Non !
```

L'échelle visuelle affecte uniquement :
- ✅ Tailles de police
- ✅ Épaisseurs de ligne
- ✅ Paddings et margins
- ✅ Tailles d'icônes

Elle **n'affecte pas** :
- ❌ Coordonnées des points
- ❌ Dimensions géométriques
- ❌ Calculs de distance

---

## 📚 Résumé

### Quand Utiliser `pixels_per_meter` ?
- Conversion pixels ↔ mètres
- Calcul de longueurs, surfaces, volumes
- Affichage de mesures réelles

### Quand Utiliser `scale_manager.scale_*()` ?
- Taille des polices
- Épaisseur des lignes
- Padding des bulles
- Taille des icônes et handles

### Règle d'Or
> **Les mesures utilisent `pixels_per_meter`.  
> L'affichage graphique utilise `scale_manager`.**

---

**📅 Créé le** : 2025-01-02  
**📌 Version** : 1.0

