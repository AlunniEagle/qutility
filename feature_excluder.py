# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FeatureExcluder
                                 A QGIS plugin component
 Tool to exclude features from a layer based on matching records in another layer
                             -------------------
        begin                : 2025-05-07
        copyright            : (C) 2025 by Lorenzo Alunni
        email                : gis@eagleprojects.it
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from qgis.PyQt import QtGui, QtWidgets, uic # type: ignore
from qgis.PyQt.QtCore import Qt, QVariant # type: ignore
from qgis.core import ( # type: ignore
    QgsProject, QgsVectorLayer, QgsFeatureRequest, 
    QgsGeometry, QgsFeature, QgsDistanceArea, QgsSpatialIndex,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform
)
from qgis.PyQt.QtWidgets import QApplication, QMessageBox # type: ignore


class FeatureExcluder:
    """A class to handle feature exclusion operations"""
    
    def __init__(self, dialog):
        """Constructor.
        
        :param dialog: The dialog instance that contains the UI elements
        """
        self.dialog = dialog
        self.current_group = None

        # Set up proper connections to project layer changes
        # Disconnect any existing connections first to avoid duplicates
        try:
            QgsProject.instance().layersAdded.disconnect(self.populate_layer_lists)
        except:
            pass
        try:
            QgsProject.instance().layersRemoved.disconnect(self.populate_layer_lists)
        except:
            pass
        
        # Connect signals with try-except to prevent crashes
        QgsProject.instance().layersAdded.connect(self.safe_populate_layer_lists)
        QgsProject.instance().layersRemoved.connect(self.safe_populate_layer_lists)

        # Connect signals
        self.dialog.eflayerdef.currentIndexChanged.connect(self.update_source_fields)
        self.dialog.eflayermatch.currentIndexChanged.connect(self.update_match_fields)
        self.dialog.efrun.clicked.connect(self.exclude_features)
        self.dialog.efcheckgeom.stateChanged.connect(self.toggle_tolerance_field)
        self.dialog.efcheckgeom.stateChanged.connect(self.toggle_geometry_options)
        self.dialog.eftoll.valueChanged.connect(self.toggle_spatial_relation)

        # Connect the help button for spatial relations
        self.dialog.efask.clicked.connect(self.show_spatial_relations_help)

        # Populate spatial relation combobox
        self.populate_spatial_relations()

        # Initially disable geometry options
        # self.toggle_geometry_options(Qt.Unchecked)

        self.toggle_spatial_relation()

        self.toggle_geometry_options(Qt.Checked if self.dialog.efcheckgeom.isChecked() else Qt.Unchecked)

        # Populate layer lists
        self.populate_layer_lists()
        
        # Connect project signals
        QgsProject.instance().layersAdded.connect(self.populate_layer_lists)
        QgsProject.instance().layersRemoved.connect(self.populate_layer_lists)

        self.dialog.eftoll.setEnabled(True)

    def populate_spatial_relations(self):
        """Popola il combobox delle relazioni spaziali"""
        self.dialog.efspat.clear()
        
        # Add only the two required spatial relations
        self.dialog.efspat.addItem("Intersects", "intersects")
        self.dialog.efspat.addItem("Contains", "contains")
        
        # Set default to "Intersects"
        self.dialog.efspat.setCurrentIndex(0)
        
        # Add tooltips for each option
        self.dialog.efspat.setItemData(0, "Le geometrie si intersecano se hanno almeno un punto in comune (a buffer tolerance)", Qt.ToolTipRole)
        self.dialog.efspat.setItemData(1, "Il layer sorgente contiene completamente il layer di confronto (a buffer tolerance)", Qt.ToolTipRole)

    def toggle_geometry_options(self, state):
        """Attiva/disattiva le opzioni legate alla geometria"""
        enabled = state == Qt.Checked
        
        # Enable the tolerance spinner
        self.dialog.eftoll.setEnabled(enabled)
        
        # Check if we should enable spatial relation
        self.toggle_spatial_relation()

    def toggle_spatial_relation(self):
        """Attiva/disattiva la relazione spaziale in base alla tolleranza e al check geometria"""
        geometry_enabled = self.dialog.efcheckgeom.isChecked()
        
        # Get the current tolerance value
        try:
            tolerance_value = float(self.dialog.eftoll.value())
        except (ValueError, TypeError):
            tolerance_value = 0
        
        tolerance_non_zero = tolerance_value > 0
        
        # Enable spatial relation only if geometry is checked and tolerance > 0
        self.dialog.efspat.setEnabled(geometry_enabled and tolerance_non_zero)
        
        # Update tooltip based on state
        if not geometry_enabled:
            self.dialog.efspat.setToolTip("Attiva 'Confronta anche la geometria' per utilizzare questa opzione")
        elif not tolerance_non_zero:
            self.dialog.efspat.setToolTip("Imposta una tolleranza > 0 per utilizzare questa opzione")
        else:
            self.dialog.efspat.setToolTip("Seleziona il tipo di relazione spaziale da utilizzare")

    def safe_populate_layer_lists(self):
        """Wrapper around populate_layer_lists to catch exceptions"""
        try:
            self.populate_layer_lists()
        except Exception as e:
            print(f"Error updating layer lists: {str(e)}")
    
    def toggle_tolerance_field(self, state):
        """Attiva/disattiva il campo di tolleranza in base allo stato del checkbox geometria"""
        self.dialog.eftoll.setEnabled(state == Qt.Checked)

    def populate_layer_lists(self):
        """Popola le liste dei layer vettoriali in modo sicuro"""
        try:
            # Memorizza le selezioni correnti se possibile
            source_layer_id = None
            match_layer_id = None
            
            if self.dialog.eflayerdef.count() > 0 and self.dialog.eflayerdef.currentIndex() >= 0:
                current_layer = self.dialog.eflayerdef.currentData()
                if current_layer and isinstance(current_layer, QgsVectorLayer) and QgsProject.instance().mapLayer(current_layer.id()):
                    source_layer_id = current_layer.id()
            
            if self.dialog.eflayermatch.count() > 0 and self.dialog.eflayermatch.currentIndex() >= 0:
                current_layer = self.dialog.eflayermatch.currentData()
                if current_layer and isinstance(current_layer, QgsVectorLayer) and QgsProject.instance().mapLayer(current_layer.id()):
                    match_layer_id = current_layer.id()
            
            # Blocca i segnali prima di modificare i combobox
            self.dialog.eflayerdef.blockSignals(True)
            self.dialog.eflayermatch.blockSignals(True)
            
            # Pulisci le liste
            self.dialog.eflayerdef.clear()
            self.dialog.eflayermatch.clear()
            
            # Ottieni tutti i layer vettoriali dal progetto
            layers = [layer for layer in QgsProject.instance().mapLayers().values() 
                    if isinstance(layer, QgsVectorLayer) and layer.isValid()]
            
            # Popola le liste
            for layer in layers:
                self.dialog.eflayerdef.addItem(layer.name(), layer)
                self.dialog.eflayermatch.addItem(layer.name(), layer)
            
            # Ripristina le selezioni se possibile
            source_index = -1
            match_index = -1
            
            if source_layer_id:
                for i in range(self.dialog.eflayerdef.count()):
                    layer = self.dialog.eflayerdef.itemData(i)
                    if layer and layer.id() == source_layer_id:
                        source_index = i
                        break
            
            if match_layer_id:
                for i in range(self.dialog.eflayermatch.count()):
                    layer = self.dialog.eflayermatch.itemData(i)
                    if layer and layer.id() == match_layer_id:
                        match_index = i
                        break
            
            # Sblocca i segnali
            self.dialog.eflayerdef.blockSignals(False)
            self.dialog.eflayermatch.blockSignals(False)
            
            # Imposta gli indici selezionati (questo genererà i segnali per aggiornare i campi)
            if source_index >= 0:
                self.dialog.eflayerdef.setCurrentIndex(source_index)
            elif self.dialog.eflayerdef.count() > 0:
                self.dialog.eflayerdef.setCurrentIndex(0)
                
            if match_index >= 0:
                self.dialog.eflayermatch.setCurrentIndex(match_index)
            elif self.dialog.eflayermatch.count() > 0:
                self.dialog.eflayermatch.setCurrentIndex(0)
            
            # Se nessun indice valido è stato impostato, aggiorna manualmente i campi
            if source_index < 0 and self.dialog.eflayerdef.count() > 0:
                self.update_source_fields()
            if match_index < 0 and self.dialog.eflayermatch.count() > 0:
                self.update_match_fields()
                
        except Exception as e:
            print(f"Error in populate_layer_lists: {str(e)}")
            # Ensure we don't leave signals blocked in case of error
            self.dialog.eflayerdef.blockSignals(False)
            self.dialog.eflayermatch.blockSignals(False)
    
    def update_source_fields(self):
        """Aggiorna la lista dei campi del layer sorgente e le statistiche"""
        self.dialog.efjoindef.clear()
        
        layer = self.dialog.eflayerdef.currentData()
        if not layer:
            self.dialog.eflabelsource.setText("Feature nel layer sorgente: --")
            return
        
        # Update the statistics label with feature count
        feature_count = layer.featureCount()
        self.dialog.eflabelsource.setText(f"Feature nel layer sorgente: {feature_count}")
        
        # Popola i campi del layer sorgente
        for field in layer.fields():
            self.dialog.efjoindef.addItem(field.name(), field)
    
    def update_match_fields(self):
        """Aggiorna la lista dei campi del layer di confronto e le statistiche"""
        self.dialog.efjoinmatch.clear()
        
        layer = self.dialog.eflayermatch.currentData()
        if not layer:
            self.dialog.eflabelmatch.setText("Feature nel layer di confronto: --")
            return
        
        # Update the statistics label with feature count
        feature_count = layer.featureCount()
        self.dialog.eflabelmatch.setText(f"Feature nel layer di confronto: {feature_count}")
        
        # Popola i campi del layer di confronto
        for field in layer.fields():
            self.dialog.efjoinmatch.addItem(field.name(), field)
    
    def exclude_features(self):
        """Esegue l'operazione di esclusione delle feature"""
        # Ottieni i layer selezionati
        source_layer = self.dialog.eflayerdef.currentData()
        match_layer = self.dialog.eflayermatch.currentData()
        source_layer_name = self.dialog.eflayerdef.currentText()
        match_layer_name = self.dialog.eflayermatch.currentText()

        # Get the selected spatial relation
        spatial_relation = self.dialog.efspat.currentData() if self.dialog.efspat.isEnabled() else "equals"
        
        if not source_layer or not match_layer:
            QMessageBox.warning(self.dialog, "Warning", "Select both layers")
            return
        
        # Ottieni i campi di unione
        source_field_name = self.dialog.efjoindef.currentText()
        match_field_name = self.dialog.efjoinmatch.currentText()
        
        
        if not source_field_name or not match_field_name:
            QMessageBox.warning(self.dialog, "Warning", "Select join fields")
            return
        
        # Opzioni avanzate
        case_sensitive = self.dialog.efcase.isChecked()
        # trim_whitespace = self.dialog.eftrim.isChecked()

        # Verifica se i campi selezionati hanno lo stesso nome
        if source_layer.id() == match_layer.id():
            reply = QMessageBox.warning(
                self.dialog, 
                "Warning",
                "<html>"
                "You have selected the same layer as both source and comparison.<br><br>"
                f"<b>Source layer:</b> <span style='color:#0066cc; font-weight:bold; font-style:italic;'>{source_layer.name()}</span><br>"
                f"<b>Comparison layer:</b> <span style='color:#cc6600; font-weight:bold; font-style:italic;'>{match_layer.name()}</span><br><br>"
                "This means you are looking for duplicate features within the same layer.<br><br>"
                "Do you want to proceed?"
                "</html>",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # Verifica se confrontare anche le geometrie
        check_geometry = self.dialog.efcheckgeom.isChecked()
        tolerance = self.dialog.eftoll.value() if check_geometry else 0
        
        # Disabilita i controlli
        self.toggle_controls(False)
        
        # Crea e mostra il popup di elaborazione
        progress_dialog = QMessageBox(self.dialog)
        progress_dialog.setWindowTitle("Processing in progress")
        progress_dialog.setText("Analyzing features to exclude...\nDo not close QGIS.")
        progress_dialog.setStandardButtons(QMessageBox.NoButton)
        progress_dialog.setIcon(QMessageBox.Information)
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            # Crea un dizionario delle feature del layer di confronto per velocizzare l'accesso
            match_features = {}
            match_geometries = {}

            # Salva i CRS originali
            source_crs = source_layer.crs()
            match_crs = match_layer.crs()

            # Sistema di riferimento metrico (UTM 32N - Italia)
            metric_crs = QgsCoordinateReferenceSystem("EPSG:32632")

            # Flag per sapere se è necessaria la trasformazione
            need_transform_source = False
            need_transform_match = False
            transforms_created = False

            # Crea i trasformatori se necessario
            if check_geometry:
                need_transform_source = source_crs.authid() != "EPSG:32632"
                need_transform_match = match_crs.authid() != "EPSG:32632"
                
                if need_transform_source or need_transform_match:
                    source_to_metric = None
                    match_to_metric = None
                    
                    # Creazione dei trasformatori
                    if need_transform_source:
                        source_to_metric = QgsCoordinateTransform(source_crs, metric_crs, QgsProject.instance())
                    
                    if need_transform_match:
                        match_to_metric = QgsCoordinateTransform(match_crs, metric_crs, QgsProject.instance())
                    
                    transforms_created = True
                
            # Crea un indice spaziale se necessario
            spatial_index = None
            if check_geometry:
                spatial_index = QgsSpatialIndex()
                
            # Popola il dizionario e l'indice spaziale
            for feature in match_layer.getFeatures():
                match_value = feature[match_field_name]
                
                # Skip NULL values
                if match_value is None or match_value == None:
                    continue
                
                # Convert to string for consistent comparison
                match_value = str(match_value)

                # Apply whitespace and case options
                # if not trim_whitespace:
                    # match_value = match_value.strip()
                    
                if not case_sensitive:
                    match_value = match_value.lower()
                
                # Store feature by join field value
                match_features[match_value] = feature.id()
                
                # Se è richiesto il check della geometria, salva la geometria
                if check_geometry:
                    geom = feature.geometry()
                    if geom and not geom.isEmpty():
                        # Trasforma la geometria in metrico se necessario
                        if need_transform_match:
                            geom = QgsGeometry(geom)
                            geom.transform(match_to_metric)
                        
                        match_geometries[feature.id()] = geom
                        
                        # Aggiungi all'indice spaziale (per eventuali ottimizzazioni future)
                        if not need_transform_match:
                            spatial_index.addFeature(feature)
            
            # Trova le feature da escludere
            features_to_delete = []
            features_with_different_geom = []
            
            # Analizza le feature nel layer sorgente
            for source_feature in source_layer.getFeatures():
                source_value = source_feature[source_field_name]
                
                # Skip NULL values
                if source_value is None or source_value == None:
                    continue
                
                # Convert to string for consistent comparison
                source_value = str(source_value)

                # Apply whitespace and case options
                # if not trim_whitespace:
                    # source_value = source_value.strip()
                    
                if not case_sensitive:
                    source_value = source_value.lower()
                
                # Check if this feature matches one in the match layer
                if source_value in match_features:
                    match_id = match_features[source_value]
                    
                    # Add to deletion list
                    features_to_delete.append(source_feature.id())
                    
                    # If geometry checking is enabled, compare geometries
                    if check_geometry:
                        source_geom = source_feature.geometry()
                        
                        if source_geom and not source_geom.isEmpty():
                            # Trasforma la geometria in metrico se necessario
                            if need_transform_source:
                                source_geom = QgsGeometry(source_geom)
                                source_geom.transform(source_to_metric)
                            
                            match_geom = match_geometries.get(match_id)
                            
                            if match_geom:
                                is_different = True  # Default to different
                                
                                # Handle different comparison approaches based on tolerance
                                if tolerance <= 0:
                                    # When tolerance is 0, geometries must be exactly equal
                                    is_different = not source_geom.equals(match_geom)
                                else:
                                    # When tolerance > 0, use the selected spatial relation with buffer
                                    
                                    if spatial_relation == "intersects":
                                        # For Intersects: Check if geometries intersect within the tolerance
                                        # Create buffers for both geometries using tolerance
                                        source_buffer = source_geom.buffer(tolerance, 5)  # 5 segments for buffer approximation
                                        match_buffer = match_geom.buffer(tolerance, 5)
                                        
                                        # Check if either original geometry intersects the other's buffer
                                        source_intersects_match = source_geom.intersects(match_buffer)
                                        match_intersects_source = match_geom.intersects(source_buffer)
                                        
                                        # If either intersects within tolerance, they're not different
                                        is_different = not (source_intersects_match or match_intersects_source)
                                        
                                    elif spatial_relation == "contains":
                                        # For Contains: Check if source layer contains comparison layer
                                        # Create a buffer for the source geometry only
                                        source_buffer = source_geom.buffer(tolerance, 5)
                                        
                                        # Check if source (with buffer) contains match
                                        is_different = not source_buffer.contains(match_geom)
                                    
                                    else:
                                        # Default to exact equality with distance check
                                        is_different = source_geom.distance(match_geom) > tolerance
                                
                                if is_different:
                                    features_with_different_geom.append(source_feature.id())
            
            # Chiudi il popup di elaborazione
            progress_dialog.accept()
            
            # Verifica se ci sono feature da eliminare
            if not features_to_delete:
                QMessageBox.information(
                    self.dialog, 
                    "Result", 
                    "No matching records found.\n"
                    "Check the join fields and geometries."
                )
                self.toggle_controls(True)
                return
            
            # Create a dialog to show features that will be deleted
            selection_dialog = QtWidgets.QDialog(self.dialog)
            selection_dialog.setWindowTitle("Feature selection")
            selection_dialog.setMinimumWidth(1000)
            selection_dialog.setMinimumHeight(600)
            
            # Create layout
            layout = QtWidgets.QVBoxLayout()
            
            # Add info label
            info_label = QtWidgets.QLabel(f"Found {len(features_to_delete)} features to delete.")

            if check_geometry:
                features_with_equal_geom = [fid for fid in features_to_delete 
                                        if fid not in features_with_different_geom]
                info_label.setText(f"Trovate {len(features_to_delete)} feature da eliminare.\n"
                                f"Di cui {len(features_with_equal_geom)} con geometria uguale e "
                                f"{len(features_with_different_geom)} con geometria diversa.")
                
                # If we transformed coordinates, add an info label
                if need_transform_source or need_transform_match:
                    crs_info = QtWidgets.QLabel(" Le geometrie sono state temporaneamente trasformate in EPSG:32632.")
                    crs_info.setStyleSheet("color: #0066cc; font-style: italic;")
                    layout.addWidget(crs_info)

                if self.dialog.eftoll.value() > 0:
                    tolerance = self.dialog.eftoll.value()
                    relation_name = self.dialog.efspat.currentText()
                    
                    # Display information about the relation being used
                    info_text = f" Le feature sono state analizzate con la relazione spaziale '{relation_name}' e una tolleranza di {tolerance} metri."
                    
                    relation_info = QtWidgets.QLabel(info_text)
                    relation_info.setStyleSheet("color: #0066cc; font-style: italic;")
                    layout.addWidget(relation_info)

                # if self.dialog.efcase.isChecked() and self.dialog.eftrim.isChecked():
                    # caseinfo2 = QtWidgets.QLabel(" Le feature sono state analizzate rispettando le maiuscole, le minuscole e gli spazi iniziali / finali.")
                    # caseinfo2.setStyleSheet("color: #0066cc; font-style: italic;")
                    # layout.addWidget(caseinfo2)
                
                # if not self.dialog.efcase.isChecked() and self.dialog.eftrim.isChecked():
                    # caseinfo3 = QtWidgets.QLabel(" Le feature sono state analizzate rispettando gli spazi iniziali / finali.")
                    # caseinfo3.setStyleSheet("color: #0066cc; font-style: italic;")
                    # layout.addWidget(caseinfo3)

            if self.dialog.efbkp.isChecked():
                    backup_info = QtWidgets.QLabel(" Verrà eseguito il backup del layer sorgente prima dell'eliminazione delle feature, salvato nella stessa directory.")
                    backup_info.setStyleSheet("color: #0066cc; font-style: italic;")
                    layout.addWidget(backup_info)

            if self.dialog.efcase.isChecked(): # and not self.dialog.eftrim.isChecked():
                caseinfo = QtWidgets.QLabel(" Le feature sono state analizzate rispettando le maiuscole e le minuscole.")
                caseinfo.setStyleSheet("color: #0066cc; font-style: italic;")
                layout.addWidget(caseinfo)

            layout.addWidget(info_label)
            
            # Create a table widget
            table = QtWidgets.QTableWidget()
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
            table.setSortingEnabled(True)
            table.horizontalHeader().setSectionsClickable(True)
            table.horizontalHeader().setSortIndicatorShown(True)
            table.sortByColumn(1, Qt.AscendingOrder)
            table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            table.horizontalHeader().setStretchLastSection(True)
            table.resizeColumnsToContents()
            layout.addWidget(table)
            
            # Get all field names from the source layer
            field_names = [field.name() for field in source_layer.fields()]
            
            # Set up the table columns
            table.setColumnCount(len(field_names) + 2)  # +2 for FID and Geometry Status
            headers = ["FID", "Stato Geometria"] + field_names
            table.setHorizontalHeaderLabels(headers)
            
            # Fill the table with data
            table.setRowCount(len(features_to_delete))
            
            # Request features by their IDs
            request = QgsFeatureRequest().setFilterFids(features_to_delete)
            
            for i, feature in enumerate(source_layer.getFeatures(request)):
                # FID column
                fid_item = QtWidgets.QTableWidgetItem(str(feature.id()))
                table.setItem(i, 0, fid_item)
                
                # Geometry status column
                if check_geometry:
                    if feature.id() in features_with_different_geom:
                        geom_status = "Diversa"
                    else:
                        geom_status = "Uguale"
                    geom_item = QtWidgets.QTableWidgetItem(geom_status)
                    table.setItem(i, 1, geom_item)
                else:
                    table.setItem(i, 1, QtWidgets.QTableWidgetItem("N/A"))
                
                # Add attribute data
                for j, field_name in enumerate(field_names):
                    value = feature[field_name]
                    if value is not None:
                        value_str = str(value)
                    else:
                        value_str = "NULL"
                    table.setItem(i, j + 2, QtWidgets.QTableWidgetItem(value_str))
                
                # Select all rows by default
                table.selectRow(i)
            
            # Add filter controls
            filter_layout = QtWidgets.QHBoxLayout()
            # filter_layout.addStretch()
            
            # Quick selection buttons
            select_all_btn = QtWidgets.QPushButton(" Seleziona Tutti ")
            select_all_btn.setToolTip("Seleziona tutte le feature nella tabella")
            select_all_btn.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
            select_all_btn.clicked.connect(lambda: self.select_with_focus(table, lambda: table.selectAll()))
            filter_layout.addWidget(select_all_btn)
            
            select_none_btn = QtWidgets.QPushButton(" Deseleziona Tutti ")
            select_none_btn.setToolTip("Deseleziona tutte le feature nella tabella")
            select_none_btn.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
            select_none_btn.clicked.connect(lambda: self.select_with_focus(table, lambda: table.clearSelection()))
            filter_layout.addWidget(select_none_btn)
            
            if check_geometry:
                select_equal_geom_btn = QtWidgets.QPushButton(" Seleziona Geometria Uguale ")
                select_equal_geom_btn.setToolTip("Seleziona solo le feature con geometria uguale")
                select_equal_geom_btn.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
                select_equal_geom_btn.clicked.connect(lambda: self.select_with_focus(table, lambda: self.select_by_geometry(table, features_with_different_geom, False)))
                filter_layout.addWidget(select_equal_geom_btn)
                
                select_diff_geom_btn = QtWidgets.QPushButton(" Seleziona Geometria Diversa ")
                select_diff_geom_btn.setToolTip("Seleziona solo le feature con geometria diversa")
                select_diff_geom_btn.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
                select_diff_geom_btn.clicked.connect(lambda: self.select_with_focus(table, lambda: self.select_by_geometry(table, features_with_different_geom, True)))
                filter_layout.addWidget(select_diff_geom_btn)
            
            # filter_layout.addStretch()
            layout.addLayout(filter_layout)
            
            # Add action buttons
            # button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            button_layout = QtWidgets.QHBoxLayout()
            button_layout.addStretch()
            # layout.addWidget(button_box)

            # Add a button for exporting to CSV
            export_button = QtWidgets.QPushButton(" Esporta in CSV (Selezionati) ")
            export_button.setToolTip("Esporta le feature selezionate in un file CSV")
            export_button.setIcon(QtGui.QIcon(":/plugins/qutility/images/csv.png"))
            export_button.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
            export_button.clicked.connect(lambda: self.select_with_focus(table, lambda: self.export_table_to_csv(table)))
            button_layout = QtWidgets.QHBoxLayout()
            button_layout.addStretch()
            button_layout.addWidget(export_button)
            # button_layout.addSpacing(20)
            # Add temporary layer button
            temp_layer_button = QtWidgets.QPushButton(" Crea Layer Temporaneo (Selezionati) ")
            temp_layer_button.setToolTip("Crea un nuovo layer temporaneo con le feature selezionate")
            temp_layer_button.setIcon(QtGui.QIcon(":/plugins/qutility/images/processor.png"))
            temp_layer_button.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
            temp_layer_button.clicked.connect(lambda: self.select_with_focus(table, lambda: self.create_temp_layer(table, source_layer, features_with_different_geom if check_geometry else None)))
            button_layout.addWidget(temp_layer_button)
            # Connect signals
            # button_box.accepted.connect(selection_dialog.accept)
            # button_box.rejected.connect(selection_dialog.reject)
            
            delete_button = QtWidgets.QPushButton(" Elimina Feature (Selezionati) ")
            delete_button.setToolTip("Elimina definitivamente le feature selezionate dal layer")
            delete_button.setIcon(QtGui.QIcon(":/plugins/qutility/images/delete.png"))
            delete_button.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
            delete_button.clicked.connect(selection_dialog.accept)
            button_layout.addWidget(delete_button)

            cancel_button = QtWidgets.QPushButton(" Chiudi ")
            cancel_button.setToolTip("Chiude la tabella e annulla l'operazione senza eliminare alcuna feature")
            cancel_button.setIcon(QtGui.QIcon(":/plugins/qutility/images/close.png"))
            cancel_button.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
            cancel_button.clicked.connect(selection_dialog.reject)
            button_layout.addWidget(cancel_button)

            button_layout.addStretch()
            layout.addLayout(button_layout)
            selection_dialog.setLayout(layout)
            
            # Show the dialog and wait for user action
            if selection_dialog.exec_() == QtWidgets.QDialog.Accepted:
                # Get IDs of selected rows
                selected_rows = table.selectionModel().selectedRows()
                features_to_delete = []
                
                for row in selected_rows:
                    fid = int(table.item(row.row(), 0).text())
                    features_to_delete.append(fid)
                
                if not features_to_delete:
                    QMessageBox.information(
                        self.dialog,
                        "Operation cancelled",
                        "No feature selected for deletion."
                    )
                    self.toggle_controls(True)
                    return
                
                # Check if backup is requested
                if self.dialog.efbkp.isChecked():
                    progress_dialog.setText("Creating backup in progress...\nDo not close QGIS.")
                    QApplication.processEvents()
                    
                    # Create backup of the source layer
                    backup_path = self.create_layer_backup(source_layer)
                    
                    if backup_path:
                        progress_dialog.setText(f"Backup created: {backup_path}")
                    else:
                        # If backup failed, ask if user wants to continue
                        progress_dialog.accept()
                        reply = QMessageBox.question(
                            self.dialog,
                            "Backup error",
                            "Failed to create layer backup.\nProceed with deletion?",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        if reply == QMessageBox.No:
                            self.toggle_controls(True)
                            return
                
                # Create progress dialog for deletion
                progress_dialog = QMessageBox(self.dialog)
                progress_dialog.setWindowTitle("Processing in progress")
                progress_dialog.setText(f"Deleting {len(features_to_delete)} features...\nDo not close QGIS.")
                progress_dialog.setStandardButtons(QMessageBox.NoButton)
                progress_dialog.setIcon(QMessageBox.Information)
                progress_dialog.show()
                QApplication.processEvents()
            
                # Procedi con l'eliminazione
                if not source_layer.isEditable():
                    source_layer.startEditing()
                
                # Elimina le feature
                source_layer.deleteFeatures(features_to_delete)
                
                # Salva le modifiche
                source_layer.commitChanges()
                
                # Chiudi il popup di elaborazione
                progress_dialog.accept()
                
                # Mostra il messaggio di completamento
                QMessageBox.information(
                    self.dialog,
                    "Operation completed",
                    f"Deleted {len(features_to_delete)} features from layer {source_layer.name()}."
                )
            
            else:
                # User canceled
                self.toggle_controls(True)
                return
            
        except Exception as e:
            # Gestione degli errori
            QMessageBox.critical(
                self.dialog,
                "Error",
                f"An error occurred during the operation:\n{str(e)}"
            )
            
            # Annulla le modifiche al layer se necessario
            if source_layer.isEditable():
                source_layer.rollBack()
        
        finally:
            # Riabilita i controlli
            self.toggle_controls(True)

    def select_by_geometry(self, table, different_geom_features, select_different):
        """Seleziona le righe in base allo stato della geometria"""
        table.clearSelection()
        
        for i in range(table.rowCount()):
            fid = int(table.item(i, 0).text())
            is_different = fid in different_geom_features
            
            if (select_different and is_different) or (not select_different and not is_different):
                table.selectRow(i)
    
    def toggle_controls(self, enable):
        """Attiva/disattiva i controlli durante l'elaborazione"""
        self.dialog.eflayerdef.setEnabled(enable)
        self.dialog.efjoindef.setEnabled(enable)
        self.dialog.eflayermatch.setEnabled(enable)
        self.dialog.efjoinmatch.setEnabled(enable)
        self.dialog.efcheckgeom.setEnabled(enable)
        self.dialog.efbkp.setEnabled(enable)
        # Rispetta lo stato del checkbox geometria
        geom_check_enabled = enable and self.dialog.efcheckgeom.isChecked()
        self.dialog.eftoll.setEnabled(geom_check_enabled)

        self.dialog.efcase.setEnabled(enable)
        # self.dialog.eftrim.setEnabled(enable)

        # Rispetta lo stato della tolleranza
        tolerance_non_zero = self.dialog.eftoll.value() > 0
        self.dialog.efspat.setEnabled(geom_check_enabled and tolerance_non_zero)
        
        self.dialog.efrun.setEnabled(enable)

    def select_with_focus(self, table, selection_function):
        """Esegue una funzione di selezione e mantiene il focus sulla tabella"""
        # Execute the selection function
        selection_function()
        
        # Return focus to the table widget
        table.setFocus()

    def create_layer_backup(self, layer):
        """Crea un backup del layer in formato zip"""
        try:
            import zipfile
            import tempfile
            import datetime
            import shutil
            import os
            
            # Get the layer source
            source_uri = layer.source()
            
            # Check if it's a file-based layer
            if not source_uri or not os.path.exists(source_uri):
                # Handle database layers or other non-file sources
                return self.create_memory_layer_backup(layer)
            
            # For file-based layers like Shapefile
            source_dir = os.path.dirname(source_uri)
            layer_name = layer.name()
            base_filename = os.path.basename(source_uri).split('.')[0]
            
            # Create timestamp for unique backup name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            backup_filename = f"{layer_name}_backup_{timestamp}.zip"
            
            # Create a path for the backup in the same directory as the source
            backup_path = os.path.join(source_dir, backup_filename)
            
            # Find all files related to this layer (same base name, different extensions)
            related_files = []
            for file in os.listdir(source_dir):
                if file.startswith(base_filename + '.'):
                    related_files.append(os.path.join(source_dir, file))
            
            # Create zip file and add all related files
            with zipfile.ZipFile(backup_path, 'w') as zip_file:
                for file in related_files:
                    # Add file to zip with just the filename (not full path)
                    zip_file.write(file, os.path.basename(file))
            
            return backup_path
        
        except Exception as e:
            print(f"Error creating backup: {str(e)}")
            return None

    def create_memory_layer_backup(self, layer):
        """Create backup for non-file-based layers (memory, database, etc.)"""
        try:
            import os
            import datetime
            import tempfile
            from qgis.core import QgsVectorFileWriter, QgsCoordinateTransformContext # type: ignore
            
            # Create timestamp for unique backup name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            layer_name = layer.name().replace(" ", "_")
            
            # Create a temporary directory for the backup
            temp_dir = tempfile.gettempdir()
            backup_dir = os.path.join(temp_dir, "qgis_backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Define backup path
            backup_path = os.path.join(backup_dir, f"{layer_name}_backup_{timestamp}.shp")
            
            # Save layer to shapefile
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "ESRI Shapefile"
            options.fileEncoding = "UTF-8"
            
            transform_context = QgsCoordinateTransformContext()
            error = QgsVectorFileWriter.writeAsVectorFormatV2(
                layer, 
                backup_path, 
                transform_context, 
                options
            )
            
            if error[0] == QgsVectorFileWriter.NoError:
                # Make a zip of the shapefile and its related files
                return self.zip_shapefile(backup_path)
            else:
                print(f"Error saving layer: {error}")
                return None
                
        except Exception as e:
            print(f"Errore durante la creazione del backup del livello di memoria: {str(e)}")
            return None

    def zip_shapefile(self, shapefile_path):
        """Create a zip file containing a shapefile and all its associated files"""
        try:
            import zipfile
            import os
            
            # Get directory and base filename
            directory = os.path.dirname(shapefile_path)
            base_name = os.path.basename(shapefile_path).split('.')[0]
            
            # Create zip filename
            zip_path = shapefile_path.replace(".shp", ".zip")
            
            # Find all files related to this shapefile
            related_files = []
            for file in os.listdir(directory):
                if file.startswith(base_name + "."):
                    related_files.append(os.path.join(directory, file))
            
            # Create zip file
            with zipfile.ZipFile(zip_path, 'w') as zip_file:
                for file in related_files:
                    zip_file.write(file, os.path.basename(file))
            
            return zip_path
        
        except Exception as e:
            print(f"Errore durante la compressione dello shapefile: {str(e)}")
            return None
        
    def export_table_to_csv(self, table):
        """Esporta i dati della tabella in un file CSV"""
        try:
            import csv
            from PyQt5.QtWidgets import QFileDialog
            import datetime
            import os
            
            # Get source layer name for filename
            source_layer = self.dialog.eflayerdef.currentData()
            if not source_layer:
                return
                
            # Create default filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            default_filename = f"{source_layer.name()}_features_{timestamp}.csv"
            
            # Ask user for save location
            filepath, _ = QFileDialog.getSaveFileName(
                self.dialog,
                "Salva CSV",
                default_filename,
                "File CSV (*.csv)"
            )
            
            if not filepath:
                return  # User canceled
                
            # Add .csv extension if not provided
            if not filepath.lower().endswith('.csv'):
                filepath += '.csv'
            
            # Get selected rows
            selected_rows = table.selectionModel().selectedRows()
            
            # If no row is selected, export all rows
            if not selected_rows:
                selected_indices = range(table.rowCount())
            else:
                selected_indices = [row.row() for row in selected_rows]
            
            # Get headers
            headers = []
            for col in range(table.columnCount()):
                headers.append(table.horizontalHeaderItem(col).text())
            
            # Write CSV file
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header row
                writer.writerow(headers)
                
                # Write data rows
                for row_idx in selected_indices:
                    row_data = []
                    for col in range(table.columnCount()):
                        item = table.item(row_idx, col)
                        if item:
                            row_data.append(item.text())
                        else:
                            row_data.append("")
                    writer.writerow(row_data)
                
                # Add empty row as separator
                writer.writerow([])
                
                # Write summary info
                writer.writerow(["Riepilogo:"])
                writer.writerow(["Layer sorgente:", source_layer.name()])
                writer.writerow(["Feature totali:", str(len(selected_indices))])
                
                # Count geometries by status
                equal_count = 0
                different_count = 0
                
                for row_idx in selected_indices:
                    status_item = table.item(row_idx, 1)
                    if status_item:
                        if status_item.text() == "Uguale":
                            equal_count += 1
                        elif status_item.text() == "Diversa":
                            different_count += 1
                
                if "Stato Geometria" in headers:
                    writer.writerow(["Feature con geometria uguale:", str(equal_count)])
                    writer.writerow(["Feature con geometria diversa:", str(different_count)])

                writer.writerow(["Configurazione:"])
                writer.writerow(["Confronto case sensitive:", "Sì" if self.dialog.efcase.isChecked() else "No"])
                # writer.writerow(["Considera spazi iniziali/finali:", "Sì" if self.dialog.eftrim.isChecked() else "No"])
                
                # Add timestamp
                writer.writerow(["Report generato il:", datetime.datetime.now().strftime("%d/%m/%Y %H:%M")])
            
            # Show success message
            QMessageBox.information(
                self.dialog,
                "Export completed",
                f"Data successfully exported to:\n{filepath}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self.dialog,
                "Export error",
                f"An error occurred during export:\n{str(e)}"
            )

    def add_temp_layer_button(self, table, layout, source_layer, features_to_delete, features_with_different_geom):
        """Adds a button to create a temporary layer from selected features"""
        temp_layer_button = QtWidgets.QPushButton("Create Temporary Layer")
        temp_layer_button.clicked.connect(lambda: self.create_temp_layer(table, source_layer, features_with_different_geom))
        layout.addWidget(temp_layer_button)
        
        return temp_layer_button

    def create_temp_layer(self, table, source_layer, features_with_different_geom):
        """Creates a temporary layer from the selected features in the table"""
        try:
            from qgis.core import ( # type: ignore
                QgsVectorLayer, QgsFeature, QgsField, QgsGeometry, 
                QgsProject, QgsCoordinateReferenceSystem, QgsApplication
            )
            from PyQt5.QtCore import QVariant
            import datetime
            
            # Get selected rows
            selected_rows = table.selectionModel().selectedRows()
            
            # If no row is selected, use all rows
            if not selected_rows:
                selected_indices = range(table.rowCount())
            else:
                selected_indices = [row.row() for row in selected_rows]
                
            if not selected_indices:
                QMessageBox.warning(
                    self.dialog,
                    "No features selected",
                    "Please select at least one feature to create the temporary layer."
                )
                return
            
            # Get feature IDs from the table
            feature_ids = []
            for idx in selected_indices:
                fid_item = table.item(idx, 0)
                if fid_item:
                    try:
                        fid = int(fid_item.text())
                        feature_ids.append(fid)
                    except ValueError:
                        continue
            
            if not feature_ids:
                QMessageBox.warning(
                    self.dialog,
                    "Invalid data",
                    "Unable to obtain the IDs of the selected features."
                )
                return
            
            # Create a unique name for the temporary layer
            timestamp = datetime.datetime.now().strftime("%H%M")
            temp_layer_name = f"{source_layer.name()}_delete_{timestamp}"
            
            # Create a memory layer with the same geometry type and CRS
            geom_type = source_layer.geometryType()
            crs = source_layer.crs()
            
            # Map geometry types to WKB types
            geom_types = {
                0: "Point",
                1: "LineString",
                2: "Polygon",
                3: "Unknown",
                4: "MultiPoint",
                5: "MultiLineString",
                6: "MultiPolygon"
            }
            
            geom_str = geom_types.get(geom_type, "Unknown")
            uri = f"{geom_str}?crs={crs.authid()}"
            
            # Create the memory layer
            temp_layer = QgsVectorLayer(uri, temp_layer_name, "memory")
            
            # Check if layer creation was successful
            if not temp_layer.isValid():
                QMessageBox.critical(
                    self.dialog,
                    "Error",
                    "Unable to create the temporary layer."
                )
                return
            
            # Add fields from the source layer
            provider = temp_layer.dataProvider()
            provider.addAttributes(source_layer.fields().toList())
            temp_layer.updateFields()
            
            # Add a new field for geometry status
            if features_with_different_geom is not None:
                status_field = QgsField("Stato_Geom", QVariant.String, "string", 10)
                provider.addAttributes([status_field])
                temp_layer.updateFields()
                status_field_idx = temp_layer.fields().indexFromName("Stato_Geom")
            
            # Copy features from source layer
            request = QgsFeatureRequest().setFilterFids(feature_ids)
            features = source_layer.getFeatures(request)
            
            new_features = []
            for feature in features:
                new_feature = QgsFeature(temp_layer.fields())
                
                # Copy attributes
                for i in range(source_layer.fields().count()):
                    new_feature[i] = feature[i]
                
                # Set geometry status if applicable
                if features_with_different_geom is not None:
                    if feature.id() in features_with_different_geom:
                        new_feature[status_field_idx] = "Diversa"
                    else:
                        new_feature[status_field_idx] = "Uguale"
                
                # Copy geometry
                new_feature.setGeometry(feature.geometry())
                new_features.append(new_feature)
            
            # Add features to the layer
            provider.addFeatures(new_features)
            
            # Apply styles based on geometry status
            if features_with_different_geom is not None:
                self.style_temp_layer(temp_layer)
            
            # Add layer to the project
            QgsProject.instance().addMapLayer(temp_layer)
            
            # Show success message
            QMessageBox.information(
                self.dialog,
                "Layer created",
                f"Temporary layer '{temp_layer_name}' created successfully.\n\n"
                f"Contains {len(new_features)} features."
            )
            
        except Exception as e:
            QMessageBox.critical(
                self.dialog,
                "Error",
                f"An error occurred while creating the temporary layer:\n{str(e)}"
            )

    def style_temp_layer(self, layer):
        """Apply styling to the temporary layer based on geometry status"""
        try:
            from qgis.core import QgsSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer # type: ignore
            
            # Get the field index for the status field
            field_idx = layer.fields().indexFromName("Stato_Geom")
            if field_idx < 0:
                return  # Field not found
            
            # Create renderer categories
            categories = []
            
            # Equal geometry - Green
            symbol_equal = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol_equal.setColor(QtGui.QColor(0, 255, 0))  # Green
            symbol_equal.setOpacity(0.9)
            cat_equal = QgsRendererCategory("Uguale", symbol_equal, "Geometria Uguale")
            categories.append(cat_equal)
            
            # Different geometry - Red
            symbol_diff = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol_diff.setColor(QtGui.QColor(255, 0, 0))  # Red
            symbol_diff.setOpacity(0.9)
            cat_diff = QgsRendererCategory("Diversa", symbol_diff, "Geometria Diversa")
            categories.append(cat_diff)
            
            # Create and apply the renderer
            renderer = QgsCategorizedSymbolRenderer("Stato_Geom", categories)
            layer.setRenderer(renderer)
            
            # Refresh the layer
            layer.triggerRepaint()
            
        except Exception as e:
            print(f"Errore nell'applicare la stilizzazione: {str(e)}")

    def show_spatial_relations_help(self):
        """Show help popup for spatial relations"""
        # Create a new dialog for the help content
        help_dialog = QtWidgets.QDialog(self.dialog)
        help_dialog.setWindowTitle("Aiuto Relazioni Spaziali")
        help_dialog.setMinimumSize(900, 850)
        
        # Create layout
        layout = QtWidgets.QVBoxLayout()
        
        # Create a QTextBrowser to display HTML content
        text_browser = QtWidgets.QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        
        # Set the HTML content
        html_content = """
        <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">
        <html>
        <head>
            <meta name="qrichtext" content="1" />
            <style type="text/css">
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                html, body {
                    margin: 0;
                    padding: 0;
                    font-family: Arial, sans-serif;
                    font-size: 13px;
                    line-height: 1.4;
                    color: #333;
                }
                
                h2 {
                    color: #1c4587;
                    border-bottom: 1px solid #ccc;
                    padding-bottom: 8px;
                    margin: 0 0 15px 0;
                }
                
                h3 {
                    color: #6aa84f;
                    margin: 15px 0 10px 0;
                }
                
                .content-container {
                    padding: 10px;
                }
                
                .example-container {
                    display: flex;
                    margin: 0 0 30px 0;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 15px;
                    background-color: #f9f9f9;
                }
                
                .image-container {
                    flex: 1;
                    text-align: center;
                    padding: 10px;
                }
                
                .explanation {
                    flex: 2;
                    padding: 10px;
                }
                
                .result {
                    font-weight: bold;
                    margin-top: 10px;
                    padding: 8px;
                    border-radius: 4px;
                }
                
                .equal {
                    background-color: #d9ead3;
                    color: #274e13;
                }
                
                .different {
                    background-color: #f4cccc;
                    color: #990000;
                }
                
                img {
                    max-width: 100%;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 5px;
                    background-color: white;
                    display: block;
                }
                
                .tolerance-note {
                    font-style: italic;
                    color: #666;
                    margin-top: 20px;
                    padding: 10px;
                    background-color: #fff8dc;
                    border-left: 4px solid #ffeb3b;
                }

                p {
                    margin: 8px 0;
                }
                
                p:first-of-type {
                    margin-top: 0;
                }
            </style>
        </head>
        <body><div class="content-container"><h2>How Spatial Relations Work</h2>
                
        <p>Spatial relations determine how two geometries are compared when using a tolerance greater than zero.</p>
                
        <h3>Example 1: Intersecting Lines</h3>
        <div class="example-container">
            <div class="image-container">
                <img src=":/plugins/qutility/images/1.png" alt="Intersecting lines" />
            </div>
            <div class="explanation">
                <p><strong>Description:</strong> In this example, the Source line (brown) and the Comparison line (green) intersect forming an X.</p>
                
                <p><strong>With "Intersects" relation:</strong></p>
                <p>The lines intersect at one point, so with tolerance > 0, the geometries are considered equal.</p>
                <div class="result equal">Result: Geometries EQUAL</div>
                
                <p><strong>With "Contains" relation:</strong></p>
                <p>The Source line does not completely contain the Comparison line, so the geometries are considered different.</p>
                <div class="result different">Result: Geometries DIFFERENT</div>
            </div>
        </div>
                
        <h3>Example 2: Close Parallel Lines</h3>
        <div class="example-container">
            <div class="image-container">
                <img src=":/plugins/qutility/images/2.png" alt="Parallel lines" />
            </div>
            <div class="explanation">
                <p><strong>Description:</strong> In this example, the Source line (brown) and the Comparison line (green) are parallel and very close to each other.</p>
                
                <p><strong>With "Intersects" relation:</strong></p>
                <p>With sufficient tolerance (e.g., 1 meter), the buffer created around the Source line intersects the Comparison line, so the geometries are considered equal.</p>
                <div class="result equal">Result: Geometries EQUAL</div>
                
                <p><strong>With "Contains" relation:</strong></p>
                <p>With sufficient tolerance, the buffer created around the Source line can completely contain the Comparison line, so the geometries are considered equal.</p>
                <div class="result equal">Result: Geometries EQUAL</div>
            </div>
        </div>
                
        <div class="tolerance-note">
            <p><strong>Note on tolerance:</strong> Tolerance determines the size of the buffer used for comparison. A higher tolerance value allows greater flexibility in the comparison.</p>
            <p>When tolerance is set to 0, geometries must be <em>exactly</em> identical to be considered equal, regardless of the selected spatial relation.</p>
        </div>
        </div></body>
        </html>
        """
        
        text_browser.setHtml(html_content)
        layout.addWidget(text_browser)
        
        # Add a close button
        close_button = QtWidgets.QPushButton("Chiudi")
        close_button.clicked.connect(help_dialog.accept)
        close_button.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        
        # Add the button to a horizontal layout to center it
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        help_dialog.setLayout(layout)
        
        # Show the dialog
        help_dialog.exec_()