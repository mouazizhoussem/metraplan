# 📊 Guide des Logs du Système d'Échelle Automatique

Ce document explique comment interpréter les logs du système d'échelle automatique pour vérifier son bon fonctionnement.

---

## 🎯 Objectif

Le système d'échelle automatique adapte la taille des éléments graphiques (textes, lignes, handles) en fonction de la taille de l'image chargée :
- **Grande image** → Éléments plus gros (facteur > 1.0)
- **Petite image** → Éléments plus petits (facteur < 1.0)

---

## 📋 Logs à Observer

### 1️⃣ **Au chargement d'une image**

```
🖼️  IMAGE CHARGÉE: 6246 × 4165 pixels

======================================================================
📐 SCALE MANAGER - CALCUL D'ÉCHELLE AUTOMATIQUE
======================================================================
   Image chargée: 6246 × 4165 pixels
   Référence: 2000 × 1500 pixels
   Ratio largeur: 3.123
   Ratio hauteur: 2.777
   Échelle calculée: 2.945
   Échelle précédente: 1.000
   ✅ Échelle mise à jour: 1.00 → 2.95
   🔔 Signal scale_changed émis
======================================================================
```

**Interprétation** :
- L'image est **3.1x plus large** et **2.8x plus haute** que la référence
- Le facteur d'échelle calculé est **2.945** (presque 3x)
- Tous les éléments graphiques seront donc **~3x plus gros**

---

### 2️⃣ **Lors du redessinage des entités**

```
🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄
🔄 ON_SCALE_CHANGED - Redessinage avec échelle 2.95
🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄
   📊 Nombre d'entités à redessiner: 3

   [1/3] Redessinage: perimeter 'Périmètre 1'
      🎨 Appel de draw()...
      ✅ Redessinage terminé

   [2/3] Redessinage: polygon 'Surface 1'
      🎨 Appel de draw()...
      ✅ Redessinage terminé

   [3/3] Redessinage: line 'Distance 1'
      🎨 Appel de draw()...
      ✅ Redessinage terminé

   🏷️  Mise à jour de la légende...
   🔄 Rafraîchissement de la scène...
🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄🔄
✅ ON_SCALE_CHANGED TERMINÉ
```

**Interprétation** :
- Toutes les entités existantes sont redessinées avec la nouvelle échelle
- Aucune erreur ne doit apparaître

---

### 3️⃣ **Lors de la création d'une nouvelle entité**

```
   🔗 ScaleManager assigné à perimeter 'Périmètre 2' (scale: 2.95)
```

**Interprétation** :
- Le `ScaleManager` est correctement assigné à la nouvelle entité
- L'échelle actuelle (2.95) est disponible pour cette entité

---

### 4️⃣ **Lors du dessin des bulles de texte**

```
      🔤 PerimeterEntity: Scaling font (base: 10pt, scale: 2.95)
   📝 Font: 10pt → 29pt (scale: 2.95)
   📦 Padding: 2px → 6px (scale: 2.95)
   ↔️  Offset: 15px → 44px (scale: 2.95)
```

**Interprétation** :
- Police de base : 10pt → **29pt** (3x plus grand)
- Padding de base : 2px → **6px** (3x plus grand)
- Offset de base : 15px → **44px** (3x plus grand)
- ✅ **Le scaling fonctionne correctement !**

---

### 5️⃣ **Pour les épaisseurs de ligne**

```
   🖊️  Pen: 2px → 5.9px (scale: 2.95)
```

**Interprétation** :
- Épaisseur de base : 2px → **5.9px** (3x plus épais)

---

### 6️⃣ **Pour les handles (anchor points)**

```
   📏 Size: 16px → 47.1px (scale: 2.95)
   📏 Size: 40px → 117.8px (scale: 2.95)
   🖊️  Pen: 3px → 8.8px (scale: 2.95)
```

**Interprétation** :
- Taille visible : 16px → **47px** (3x plus grand)
- Zone cliquable : 40px → **118px** (3x plus grande)
- Contour : 3px → **9px** (3x plus épais)

---

## ⚠️ Problèmes Potentiels

### ❌ **ScaleManager non assigné**

```
   ⚠️  ScaleManager NON assigné à perimeter 'Périmètre 1'
   ⚠️  PerimeterEntity: Aucun scale_manager! Font par défaut utilisé
```

**Cause** : L'entité a été dessinée **AVANT** d'être ajoutée au `EntityManager`

**Solution** : Vérifier que l'ordre est correct dans les tools :
```python
# ✅ CORRECT
entity_manager.add_entity(entity)  # Assigne scale_manager
entity.draw(scene)                 # Utilise scale_manager

# ❌ INCORRECT
entity.draw(scene)                 # Pas encore de scale_manager !
entity_manager.add_entity(entity)  # Trop tard
```

---

### ❌ **Échelle inchangée**

```
   ℹ️ Échelle inchangée: 1.00
```

**Cause** : La nouvelle image a la même taille que la précédente (ou ratio équivalent)

**Solution** : Tester avec des images de tailles très différentes

---

## ✅ Test de Validation

Pour valider le bon fonctionnement du système d'échelle :

### Test 1 : Grande Image
1. Charger une **grande image** (ex: 6246×4165)
2. Vérifier dans les logs : `Échelle calculée: 2.945` (environ)
3. Dessiner un périmètre
4. Vérifier : `Font: 10pt → 29pt`
5. **Résultat attendu** : Bulles et textes visiblement **plus gros**

### Test 2 : Petite Image
1. Charger une **petite image** (ex: 990×700)
2. Vérifier dans les logs : `Échelle calculée: 0.481` (environ)
3. Dessiner un périmètre
4. Vérifier : `Font: 10pt → 6pt` (minimum appliqué)
5. **Résultat attendu** : Bulles et textes visiblement **plus petits**

### Test 3 : Entités Existantes
1. Charger une grande image avec des entités déjà dessinées
2. Vérifier le bloc `ON_SCALE_CHANGED`
3. Toutes les entités doivent être redessinées
4. **Résultat attendu** : Les anciennes entités s'adaptent à la nouvelle échelle

---

## 🔧 Désactiver les Logs (si trop verbeux)

Pour réduire la verbosité, commentez les lignes `print()` dans :
- `core/scale_manager.py` (méthodes `scale_*`)
- `core/entity_manager.py` (assignation scale_manager)
- `entities/*.py` (logs de scaling dans draw_text)

Conservez uniquement les logs principaux dans :
- `core/scale_manager.py` → `set_scale_from_image()` (calcul d'échelle)
- `core/canvas_view.py` → `on_scale_changed()` (redessinage)

---

## 📈 Formule de Calcul

```python
width_ratio = image_width / 2000
height_ratio = image_height / 1500
scale_factor = sqrt(width_ratio × height_ratio)
scale_factor = clamp(scale_factor, 0.3, 3.0)  # Limites
```

**Exemples** :
- Image 6246×4165 → scale = 2.945
- Image 2000×1500 → scale = 1.000 (référence)
- Image 990×700 → scale = 0.481
- Image 400×300 → scale = 0.300 (minimum)
- Image 10000×10000 → scale = 3.000 (maximum)

---

## 💡 Conseils

1. **Au premier test**, laissez tous les logs activés pour comprendre le flux
2. **Une fois validé**, désactivez les logs des méthodes `scale_*` (trop verbeux)
3. **Gardez** les logs de `set_scale_from_image()` et `on_scale_changed()` pour débogage
4. **Si problème**, vérifiez l'ordre `add_entity()` → `draw()` dans tous les tools

---

🎉 **Bon diagnostic !**

