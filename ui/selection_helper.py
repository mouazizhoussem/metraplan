class SelectionHelper:
    """
    Regroupe la gestion des sélections et des signaux associés pour alléger MainWindow.
    Logique conservée, seulement déplacée.
    """

    def __init__(self, window):
        self.w = window

    # --- Connexions d'entités ---
    def setup_entity_signals(self):
        if hasattr(self.w.canvas_view, 'entity_manager'):
            entities = self.w.canvas_view.entity_manager.get_all_entities()
            for entity in entities:
                self.connect_entity_signals(entity)

    def connect_entity_signals(self, entity):
        if hasattr(entity, 'entityClicked'):
            try:
                entity.entityClicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            try:
                entity.entityClicked.connect(
                    lambda ent=entity: self.on_entity_selected_from_scene(ent))
            except Exception as e:
                pass

    # --- Sélection depuis la scène ---
    def on_entity_selected_from_scene(self, entity):
        if not entity:
            return
        try:
            if hasattr(self.w.canvas_view, 'scene') and self.w.canvas_view.scene:
                self.w.canvas_view.scene.clearSelection()
                if hasattr(self.w.canvas_view, 'entity_manager'):
                    for other_entity in self.w.canvas_view.entity_manager.get_all_entities():
                        if other_entity != entity and hasattr(other_entity, 'set_selected'):
                            try:
                                other_entity.set_selected(False)
                            except Exception as e:
                                pass

            if hasattr(entity, 'set_selected'):
                entity.set_selected(True)

            if hasattr(self.w, 'properties_dock') and self.w.properties_dock:
                self.w.properties_dock.select_entity(entity)
                self.w.update_properties_entities_list()
        except Exception as e:
            import traceback
            traceback.print_exc()

        self.w.update_toolbar_selection(entity)

    def on_selection_changed(self):
        if not hasattr(self.w.canvas_view, 'scene') or not self.w.canvas_view.scene:
            return

        selected_items = self.w.canvas_view.scene.selectedItems()

        if not selected_items:
            if hasattr(self.w, 'properties_dock'):
                self.w.properties_dock.clear_selection()
            self.w.update_toolbar_selection(None)
            return

        item = selected_items[0]
        entity_id = item.data(1) if hasattr(item, 'data') else None

        if entity_id and hasattr(self.w.canvas_view, 'entity_manager'):
            entity = self.w.canvas_view.entity_manager.get_entity(entity_id)
            if entity and hasattr(self.w, 'properties_dock'):
                self.w.properties_dock.select_entity(entity)
                self.w.update_toolbar_selection(entity)

