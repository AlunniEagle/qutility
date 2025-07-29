# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LayerLoader
                                 A QGIS plugin component
 Tool to load layers from files and folders with various filters
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
import zipfile
import tarfile
import glob
import datetime
from qgis.PyQt import QtGui, QtWidgets, QtCore # type: ignore
from qgis.PyQt.QtCore import Qt, QDateTime # type: ignore
from qgis.core import ( # type: ignore
    QgsProject, QgsVectorLayer, QgsRasterLayer, 
    QgsCoordinateReferenceSystem, QgsLayerTreeGroup
)
from qgis.PyQt.QtWidgets import QApplication, QMessageBox, QFileDialog # type: ignore


class LayerLoader:
    """A class to handle layer loading operations with various filters"""
    
    def __init__(self, dialog):
        """Constructor.
        
        :param dialog: The dialog instance that contains the UI elements
        """
        self.dialog = dialog
        self.current_group = None
        # Initialize the created_groups set
        self.created_groups = set()
        
        # Connect signals
        self.dialog.llsearch.clicked.connect(self.browse_source)
        self.dialog.llrun.clicked.connect(self.load_layers)
        
        self.dialog.llchecktext.stateChanged.connect(self.toggle_text_filter)
        self.dialog.llcheckdate.stateChanged.connect(self.toggle_date_filter)
        self.dialog.llcheckgeom.stateChanged.connect(self.toggle_geometry_filter)
        
        # Connect extension checkbox signals to update geometry filter availability
        self.dialog.llshp.stateChanged.connect(self.update_geometry_filter_availability)
        self.dialog.llgml.stateChanged.connect(self.update_geometry_filter_availability)
        self.dialog.llgpkg.stateChanged.connect(self.update_geometry_filter_availability)
        self.dialog.lltif.stateChanged.connect(self.update_geometry_filter_availability)
        self.dialog.llxslx.stateChanged.connect(self.update_geometry_filter_availability)
        self.dialog.lldbf.stateChanged.connect(self.update_geometry_filter_availability)
        
        # Setup datetime control
        self.dialog.lldate.setDateTime(QDateTime.currentDateTime())
        self.dialog.lldate.setCalendarPopup(True)
        self.dialog.lldate.setDisplayFormat("dd/MM/yyyy HH:mm")
        
        # Setup geometry combobox
        self.populate_geometry_combobox()
        
        # Initial state of controls
        self.toggle_text_filter(Qt.Unchecked)
        self.toggle_date_filter(Qt.Unchecked)
        self.toggle_geometry_filter(Qt.Unchecked)
        
        # Initialize geometry filter availability
        self.update_geometry_filter_availability()
    
    def update_geometry_filter_availability(self):
        """Attiva/disattiva il filtro di geometria in base ai tipi di file selezionati"""
        # Lista di estensioni che possono contenere geometria
        geom_extensions = [self.dialog.llshp, self.dialog.llgml, self.dialog.llgpkg]
        
        # Verifica se almeno una estensione che supporta geometria è selezionata
        has_geom_extension = any(ext.isChecked() for ext in geom_extensions)
        
        # Abilita/disabilita il checkbox del filtro geometria
        self.dialog.llcheckgeom.setEnabled(has_geom_extension)
        
        # Se nessuna estensione con geometria è selezionata, deseleziona il checkbox
        if not has_geom_extension and self.dialog.llcheckgeom.isChecked():
            self.dialog.llcheckgeom.setChecked(False)
            self.toggle_geometry_filter(Qt.Unchecked)

    def populate_geometry_combobox(self):
        """Popola il combobox delle geometrie"""
        self.dialog.llgeom.clear()
        self.dialog.llgeom.addItem("Qualsiasi geometria", "any")
        self.dialog.llgeom.addItem("Punto/Multipunto", "Point")
        self.dialog.llgeom.addItem("Linea/Multilinea", "Line")
        self.dialog.llgeom.addItem("Poligono/Multipoligono", "Polygon")
    
    def toggle_text_filter(self, state):
        """Attiva/disattiva il filtro per testo nel nome"""
        self.dialog.lltext.setEnabled(state == Qt.Checked)
        if state != Qt.Checked:
            self.dialog.lltext.setText("")
    
    def toggle_date_filter(self, state):
        """Attiva/disattiva il filtro per data di modifica"""
        self.dialog.lldate.setEnabled(state == Qt.Checked)
    
    def toggle_geometry_filter(self, state):
        """Attiva/disattiva il filtro per tipo di geometria"""
        self.dialog.llgeom.setEnabled(state == Qt.Checked)
    
    def browse_source(self):
        """Apre un selettore di file/directory per scegliere la sorgente"""
        # Crea un dialog personalizzato per la scelta
        dialog = QtWidgets.QDialog(self.dialog)
        dialog.setWindowTitle("Tipo di sorgente")
        
        layout = QtWidgets.QVBoxLayout()
        
        # Aggiungi radio button
        dir_radio = QtWidgets.QRadioButton("Directory")
        file_radio = QtWidgets.QRadioButton("File compresso (ZIP, TAR, ecc.)")
        dir_radio.setChecked(True)  # Default a directory
        
        layout.addWidget(dir_radio)
        layout.addWidget(file_radio)
        
        # Aggiungi pulsanti
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        
        # Mostra il dialog
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            if dir_radio.isChecked():
                # Seleziona directory
                source_path = QFileDialog.getExistingDirectory(
                    self.dialog,
                    "Seleziona una directory",
                    "",
                    QFileDialog.ShowDirsOnly
                )
            else:
                # Seleziona file
                source_path, _ = QFileDialog.getOpenFileName(
                    self.dialog,
                    "Seleziona un file compresso",
                    "",
                    "File compressi (*.zip *.tar *.rar *.7z *.gz);;Tutti i file (*.*)"
                )
                
            if source_path:
                self.dialog.llsource.setText(source_path)
    
    def check_extension(self, filepath):
        """Verifica se l'estensione del file è tra quelle selezionate"""
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext == '.shp' and self.dialog.llshp.isChecked():
            return True
        elif ext == '.gml' and self.dialog.llgml.isChecked():
            return True
        elif ext == '.gpkg' and self.dialog.llgpkg.isChecked():
            return True
        elif ext == '.tif' and self.dialog.lltif.isChecked():
            return True
        elif ext == '.xlsx' and self.dialog.llxslx.isChecked():
            return True
        elif ext == '.dbf' and self.dialog.lldbf.isChecked():
            return True
        
        return False
    
    def check_name_filter(self, filename):
        """Verifica se il nome del file soddisfa il filtro testuale"""
        if not self.dialog.llchecktext.isChecked():
            return True
        
        filter_text = self.dialog.lltext.text().strip().lower()
        if not filter_text:
            return True
        
        return filter_text in filename.lower()
    
    def check_date_filter(self, filepath):
        """Verifica se la data di modifica del file soddisfa il filtro temporale"""
        if not self.dialog.llcheckdate.isChecked():
            return True
        
        filter_date = self.dialog.lldate.dateTime().toPyDateTime()
        mod_time = os.path.getmtime(filepath)
        mod_date = datetime.datetime.fromtimestamp(mod_time)
        
        return mod_date >= filter_date
    
    def check_geometry_filter(self, layer):
        """Verifica se la geometria del layer soddisfa il filtro geometrico"""
        if not self.dialog.llcheckgeom.isChecked():
            return True
        
        # Se il layer non è vettoriale, ignora il filtro di geometria
        if not isinstance(layer, QgsVectorLayer):
            return True
        
        selected_geom = self.dialog.llgeom.currentData()
        
        # Se è selezionato "Qualsiasi geometria", accetta tutto
        if selected_geom == "any":
            return True
        
        # Altrimenti controlla il tipo di geometria
        layer_geom_type = layer.geometryType()
        
        # Mappa i tipi di geometria QGIS ai nomi delle geometrie semplificate
        if selected_geom == "Point":
            # Accetta sia Point (0) che MultiPoint (4)
            return layer_geom_type in [0, 4]
        elif selected_geom == "Line":
            # Accetta sia LineString (1) che MultiLineString (5)
            return layer_geom_type in [1, 5]
        elif selected_geom == "Polygon":
            # Accetta sia Polygon (2) che MultiPolygon (6)
            return layer_geom_type in [2, 6]
        
        return False
    
    def create_layer_group(self, folder_path):
        """Crea un gruppo di layer basato sulla struttura delle cartelle"""
        if not self.dialog.llcheckgroup.isChecked():
            return None
        
        root = QgsProject.instance().layerTreeRoot()
        folder_name = os.path.basename(folder_path)
        
        # Se il gruppo già esiste, usalo
        for child in root.children():
            if child.name() == folder_name and child.nodeType() == 0:  # 0 = gruppo
                return child
        
        # Altrimenti crea un nuovo gruppo
        group = root.addGroup(folder_name)
        
        # Add to tracking set
        self.created_groups.add(group)
        
        return group
    
    def process_files(self, directory, parent_group=None):
        """Elabora i file in una directory e carica i layer corrispondenti"""
        loaded_count = 0
        total_files = 0
        
        # Crea un gruppo per questa directory se necessario
        if self.dialog.llcheckgroup.isChecked() and not parent_group:
            parent_group = self.create_layer_group(directory)
        
        # Scansiona tutti i file nella directory
        for root, dirs, files in os.walk(directory):
            # Crea un gruppo per questa sottocartella se necessario
            current_group = parent_group
            if self.dialog.llcheckgroup.isChecked() and root != directory:
                rel_path = os.path.relpath(root, directory)
                if rel_path != ".":
                    # Crea gruppi annidati per la struttura delle cartelle
                    parts = rel_path.split(os.sep)
                    temp_group = parent_group
                    for part in parts:
                        found = False
                        if temp_group:
                            for child in temp_group.children():
                                if child.name() == part and child.nodeType() == 0:  # 0 = gruppo
                                    temp_group = child
                                    found = True
                                    break
                        
                        if not found and temp_group:
                            temp_group = temp_group.addGroup(part)
                            self.created_groups.add(temp_group)  # Track this group
                    
                    current_group = temp_group
            
            for file in files:
                total_files += 1
                file_path = os.path.join(root, file)
                
                # Controlla se il file è un archivio compresso
                if any(file.lower().endswith(ext) for ext in ['.zip', '.tar', '.rar', '.7z', '.gz']):
                    if self.dialog.llchecknest.isChecked():
                        # Elabora l'archivio compresso
                        nested_count = self.process_compressed_file(file_path, current_group)
                        loaded_count += nested_count
                    continue
                
                # Controlla i filtri
                if not self.check_extension(file_path):
                    continue
                
                if not self.check_name_filter(file):
                    continue
                
                if not self.check_date_filter(file_path):
                    continue
                
                # Carica il layer
                loaded = self.load_layer(file_path, current_group)
                if loaded:
                    loaded_count += 1
            
            # Interrompi la ricorsione se l'opzione di sottocartelle non è attiva
            if not self.dialog.llchecknest.isChecked():
                break
        
        return loaded_count, total_files
    
    def process_compressed_file(self, archive_path, parent_group=None):
        """Elabora un file compresso seguendo l'approccio dello script funzionante"""
        loaded_count = 0
        
        # Crea una directory temporanea per l'estrazione
        import tempfile
        temp_dir = tempfile.mkdtemp()
        print(f"Estrazione di {archive_path} in {temp_dir}")
        
        try:
            # Estrai l'archivio principale
            if archive_path.lower().endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            elif archive_path.lower().endswith(('.tar', '.tar.gz', '.tgz')):
                with tarfile.open(archive_path, 'r:*') as tar_ref:
                    tar_ref.extractall(temp_dir)
            else:
                # Altri formati di compressione non supportati direttamente
                return 0
            
            # Funzione per estrarre ricorsivamente tutti i ZIP annidati
            def extract_nested_zips(directory):
                for root, _, files in os.walk(directory):
                    for file in files:
                        if file.lower().endswith('.zip'):
                            zip_inner_path = os.path.join(root, file)
                            print(f"Estrazione dello ZIP annidato: {zip_inner_path}")
                            try:
                                with zipfile.ZipFile(zip_inner_path, 'r') as inner_zip:
                                    # Estrai nella stessa cartella
                                    inner_zip.extractall(root)
                                    print(f"ZIP estratto: {zip_inner_path}")
                            except Exception as e:
                                print(f"Errore nell'estrazione dello ZIP {zip_inner_path}: {str(e)}")
            
            # Estrai tutti gli ZIP annidati se l'opzione è attiva
            if self.dialog.llchecknest.isChecked():
                extract_nested_zips(temp_dir)
            
            # Crea un gruppo per questo archivio se necessario
            archive_group = parent_group
            if self.dialog.llcheckgroup.isChecked():
                archive_name = os.path.basename(archive_path)
                if parent_group:
                    archive_group = parent_group.addGroup(archive_name)
                    self.created_groups.add(archive_group)
                else:
                    root = QgsProject.instance().layerTreeRoot()
                    archive_group = root.addGroup(archive_name)
                    self.created_groups.add(archive_group)
            
            # Trova tutti i file nelle cartelle estratte
            found_files = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    # Controllo estensione
                    ext = os.path.splitext(file)[1].lower()
                    valid_extension = False
                    
                    if (ext == '.shp' and self.dialog.llshp.isChecked() or
                        ext == '.gml' and self.dialog.llgml.isChecked() or
                        ext == '.gpkg' and self.dialog.llgpkg.isChecked() or
                        ext == '.tif' and self.dialog.lltif.isChecked() or
                        ext == '.xlsx' and self.dialog.llxslx.isChecked() or
                        ext == '.dbf' and self.dialog.lldbf.isChecked()):
                        valid_extension = True
                    
                    if not valid_extension:
                        continue
                    
                    file_path = os.path.join(root, file)
                    
                    # Controllo filtri
                    if not self.check_name_filter(file):
                        continue
                    
                    if not self.check_date_filter(file_path):
                        continue
                    
                    found_files.append(file_path)
                    print(f"File trovato: {file_path}")
            
            # Carica i file trovati
            for file_path in found_files:
                layer_name = os.path.splitext(os.path.basename(file_path))[0]
                ext = os.path.splitext(file_path)[1].lower()
                
                if ext == '.shp':
                    layer = QgsVectorLayer(file_path, layer_name, "ogr")
                elif ext == '.gml':
                    layer = QgsVectorLayer(file_path, layer_name, "ogr")
                elif ext == '.gpkg':
                    layer = QgsVectorLayer(file_path, layer_name, "ogr")
                elif ext == '.tif':
                    layer = QgsRasterLayer(file_path, layer_name)
                elif ext == '.xlsx':
                    layer = QgsVectorLayer(file_path, layer_name, "ogr")
                elif ext == '.dbf':
                    layer = QgsVectorLayer(file_path, layer_name, "ogr")
                else:
                    continue
                
                # Verifica se il layer è valido
                if not layer.isValid():
                    print(f"Layer non valido: {file_path}")
                    continue
                
                # Applica il filtro di geometria
                if not self.check_geometry_filter(layer):
                    continue
                
                # Verifica se il layer ha effettivamente feature accessibili
                if isinstance(layer, QgsVectorLayer):
                    feature_count = layer.featureCount()
                    if feature_count > 0:
                        # Verifica che almeno una feature sia accessibile
                        has_features = False
                        for _ in layer.getFeatures():
                            has_features = True
                            break
                        
                        if not has_features:
                            print(f"AVVISO: Layer '{layer_name}' indica {feature_count} feature ma nessuna è accessibile")
                
                # Aggiungi il layer al progetto
                QgsProject.instance().addMapLayer(layer, False)
                
                # Aggiungi il layer al gruppo appropriato
                if archive_group:
                    archive_group.insertLayer(0, layer)
                else:
                    QgsProject.instance().layerTreeRoot().insertLayer(0, layer)
                
                loaded_count += 1
                print(f"Layer caricato con successo: {layer_name}")
            
            # Se non è stato caricato nulla, mostra un avviso
            if loaded_count == 0:
                print(f"Nessun file supportato trovato in {archive_path}")
            
        except Exception as e:
            QMessageBox.warning(
                self.dialog, 
                "Errore", 
                f"Impossibile elaborare l'archivio {archive_path}: {str(e)}"
            )
            import traceback
            traceback.print_exc()
            
        finally:
            # Pulizia della directory temporanea
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        return loaded_count

    def load_layer(self, file_path, group=None):
        """Carica un layer da un file"""
        try:
            # Create a set to track created groups
            self.created_groups = set()
            layer_name = os.path.splitext(os.path.basename(file_path))[0]
            ext = os.path.splitext(file_path)[1].lower()
            
            # Determina il tipo di layer
            if ext in ['.shp', '.gml', '.gpkg', '.dbf']:
                layer = QgsVectorLayer(file_path, layer_name, "ogr")
            elif ext in ['.tif']:
                layer = QgsRasterLayer(file_path, layer_name)
            elif ext in ['.xlsx']:
                # Approach for Excel files - try different loading methods
                # Method 1: Direct path
                layer = QgsVectorLayer(file_path, layer_name, "ogr")
                
                # Method 2: If first method fails, try with explicit sheet reference
                if not layer.isValid():
                    layer = QgsVectorLayer(f"{file_path}|layername=Sheet1", layer_name, "ogr")
                
                # Method 3: If that still fails, try using URI with the XLSX driver explicitly
                if not layer.isValid():
                    layer = QgsVectorLayer(f"XLSX:{file_path}", layer_name, "ogr")
                
                # Debug output
                if not layer.isValid():
                    print(f"Failed to load Excel file: {file_path}")
                    print(f"Error message: {layer.error().summary()}")
            else:
                return False
            
            # Verifica se il layer è valido
            if not layer.isValid():
                return False
            
            # Applica il filtro di geometria
            if not self.check_geometry_filter(layer):
                return False
            
            # Aggiungi il layer al progetto
            QgsProject.instance().addMapLayer(layer, False)
            
            # Aggiungi il layer al gruppo appropriato
            if group:
                group.insertLayer(0, layer)
            else:
                QgsProject.instance().layerTreeRoot().insertLayer(0, layer)
            
            # After loading is complete, clean up empty groups
            if self.dialog.llcheckgroup.isChecked():
                self.remove_empty_groups()

            return True
            
        except Exception as e:
            # Continua con il prossimo file in caso di errore
            print(f"Errore nel caricamento di {file_path}: {str(e)}")
            return False
        
    def clean_empty_groups(self, parent):
        """Rimuove i gruppi vuoti e ritorna True se almeno un gruppo è stato rimosso"""
        removed = False
        
        # Creiamo una copia della lista dei figli perché la modifichiamo durante l'iterazione
        children = list(parent.children())
        
        for child in children:
            # Prima pulisci ricorsivamente i figli di questo nodo
            if isinstance(child, QgsLayerTreeGroup):
                # Se abbiamo rimosso qualche gruppo nei figli, aggiorna il flag
                if self.clean_empty_groups(child):
                    removed = True
                
                # Dopo aver pulito i figli, controlla se questo gruppo è vuoto
                if len(child.children()) == 0:
                    parent.removeChildNode(child)
                    removed = True
        
        return removed

    def remove_empty_groups(self):
        """Rimuove tutti i gruppi vuoti creati durante il caricamento"""
        root = QgsProject.instance().layerTreeRoot()
        
        # Ripeti la pulizia finché non ci sono più gruppi vuoti da rimuovere
        removed = True
        while removed:
            removed = self.clean_empty_groups(root)
    
    def load_layers(self):
        """Avvia il processo di caricamento dei layer"""
        # Ottieni il percorso sorgente
        source_path = self.dialog.llsource.text().strip()
        if not source_path:
            QMessageBox.warning(self.dialog, "Attenzione", "Seleziona un percorso sorgente")
            return
        
        # Verifica se almeno un tipo di file è selezionato
        if not (self.dialog.llshp.isChecked() or 
                self.dialog.llgml.isChecked() or 
                self.dialog.llgpkg.isChecked() or 
                self.dialog.lltif.isChecked() or 
                self.dialog.llxslx.isChecked() or 
                self.dialog.lldbf.isChecked()):
            QMessageBox.warning(self.dialog, "Attenzione", "Seleziona almeno un tipo di file da caricare")
            return
        
        # Disabilita i controlli
        self.toggle_controls(False)
        
        # Mostra il popup di elaborazione
        progress_dialog = QMessageBox(self.dialog)
        progress_dialog.setWindowTitle("Elaborazione in corso")
        progress_dialog.setText("Caricamento dei layer in corso...\nNon chiudere QGIS.")
        progress_dialog.setStandardButtons(QMessageBox.NoButton)
        progress_dialog.setIcon(QMessageBox.Information)
        progress_dialog.show()
        QApplication.processEvents()
        
        loaded_count = 0
        total_files = 0
        
        try:
            # Verifica se il percorso è un file o una directory
            if os.path.isfile(source_path):
                # Se è un archivio compresso
                if any(source_path.lower().endswith(ext) for ext in ['.zip', '.tar', '.rar', '.7z', '.gz']):
                    loaded_count = self.process_compressed_file(source_path)
                    total_files = 1  # consideriamo l'archivio come un solo file
                else:
                    # Controlla i filtri
                    if self.check_extension(source_path) and self.check_name_filter(os.path.basename(source_path)) and self.check_date_filter(source_path):
                        # Carica il layer
                        if self.load_layer(source_path):
                            loaded_count = 1
                    total_files = 1
            elif os.path.isdir(source_path):
                # Elabora la directory
                loaded_count, total_files = self.process_files(source_path)
            else:
                QMessageBox.warning(
                    self.dialog, 
                    "Errore", 
                    f"Il percorso specificato non esiste: {source_path}"
                )

            # Rimuovi i gruppi vuoti se l'opzione è attiva
            if self.dialog.llcheckgroup.isChecked():
                self.remove_empty_groups()
        
        except Exception as e:
            QMessageBox.warning(
                self.dialog, 
                "Errore", 
                f"Si è verificato un errore durante il caricamento: {str(e)}"
            )
        
        finally:
            # Chiudi il popup di elaborazione
            progress_dialog.accept()
            
            # Riabilita i controlli
            self.toggle_controls(True)
            
            # Mostra il messaggio di completamento
            if loaded_count > 0:
                QMessageBox.information(
                    self.dialog, 
                    "Completato", 
                    f"Caricamento completato.\n\nLayer caricati: {loaded_count}"
                )
            else:
                QMessageBox.warning(
                    self.dialog, 
                    "Attenzione", 
                    f"Nessun layer caricato su {total_files} file trovati.\n"
                    f"Verifica i filtri applicati e i formati selezionati."
                )
    
    def toggle_controls(self, enable):
        """Attiva/disattiva i controlli durante l'elaborazione"""
        # Input di percorso
        self.dialog.llsource.setEnabled(enable)
        self.dialog.llsearch.setEnabled(enable)
        
        # Checkbox dei formati
        self.dialog.llshp.setEnabled(enable)
        self.dialog.llgml.setEnabled(enable)
        self.dialog.llgpkg.setEnabled(enable)
        self.dialog.lltif.setEnabled(enable)
        self.dialog.llxslx.setEnabled(enable)
        self.dialog.lldbf.setEnabled(enable)
        
        # Filtri
        self.dialog.llchecktext.setEnabled(enable)
        self.dialog.llcheckdate.setEnabled(enable)
        self.dialog.llcheckgeom.setEnabled(enable)
        
        # Controlli dei filtri
        text_enabled = enable and self.dialog.llchecktext.isChecked()
        date_enabled = enable and self.dialog.llcheckdate.isChecked()
        geom_enabled = enable and self.dialog.llcheckgeom.isChecked()
        
        self.dialog.lltext.setEnabled(text_enabled)
        self.dialog.lldate.setEnabled(date_enabled)
        self.dialog.llgeom.setEnabled(geom_enabled)
        
        # Opzioni aggiuntive
        self.dialog.llcheckgroup.setEnabled(enable)
        self.dialog.llchecknest.setEnabled(enable)
        
        # Pulsante di esecuzione
        self.dialog.llrun.setEnabled(enable)