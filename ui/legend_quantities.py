from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QTableWidgetItem, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class LegendQuantitiesHelper:
    """
    Regroupe la logique de mise à jour de la légende et du relevé quantitatif.
    Objectif: alléger MainWindow sans changer la logique métier.
    """

    def __init__(self, window):
        self.w = window
        # Logs activés pour diagnostiquer le comportement de la légende.
        self.debug = True

    def _log(self, message: str):
        if self.debug:
            pass

    def format_number(self, value):
        """Formate un nombre: espace milliers + ,00."""
        try:
            num = float(value)
        except (TypeError, ValueError):
            num = 0.0
        formatted = f"{num:,.2f}"
        return formatted.replace(",", " ").replace(".", ",")

    def format_money(self, value):
        """Formate un montant: $ + espace milliers + ,00."""
        return f"$ {self.format_number(value)}"

    def _smart_qty(self, entity):
        """
        Même logique dynamique que le panneau Pages & Mesures.
        Retourne (valeur, unité) avec unités: m, m², m³, ml, u.
        """
        etype = getattr(entity, 'entity_type', '')
        height = float(getattr(entity, 'height', 0.0) or 0.0)
        thick = float(getattr(entity, 'thickness', 0.0) or 0.0)
        self._log(
            f"_smart_qty entité='{getattr(entity, 'name', '?')}' type='{etype}' h={height:.2f} e={thick:.2f}")
        is_grp = bool(getattr(entity, 'is_group_parent', False))
        children = list(getattr(entity, 'child_entities', []) or [])
        members = [entity] + children if (is_grp and children) else [entity]

        # Surface
        if etype in ('polygon', 'surface'):
            # Volume si épaisseur (dalle) OU hauteur (voile/mur horizontal) renseignée
            if height > 0 or thick > 0:
                vol = 0.0
                for m in members:
                    if hasattr(m, 'calculate_volume'):
                        try:
                            vol += float(m.calculate_volume() or 0.0)
                        except Exception:
                            pass
                return vol, "m³"
            if is_grp and children and hasattr(entity, 'calculate_total_group_area'):
                try:
                    return float(entity.calculate_total_group_area() or 0.0), "m²"
                except Exception:
                    pass
            try:
                if getattr(entity, 'openings', None):
                    return float(entity.calculate_net_area() or 0.0), "m²"
                return float(entity.calculate_area() or 0.0), "m²"
            except Exception:
                return 0.0, "m²"

        # Périmètre / ligne
        if etype in ('perimeter', 'line'):
            if height > 0 and thick > 0:
                vol = 0.0
                for m in members:
                    if hasattr(m, 'calculate_volume'):
                        try:
                            vol += float(m.calculate_volume() or 0.0)
                        except Exception:
                            pass
                return vol, "m³"
            if height > 0:
                surf = 0.0
                for m in members:
                    if hasattr(m, 'calculate_surface_laterale'):
                        try:
                            surf += float(m.calculate_surface_laterale() or 0.0)
                        except Exception:
                            pass
                return surf, "m²"
            if is_grp and children and hasattr(entity, 'calculate_total_group_length'):
                try:
                    return float(entity.calculate_total_group_length() or 0.0), "ml"
                except Exception:
                    pass
            try:
                return float(entity.calculate_perimeter_length() or 0.0), "ml"
            except Exception:
                return 0.0, "ml"

        # Compteur
        if etype == 'point':
            count = 1
            gid = getattr(entity, 'group_id', None)
            if gid and hasattr(self.w, 'canvas_view') and hasattr(self.w.canvas_view, 'entity_manager'):
                try:
                    count = len(self.w.canvas_view.entity_manager.get_points_by_group(gid))
                except Exception:
                    pass
            length = float(getattr(entity, 'length', 0.0) or 0.0)
            height = float(getattr(entity, 'height', 0.0) or 0.0)
            thick = float(getattr(entity, 'thickness', 0.0) or 0.0)
            if length > 0 and height > 0 and thick > 0:
                return length * height * thick * count, "m³"
            if length > 0 and height > 0:
                return length * height * count, "m²"
            if length > 0:
                return length * count, "m"
            return float(count), "u."

        return 0.0, ""

    def _fmt_qty(self, value: float, unit: str) -> str:
        if unit == "m³":
            return f"{value:.2f} m³"
        if unit == "m²":
            return f"{value:.2f} m²"
        if unit == "ml":
            return f"{value:.2f} ml"
        if unit == "m":
            return f"{value:.2f} m"
        if unit == "u.":
            n = int(round(value))
            return f"{n} U"
        return f"{value:.2f}" if value else "-"

    def _ensure_unit_suffix(self, text: str, type_label: str) -> str:
        """Garantit une unité visible même si un texte legacy est renvoyé."""
        if not text:
            text = "0,00"
        low = text.lower()
        if any(u in low for u in ("m³", "m²", " ml", " m", " u", "unit")):
            return text
        t = (type_label or "").lower()
        if t == "volume":
            return f"{text} m³"
        if t == "surface":
            return f"{text} m²"
        if t == "distance" or t == "périmètre":
            return f"{text} m"
        if t == "point":
            return f"{text} U"
        return text

    def _pick_best_quantity_reference(self, entities):
        """Choisit l'entité la plus pertinente pour le calcul dynamique."""
        if not entities:
            return None

        def _score(ent):
            h = float(getattr(ent, "height", 0.0) or 0.0)
            th = float(getattr(ent, "thickness", 0.0) or 0.0)
            ln = float(getattr(ent, "length", 0.0) or 0.0)
            parent = 1.0 if bool(getattr(ent, "is_group_parent", False)) else 0.0
            # Priorité aux dimensions réelles, puis au parent de groupe.
            return (h, th, ln, parent)

        return max(entities, key=_score)

    def update_grand_total_row(self):
        """Met à jour la ligne Total général si elle existe."""
        if not hasattr(self.w, 'quantities_table'):
            return
        row = self.w.quantities_table.rowCount() - 1
        if row < 0:
            return
        name_item = self.w.quantities_table.item(row, 2)
        if not name_item or name_item.text() != "TOTAL GÉNÉRAL":
            return
        total = 0.0
        for r in range(self.w.quantities_table.rowCount() - 1):
            total_item = self.w.quantities_table.item(r, 4)
            if total_item:
                text = total_item.text().replace("$", "").replace(" ", "").replace("\u202f", "").replace(",", ".").strip()
                try:
                    total += float(text) if text else 0.0
                except ValueError:
                    pass
        total_item = self.w.quantities_table.item(row, 4)
        if total_item:
            total_item.setText(self.format_money(total))

    # --- Relevé quantitatif ---
    def update_quantities_table_for_entity(self, entity):
        if not entity:
            return
        # Colonne Actions supprimée -> rafraîchir tout
        self.update_quantities_table()

    def update_table_row(self, row, entity):
        """Met à jour une ligne spécifique du tableau"""
        entity_type = self.w.get_entity_type_label(entity)
        type_item = QTableWidgetItem(entity_type)
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
        type_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.w.quantities_table.setItem(row, 0, type_item)

        name = getattr(entity, 'name', 'Sans nom')
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_item.setBackground(QColor(240, 240, 240))
        name_item.setForeground(QColor(80, 80, 80))
        name_item.setToolTip("⚠️ Modifiez le nom dans le panneau des propriétés")
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.w.quantities_table.setItem(row, 1, name_item)

        value = self.w.get_entity_numeric_value(entity)
        value_item = QTableWidgetItem(self.format_number(value))
        value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
        value_item.setData(Qt.UserRole, value)
        value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.w.quantities_table.setItem(row, 2, value_item)

        unit_price_item = QTableWidgetItem(self.format_money(0.0))
        unit_price_item.setFlags(unit_price_item.flags() | Qt.ItemIsEditable)
        unit_price_item.setData(Qt.UserRole, None)
        unit_price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.w.quantities_table.setItem(row, 3, unit_price_item)

        total_item = QTableWidgetItem(self.format_money(0.0))
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.w.quantities_table.setItem(row, 4, total_item)

    def update_quantities_table(self):
        """Met à jour le tableau complet"""
        self._log("update_quantities_table: reset + rebuild complet")
        self.w.quantities_table.setRowCount(0)
        self.update_quantities_table_fast()

    def update_quantities_table_fast(self):
        """Version rapide : remplit toutes les lignes d'un coup"""
        try:
            if hasattr(self.w, '_quantities_block_updates'):
                self.w._quantities_block_updates = True
            grouped_data = self.get_grouped_entities()
            self._log(f"update_quantities_table_fast: groupes={len(grouped_data)}")
            self.w.quantities_table.setRowCount(len(grouped_data) + 1)

            for row, group_info in enumerate(grouped_data):
                group_key = group_info.get('group_key')
                # Type
                type_item = QTableWidgetItem(group_info['type_label'])
                if group_info['count'] > 1:
                    type_item.setForeground(Qt.darkBlue)
                    font = type_item.font()
                    font.setBold(True)
                    type_item.setFont(font)
                type_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.w.quantities_table.setItem(row, 0, type_item)

                # Nom
                name_display = group_info['name']
                if group_info['count'] > 1 and not group_info.get('is_point_group'):
                    name_display = f"{name_display} (×{group_info['count']})"
                name_item = QTableWidgetItem(name_display)
                if group_info['count'] > 1 and not group_info.get('is_point_group'):
                    name_item.setForeground(Qt.darkBlue)
                    font = name_item.font()
                    font.setBold(True)
                    name_item.setFont(font)
                name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.w.quantities_table.setItem(row, 1, name_item)

                # Quantité
                quantity_value = group_info['total_value']
                quantity_text = group_info.get('total_text') or self.format_number(quantity_value)
                quantity_text = self._ensure_unit_suffix(quantity_text, group_info.get('type_label', ''))
                self._log(
                    f"row={row} name='{group_info.get('name')}' type='{group_info.get('type_label')}' qty='{quantity_text}' value={quantity_value:.4f}")
                quantity_item = QTableWidgetItem(quantity_text)
                if group_info['count'] > 1:
                    quantity_item.setForeground(QColor(33, 150, 243))
                    font = quantity_item.font()
                    font.setBold(True)
                    quantity_item.setFont(font)
                quantity_item.setFlags(quantity_item.flags() & ~Qt.ItemIsEditable)
                quantity_item.setData(Qt.UserRole, quantity_value)
                quantity_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.w.quantities_table.setItem(row, 2, quantity_item)

                # Prix unitaire (editable)
                unit_price = self.w._quantities_unit_prices.get(group_key, 0.0)
                unit_price_item = QTableWidgetItem(
                    self.format_number(unit_price))
                unit_price_item.setFlags(unit_price_item.flags() | Qt.ItemIsEditable)
                unit_price_item.setData(Qt.UserRole, group_key)
                unit_price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.w.quantities_table.setItem(row, 3, unit_price_item)

                # Total
                total = quantity_value * unit_price
                total_item = QTableWidgetItem(self.format_money(total))
                total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
                total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.w.quantities_table.setItem(row, 4, total_item)

            # Ligne Total général
            total_row = self.w.quantities_table.rowCount() - 1
            type_item = QTableWidgetItem("")
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            self.w.quantities_table.setItem(total_row, 0, type_item)

            name_item = QTableWidgetItem("")
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.w.quantities_table.setItem(total_row, 1, name_item)

            # Fusionner Quantité + Prix unitaire pour le libellé
            self.w.quantities_table.setSpan(total_row, 2, 1, 2)
            qty_item = QTableWidgetItem("TOTAL GÉNÉRAL")
            qty_item.setFlags(qty_item.flags() & ~Qt.ItemIsEditable)
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            font = qty_item.font()
            font.setBold(True)
            qty_item.setFont(font)
            self.w.quantities_table.setItem(total_row, 2, qty_item)

            total_item = QTableWidgetItem(self.format_money(0.0))
            total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_font = total_item.font()
            total_font.setBold(True)
            total_item.setFont(total_font)
            self.w.quantities_table.setItem(total_row, 4, total_item)
            self.update_grand_total_row()

            # Cache pour les comparaisons ultérieures
            self.w._last_grouped_data = grouped_data
            if hasattr(self.w, '_quantities_block_updates'):
                self.w._quantities_block_updates = False

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.w._last_grouped_data = []
            if hasattr(self.w, '_quantities_block_updates'):
                self.w._quantities_block_updates = False

    def update_quantities_values_only(self):
        """Met à jour uniquement les valeurs (colonne 2) si structure inchangée."""
        if not hasattr(self.w, 'canvas_view') or not hasattr(self.w.canvas_view, 'entity_manager'):
            return

        grouped_data = self.get_grouped_entities()
        self._log(
            f"update_quantities_values_only: rows_table={self.w.quantities_table.rowCount()} rows_grouped={len(grouped_data)}")

        if self.w.quantities_table.rowCount() != len(grouped_data):
            self._log("values_only: mismatch lignes -> rebuild complet")
            self.update_quantities_table_fast()
            return

        if len(self.w._last_grouped_data) == len(grouped_data):
            structure_changed = False
            for old_group, new_group in zip(self.w._last_grouped_data, grouped_data):
                if (old_group.get('name') != new_group.get('name') or
                        old_group.get('type_label') != new_group.get('type_label') or
                        old_group.get('count') != new_group.get('count')):
                    structure_changed = True
                    break
            if structure_changed:
                self._log("values_only: structure_changed=True -> rebuild complet")
                self.update_quantities_table_fast()
                return
        else:
            self._log("values_only: cache size different -> rebuild complet")
            self.update_quantities_table_fast()
            return

        if hasattr(self.w, '_quantities_block_updates'):
            self.w._quantities_block_updates = True
        for row, group_info in enumerate(grouped_data):
            quantity_value = group_info['total_value']
            quantity_item = self.w.quantities_table.item(row, 2)
            if quantity_item:
                quantity_text = group_info.get('total_text') or self.format_number(quantity_value)
                quantity_text = self._ensure_unit_suffix(quantity_text, group_info.get('type_label', ''))
                quantity_item.setText(quantity_text)
                self._log(
                    f"values_only row={row} name='{group_info.get('name')}' type='{group_info.get('type_label')}' qty='{quantity_text}' value={quantity_value:.4f}")
                quantity_item.setData(Qt.UserRole, quantity_value)
                quantity_item.setFlags(quantity_item.flags() & ~Qt.ItemIsEditable)
                quantity_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if group_info['count'] > 1:
                    if quantity_item.foreground().color() != QColor(33, 150, 243):
                        quantity_item.setForeground(QColor(33, 150, 243))
                        font = quantity_item.font()
                        font.setBold(True)
                        quantity_item.setFont(font)

            unit_price_item = self.w.quantities_table.item(row, 3)
            unit_price = 0.0
            if unit_price_item:
                group_key = unit_price_item.data(Qt.UserRole)
                unit_price = self.w._quantities_unit_prices.get(group_key, 0.0)

            total_item = self.w.quantities_table.item(row, 4)
            if total_item:
                total_item.setText(self.format_money(quantity_value * unit_price))
                total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.w._last_grouped_data = grouped_data
        self.w.update_toolbar_summary()
        self.update_grand_total_row()
        if hasattr(self.w, '_quantities_block_updates'):
            self.w._quantities_block_updates = False

    def get_grouped_entities(self):
        """Regroupe les entités par (nom, type) en excluant les enfants et ouvertures."""
        entities = None
        if hasattr(self.w, 'get_pdf_entities_for_quantities'):
            entities = self.w.get_pdf_entities_for_quantities()

        # Fallback sur les entités live du canvas — UNIQUEMENT hors d'un switch de page.
        # Pendant un switch, le canvas est en état transitoire (clear_scene fait,
        # restore pas encore terminé) : les entités live appartiendraient à la MAUVAISE
        # page ou seraient vides, ce qui écraserait l'affichage correct.
        is_switching = getattr(self.w, '_is_switching_pdf_page', False)
        if not is_switching and (entities is None or len(entities) == 0):
            live_entities = self.w.canvas_view.entity_manager.get_all_entities()
            if entities is None or len(live_entities) > 0:
                entities = live_entities

        if entities is None:
            entities = []

        self._log(f"get_grouped_entities: source_entities={len(entities)}")
        return self.get_grouped_entities_from_entities(entities)

    def get_grouped_entities_from_entities(self, entities):
        """Regroupe une liste d'entités par (nom, type) en excluant les enfants et ouvertures."""
        groups = {}

        if self.debug:
            pass

        for entity in entities:
            entity_type_raw = entity.entity_type if hasattr(entity, 'entity_type') else ''
            if entity_type_raw == 'opening':
                continue
            # Exclure la ligne d'échelle de référence du relevé
            name = entity.name if hasattr(entity, 'name') else ''
            if entity_type_raw == 'line' and isinstance(name, str) and name.strip().lower() == "échelle de référence":
                continue

            has_parent = hasattr(entity, 'parent_entity') and entity.parent_entity
            if has_parent:
                continue

            name = entity.name if hasattr(entity, 'name') else 'Sans nom'
            entity_type = self.w.get_entity_type_label(entity)
            is_point = getattr(entity, 'entity_type', '') == 'point'

            # Règles de typage dynamiques
            is_surface = (entity_type == "Surface")
            is_perimeter = (entity_type == "Périmètre")
            has_height = hasattr(entity, 'height') and getattr(entity, 'height', 0) > 0
            has_thickness = hasattr(entity, 'thickness') and getattr(entity, 'thickness', 0) > 0

            # Surface : si hauteur OU épaisseur > 0, on bascule en Volume (m³)
            is_volume_surface = is_surface and (has_height or has_thickness) and not is_point
            if is_volume_surface:
                entity_type = "Volume"

            # Périmètre : si épaisseur > 0 et hauteur > 0 → Volume (m³)
            # sinon si hauteur > 0 → Surface (m²) avec surface latérale
            if is_perimeter and not is_point:
                if has_height and has_thickness:
                    entity_type = "Volume"
                elif has_height:
                    entity_type = "Surface"

            group_id = getattr(entity, 'group_id', None)
            key = (group_id, entity_type) if group_id else (name, entity_type)

            if self.debug:
                pass

            if key not in groups:
                groups[key] = {
                    'name': name,
                    'type_label': entity_type,
                    'entities': [],
                    'values': [],
                    'values_volume': [],
                    'values_lateral': [],
                    'count': 0,
                    'is_point_group': is_point,
                    'group_key': key
                }

            is_group_parent = getattr(entity, 'is_group_parent', False)
            child_entities = getattr(entity, 'child_entities', []) or []

            if is_group_parent and child_entities:
                # Ajouter le parent + tous les enfants pour permettre la suppression groupée
                groups[key]['entities'].append(entity)
                groups[key]['entities'].extend(child_entities)
                groups[key]['count'] += 1 + len(child_entities)

                # Valeur = aire/longueur totale du groupe si disponible
                # Pour périmètre avec hauteur (Surface m²) : sommer les surfaces, pas les longueurs
                total_value = None
                total_volume = 0.0
                total_lateral = 0.0
                if hasattr(entity, 'calculate_total_group_area'):
                    try:
                        total_value = entity.calculate_total_group_area()
                    except Exception:
                        total_value = None
                # Ne PAS utiliser calculate_total_group_length pour Surface/Volume (périmètres avec hauteur)
                if total_value is None and entity_type == "Périmètre" and hasattr(entity, 'calculate_total_group_length'):
                    try:
                        total_value = entity.calculate_total_group_length()
                    except Exception:
                        total_value = None
                # Si on a un volume à calculer, cumuler parent + enfants
                # IMPORTANT : Cette logique agrège les volumes de tous les membres du groupe
                if entity_type == "Volume":
                    candidates = [entity] + list(child_entities)
                    for ent in candidates:
                        if hasattr(ent, 'calculate_volume'):
                            try:
                                total_volume += ent.calculate_volume()
                            except Exception:
                                pass
                if total_value is None:
                    # fallback : parent + somme des enfants (surfaces m² pour périmètres avec hauteur)
                    parent_val = self.get_entity_numeric_value(entity)
                    child_sum = 0.0
                    child_vol = 0.0
                    child_lat = 0.0
                    for child in child_entities:
                        child_sum += self.get_entity_numeric_value(child)
                        if hasattr(child, 'calculate_volume'):
                            try:
                                child_vol += child.calculate_volume()
                            except Exception:
                                pass
                        if hasattr(child, 'calculate_surface_laterale'):
                            try:
                                child_lat += child.calculate_surface_laterale()
                            except Exception:
                                pass
                    total_value = (child_sum + parent_val) if child_entities else parent_val
                    total_volume = child_vol
                    if hasattr(entity, 'calculate_volume'):
                        try:
                            total_volume += entity.calculate_volume()
                        except Exception:
                            pass
                    total_lateral = child_lat
                    if hasattr(entity, 'calculate_surface_laterale'):
                        try:
                            total_lateral += entity.calculate_surface_laterale()
                        except Exception:
                            pass
                else:
                    # Calculer surface latérale à partir du parent + enfants si dispo
                    candidates = [entity] + list(child_entities)
                    for ent in candidates:
                        if hasattr(ent, 'calculate_surface_laterale'):
                            try:
                                total_lateral += ent.calculate_surface_laterale()
                            except Exception:
                                pass

                groups[key]['values'].append(total_value)
                groups[key]['values_volume'].append(total_volume)
                groups[key]['values_lateral'].append(total_lateral)
                if self.debug:
                    pass
            else:
                # Entité non parent de groupe
                groups[key]['entities'].append(entity)
                groups[key]['count'] += 1
                if is_point:
                    numeric_value = self.get_entity_numeric_value(entity)
                    vol = 0.0
                    lat = 0.0
                # Surface avec hauteur : on prend le volume et on étiquette Volume
                elif is_volume_surface:
                    numeric_value = 0.0
                    try:
                        numeric_value = entity.calculate_volume()
                    except Exception:
                        numeric_value = 0.0
                    vol = numeric_value
                    lat = 0.0
                # Périmètre avec hauteur seule : surface latérale (m²) uniquement
                elif is_perimeter and has_height and not has_thickness:
                    numeric_value = 0.0
                    vol = 0.0
                    lat = 0.0
                    try:
                        lat = entity.calculate_surface_laterale()
                    except Exception:
                        lat = 0.0
                    numeric_value = lat
                # Périmètre avec hauteur + épaisseur : volume uniquement (m³)
                elif is_perimeter and has_height and has_thickness:
                    numeric_value = 0.0
                    vol = 0.0
                    lat = 0.0
                    try:
                        vol = entity.calculate_volume()
                    except Exception:
                        vol = 0.0
                    numeric_value = vol
                else:
                    numeric_value = self.get_entity_numeric_value(entity)
                    vol = 0.0
                    lat = 0.0
                    if hasattr(entity, 'calculate_volume'):
                        try:
                            vol = entity.calculate_volume()
                        except Exception:
                            vol = 0.0
                    if hasattr(entity, 'calculate_surface_laterale'):
                        try:
                            lat = entity.calculate_surface_laterale()
                        except Exception:
                            lat = 0.0
                groups[key]['values'].append(numeric_value)
                groups[key]['values_volume'].append(vol)
                groups[key]['values_lateral'].append(lat)
                if self.debug:
                    pass

        # IMPORTANT : Agrégation finale des valeurs par groupe
        # Cette section calcule les totaux pour chaque groupe d'entités
        grouped_data = []
        for group in groups.values():
            total_value = sum(group['values']) if group['values'] else 0.0
            total_volume = sum(group['values_volume']) if group['values_volume'] else 0.0
            total_lateral = sum(group['values_lateral']) if group['values_lateral'] else 0.0
            total_text = self.w.get_entity_value_text(
                group['entities'][0]) if group['entities'] else "N/A"

            # Recalcul dynamique unifié (même comportement que Pages & Mesures)
            if group['entities']:
                ref = self._pick_best_quantity_reference(group['entities'])
                try:
                    qty_val, qty_unit = self._smart_qty(ref)
                    # Fallback robuste pour les groupes reconstruits sans liens parent/enfant :
                    # agréger tous les membres si aucune relation enfant n'est disponible.
                    has_linked_parent = any(
                        bool(getattr(ent, "is_group_parent", False))
                        and bool(getattr(ent, "child_entities", []) or [])
                        for ent in group['entities']
                    )
                    if not has_linked_parent and len(group['entities']) > 1:
                        agg_val = 0.0
                        same_unit_only = True
                        seen = set()
                        for ent in group['entities']:
                            ent_key = getattr(ent, "entity_id", None) or id(ent)
                            if ent_key in seen:
                                continue
                            seen.add(ent_key)
                            ev, eu = self._smart_qty(ent)
                            if eu != qty_unit:
                                same_unit_only = False
                                break
                            agg_val += float(ev or 0.0)
                        if same_unit_only:
                            qty_val = agg_val

                    total_value = qty_val
                    total_text = self._fmt_qty(qty_val, qty_unit)
                    self._log(
                        f"groupe='{group['name']}' ref='{getattr(ref, 'name', '?')}' -> qty={qty_val:.4f} unit={qty_unit}")
                    if qty_unit == "m³":
                        group['type_label'] = "Volume"
                    elif qty_unit == "m²":
                        group['type_label'] = "Surface"
                    elif qty_unit in ("ml", "m"):
                        group['type_label'] = "Distance"
                    elif qty_unit == "u.":
                        group['type_label'] = "Point"
                except Exception:
                    pass

            grouped_data.append({
                'name': group['name'],
                'type_label': group['type_label'],
                'entities': group['entities'],
                'group_key': group.get('group_key'),
                'total_value': total_value,
                'total_volume': total_volume,
                'total_lateral': total_lateral,
                'total_text': total_text,
                'count': group['count'],
                'is_point_group': group.get('is_point_group', False)
            })

        grouped_data.sort(key=lambda x: (x['type_label'], x['name']))

        if self.debug:
            pass

        return grouped_data

    def get_entity_numeric_value(self, entity):
        """Valeur numérique pour surface/perim/longueur (utilise net area si dispo)."""
        # Gestion spécifique des volumes/surfaces dérivées
        if hasattr(entity, 'entity_type'):
            ent_type = entity.entity_type
            has_height = hasattr(entity, 'height') and getattr(entity, 'height', 0) > 0
            has_thickness = hasattr(entity, 'thickness') and getattr(entity, 'thickness', 0) > 0

            # Surface/polygone avec hauteur ou épaisseur -> volume
            if ent_type in ('surface', 'polygon') and (has_height or has_thickness):
                if hasattr(entity, 'calculate_volume'):
                    try:
                        return entity.calculate_volume()
                    except Exception:
                        return 0.0

            # Périmètre avec hauteur -> surface latérale (m²) ou volume (m³)
            if ent_type == 'perimeter' and has_height:
                if has_thickness and hasattr(entity, 'calculate_volume'):
                    try:
                        return entity.calculate_volume()
                    except Exception:
                        return 0.0
                if hasattr(entity, 'calculate_surface_laterale'):
                    try:
                        return entity.calculate_surface_laterale()
                    except Exception:
                        return 0.0

        if getattr(entity, 'entity_type', '') == 'point':
            length = float(getattr(entity, 'length', 0.0) or 0.0)
            height = float(getattr(entity, 'height', 0.0) or 0.0)
            thickness = float(getattr(entity, 'thickness', 0.0) or 0.0)
            if length > 0 and height > 0 and thickness > 0:
                return length * height * thickness
            if length > 0 and height > 0:
                return length * height
            if length > 0:
                return length
            return 1.0
        if hasattr(entity, 'calculate_net_area'):
            try:
                return entity.calculate_net_area()
            except Exception as e:
                pass
        elif hasattr(entity, 'calculate_area'):
            try:
                return entity.calculate_area()
            except Exception as e:
                pass

        if hasattr(entity, 'calculate_perimeter_length'):
            try:
                return entity.calculate_perimeter_length()
            except Exception as e:
                pass

        if hasattr(entity, 'calculate_length'):
            try:
                return entity.calculate_length()
            except Exception:
                pass

        if hasattr(entity, 'calculate_distance'):
            try:
                return entity.calculate_distance()
            except Exception:
                pass

        return 0.0

    def delete_entity_group(self, entities):
        """Supprime toutes les entités d'un groupe (même nom)."""
        if not entities:
            return

        if len(entities) > 1:
            name = getattr(entities[0], 'name', 'Sans nom')
            reply = QMessageBox.question(
                self.w,
                "Confirmation",
                f"Supprimer toutes les {len(entities)} entités '{name}' ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        deleted_count = 0
        for entity in entities:
            if hasattr(entity, 'entity_id') and hasattr(self.w.canvas_view, 'entity_manager'):
                entity_id = entity.entity_id
                if self.w.canvas_view.entity_manager.remove_entity(entity_id, self.w.canvas_view.scene):
                    deleted_count += 1

        if deleted_count > 0:
            self.update_quantities_table()
            if hasattr(self.w.canvas_view, 'update_legend'):
                self.w.canvas_view.update_legend()
            if hasattr(self.w, 'statusBar'):
                self.w.statusBar().showMessage(
                    f"{deleted_count} entité(s) supprimée(s)", 3000)
            if hasattr(self.w, 'canvas_view'):
                self.w.canvas_view.clean_orphaned_items()

