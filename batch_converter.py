# -*- coding: utf-8 -*-
"""
/***************************************************************************
 BatchConverter
                                 A QGIS plugin component
 Tool to convert multiple files between different formats
                             -------------------
        begin                : 2025-05-13
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
import glob
import re
import datetime
from qgis.PyQt import QtGui, QtWidgets, QtCore # type: ignore
from qgis.PyQt.QtCore import Qt, QDateTime, QVariant # type: ignore
from qgis.core import ( # type: ignore
    QgsProject, QgsVectorLayer, QgsRasterLayer, 
    QgsCoordinateReferenceSystem, QgsVectorFileWriter,
    QgsCoordinateTransformContext, QgsFields, QgsField,
    QgsTask, QgsApplication, QgsMessageLog, QgsFeature
)
from qgis.PyQt.QtWidgets import QApplication, QMessageBox, QFileDialog, QTableWidgetItem, QHeaderView # type: ignore

class ConversionProgressDialog(QtWidgets.QDialog):
    """Finestra di dialogo che mostra il progresso della conversione"""
    
    def __init__(self, parent=None, total_files=0):
        super(ConversionProgressDialog, self).__init__(parent)
        
        self.setWindowTitle("Conversione in corso")
        self.setMinimumWidth(400)
        self.setMinimumHeight(150)
        self.setModal(True)
        
        # Layout principale
        layout = QtWidgets.QVBoxLayout(self)
        
        # Etichetta di stato
        self.status_label = QtWidgets.QLabel("Conversione in corso...")
        layout.addWidget(self.status_label)
        
        # Progress Bar
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Etichetta di conteggio
        self.count_label = QtWidgets.QLabel(f"0 / {total_files} completati")
        layout.addWidget(self.count_label)
        
        # Metti al centro dello schermo
        if parent:
            # geometria della finestra padre
            pg = parent.frameGeometry()
            # centro del parent
            cx = pg.x() + pg.width()  / 2
            cy = pg.y() + pg.height() / 2
            # centro del dialog
            dg = self.frameGeometry()
            self.move(int(cx - dg.width()  / 2),
                    int(cy - dg.height() / 2))
        else:
            # fallback: centro sullo schermo in cui è il dialog
            desktop = QApplication.desktop()
            screen_num = desktop.screenNumber(self)
            sg = desktop.availableGeometry(screen_num)
            self.move(sg.x() + (sg.width()  - self.width())  // 2,
                    sg.y() + (sg.height() - self.height()) // 2)
    
    def update_progress(self, completed, total, status=""):
        """Aggiorna la progress bar e le etichette"""
        self.progress_bar.setValue(completed)
        self.count_label.setText(f"{completed} / {total} completati")
        
        if status:
            self.status_label.setText(status)
        
        # Processa gli eventi per aggiornare l'UI
        QApplication.processEvents()


class BatchConverter:
    """A class to handle batch conversion of files between formats"""
    
    def __init__(self, dialog):
        """Constructor.
        
        :param dialog: The dialog instance that contains the UI elements
        """
        self.dialog = dialog

        # ── widgets "Nome file GeoPackage" ──────────────────────────────
        self.gpkgNameLabel = QtWidgets.QLabel("Nome file GeoPackage (opzionale):")
        self.gpkgNameLabel.setObjectName("bcpackagenamelabel")
        self.gpkgNameLine  = QtWidgets.QLineEdit()
        self.gpkgNameLine.setObjectName("bcpackagename")
        self.gpkgNameLine.setPlaceholderText("Lascia vuoto per 'output.gpkg'")

        # ── infila nella groupBox_10 (che usa un QFormLayout) ──────────
        grp = self.dialog.findChild(QtWidgets.QGroupBox, "groupBox_10")
        layout: QtWidgets.QFormLayout = grp.layout()
        layout.addRow(self.gpkgNameLabel, self.gpkgNameLine)

        # nascosti di default
        self.gpkgNameLabel.hide()
        self.gpkgNameLine.hide()

        self.supported_delimiters = {
            'Tabulazione (\\t)': '\t',
            # 'Due punti (:)': ':',
            'Spazio ( )': ' ',
            'Punto e virgola (;)': ';',
            'Virgola (,) [Default]': ','
        }
        
        # Formati supportati mappati alle estensioni corrispondenti
        self.supported_formats = {
            'ESRI Shapefile': '.shp',
            'GeoJSON': '.geojson',
            'GeoPackage': '.gpkg',
            # 'MapInfo File': '.tab',
            'KML': '.kml',
            'GML': '.gml',
            'SQLite': '.sqlite',
            'CSV': '.csv',
            'DXF': '.dxf',
            'FileGDB': '.gdb'
        }
        
        # Formati raster supportati
        self.supported_raster_formats = {
            'GeoTIFF': '.tif',
            'JPEG': '.jpg',
            'PNG': '.png',
            'ECW': '.ecw',
            'ERDAS Imagine': '.img'
        }
        
        # Opzioni dei driver per QgsVectorFileWriter
        self.driver_options = {
            'ESRI Shapefile': 'ESRI Shapefile',
            'GeoJSON': 'GeoJSON',
            'GeoPackage': 'GPKG',
            'MapInfo File': 'MapInfo File',
            'KML': 'KML',
            'GML': 'GML',
            'SQLite': 'SQLite',
            'CSV': 'CSV',
            'DXF': 'DXF',
            'FileGDB': 'FileGDB'
        }

        # Imposta le intestazioni della tabella
        self.dialog.bctable.setColumnCount(5)
        headers = ["Nome file", "Tipo", "Dimensione", "Data modifica", "Stato"]
        self.dialog.bctable.setHorizontalHeaderLabels(headers)

        # Configura il comportamento di ridimensionamento delle colonne
        header = self.dialog.bctable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)         # Nome file si espande per riempire lo spazio
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Tipo si adatta al contenuto
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Dimensione si adatta al contenuto
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Data modifica si adatta al contenuto
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Stato si adatta al contenuto

        # Attiva ordinamento
        self.dialog.bctable.setSortingEnabled(True)

        # Permetti la selezione di righe intere
        self.dialog.bctable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        # Consenti selezione multipla
        self.dialog.bctable.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.dialog.bctable.setAlternatingRowColors(True)

        # Applica stili CSS alla tabella per migliorarne l'aspetto
        self.dialog.bctable.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: #fcfcfc;
                alternate-background-color: #f2f2f2; /* Colore per righe alternate */
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                selection-background-color: #e6f0ff;
                selection-color: #000000;
            }
            
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f0f0f0;
            }
            
            QTableWidget::item:selected {
                background-color: #e6f0ff;
                color: #000000;
            }
            
            QHeaderView::section {
                background-color: #e0e0e0;
                border: 1px solid #c0c0c0;
                padding: 4px;
                font-weight: bold;
            }
            
            QHeaderView::section:hover {
                background-color: #d0d0d0;
            }
        """)
        
        # Connetti segnali
        self.dialog.bcbrowsesource.clicked.connect(self.browse_source)
        self.dialog.bcbrowsedest.clicked.connect(self.browse_destination)
        self.dialog.bcaddsources.clicked.connect(self.add_source_files)
        self.dialog.bcremovefiles.clicked.connect(self.remove_selected_files)
        self.dialog.bcclearfiles.clicked.connect(self.clear_files)
        self.dialog.bcrun.clicked.connect(self.start_conversion)
        
        # Connetti il cambio di formato
        self.dialog.bcoutputformat.currentIndexChanged.connect(self.update_ui_for_format)

        # Gestione dello stato iniziale del widget CRS
        self.init_crs_widget_state()
        
        # Connetti il cambio di stato del checkbox alla funzione di attivazione/disattivazione
        self.dialog.bctransformcrs.stateChanged.connect(self.toggle_crs_widget)

        # Connetti il cambio di stato del checkbox "unico GeoPackage"
        self.dialog.bcsinglefile.toggled.connect(self._singlefile_toggled)

        #  ── flag: la checkbox è stata forzata a FALSO dal formato CSV?
        self._crs_forced_by_csv = False

        # Popola i formati di output
        self.populate_formats()

    def _singlefile_toggled(self, checked: bool):
        # cambia la label già esistente
        if checked:
            self.dialog.bclayernamelabel.setText("Nome layer interni (opzionale):")
            self.gpkgNameLabel.show()
            self.gpkgNameLine.show()
        else:
            self.dialog.bclayernamelabel.setText("Nome file di output (opzionale):")
            self.gpkgNameLabel.hide()
            self.gpkgNameLine.hide()

    def init_crs_widget_state(self):
        """Inizializza lo stato del widget CRS in base al checkbox e imposta il CRS di default"""
        # Imposta il CRS di progetto come CRS predefinito nel widget
        project_crs = QgsProject.instance().crs()
        if project_crs.isValid():
            self.dialog.bcoutputcrs.setCrs(project_crs)
            # QgsMessageLog.logMessage(f"CRS di progetto impostato nel widget: {project_crs.authid()}", "BatchConverter", level=0)
        
        # Attiva il checkbox di trasformazione per default
        self.dialog.bctransformcrs.setChecked(True)
        
        # Aggiorna lo stato di attivazione del widget CRS in base al checkbox
        self.toggle_crs_widget(self.dialog.bctransformcrs.checkState())

    def toggle_crs_widget(self, state):
        """Attiva o disattiva il widget CRS in base allo stato del checkbox
        
        Args:
            state: Lo stato del checkbox (Qt.Checked o Qt.Unchecked)
        """
        # Attiva/disattiva il widget CRS
        self.dialog.bcoutputcrs.setEnabled(state == Qt.Checked)
        
        # if state == Qt.Checked:
            # Quando viene attivato, aggiorna il messaggio di log
            # selected_crs = self.dialog.bcoutputcrs.crs()
            # if selected_crs.isValid():
                # QgsMessageLog.logMessage(f"Widget CRS attivato con: {selected_crs.authid()}","BatchConverter",level=0)
        # else:
            # Quando viene disattivato, aggiorna il messaggio di log
            # QgsMessageLog.logMessage("Widget CRS disattivato","BatchConverter",level=0)

    def populate_formats(self):
        """Popola il combobox dei formati di output"""
        self.dialog.bcoutputformat.clear()
        
        
        for format_name in sorted(self.supported_delimiters.keys()):
            self.dialog.bcdelimiter.addItem(format_name)

        # Aggiungi formati vettoriali
        for format_name in sorted(self.supported_formats.keys()):
            self.dialog.bcoutputformat.addItem(format_name)
            
        # Aggiungi formati raster (opzionale se supporti anche i raster)
        # for format_name in sorted(self.supported_raster_formats.keys()):
        #     self.dialog.bcoutputformat.addItem(format_name)

        self.update_ui_for_format()   # Stato coerente già al primo avvio
    
    def update_ui_for_format(self):
        """Aggiorna l'interfaccia utente in base al formato selezionato"""
        current_format = self.dialog.bcoutputformat.currentText()
        
        # Abilita/disabilita opzioni specifiche in base al formato selezionato
        is_csv = current_format == 'CSV'
        
        # Se è CSV, mostra opzioni di delimitatore e codifica
        self.dialog.bcdelimiter.setEnabled(is_csv)
        self.dialog.bcdelimiterlabel.setEnabled(is_csv)

        # ─── trasformazione di coordinate ───────────────────────────
        if is_csv:
            # Se è CSV, disabilita la trasformazione CRS
            # ① CSV → disabilita e togli la spunta (solo se non l’hai già fatto)
            if self.dialog.bctransformcrs.isChecked():
                self.dialog.bctransformcrs.setChecked(False)
            self.dialog.bctransformcrs.setEnabled(False)
            self.dialog.bcoutputcrs.setEnabled(False)
            self._crs_forced_by_csv = True
            self.dialog.bcdelimiterlabel.show()
            self.dialog.bcdelimiter.show()
        else:
            # Se non è CSV, abilita la trasformazione CRS
            # ② Formati NON CSV → riabilita la checkbox
            self.dialog.bctransformcrs.setEnabled(True)
            if self._crs_forced_by_csv:
                self.dialog.bctransformcrs.setChecked(True)
            self.dialog.bcoutputcrs.setEnabled(self.dialog.bctransformcrs.isChecked())
            self._crs_forced_by_csv = False
            self.dialog.bcdelimiterlabel.hide()
            self.dialog.bcdelimiter.hide()

        # self.dialog.bctransformcrs.setEnabled(not is_csv)
        # self.dialog.bcoutputcrs.setEnabled(not is_csv)

        # Se è CSV, mostra la label e il combobox per il delimitatore
        # if is_csv:
            # self.dialog.bcdelimiterlabel.show()
            # self.dialog.bcdelimiter.show()
        # else:
            # self.dialog.bcdelimiterlabel.hide()
            # self.dialog.bcdelimiter.hide()

        #     SOLO come “Nuovo nome file (opzionale)”
        self.dialog.bclayernamelabel.setText("Nome file di output (opzionale):")
        self.dialog.bclayername.setPlaceholderText("Lascia vuoto per usare il nome originale")
        self.dialog.bclayername.setEnabled(True)

        # NEW: gestisci la checkbox “unico GeoPackage”
        is_gpkg = current_format == 'GeoPackage'
        self.dialog.bcsinglefile.setEnabled(is_gpkg)   # attiva solo se serve
        self.dialog.bcsinglefile.setChecked(is_gpkg)   # la spunti quando serve
        if is_gpkg:
            self.dialog.bcsinglefile.show()
        else:
            self.dialog.bcsinglefile.hide()

        # imposta 'Virgola' come default
        # idx = self.dialog.bcdelimiter.findData(",")   # restituisce l'indice della voce con data=","
        self.dialog.bcdelimiter.setCurrentIndex(3) # imposta la virgola come default
    
    def _output_basename(self, input_path, seq=None):
        """
        Restituisce il nome base da usare per il file di output.

        •  Se l’utente ha scritto qualcosa in bclayername ⇒ usa quel testo
        e, se seq > 0, aggiunge il suffisso _<seq>
        •  Se il campo è vuoto ⇒ usa il basename del file sorgente
        """
        custom = self.dialog.bclayername.text().strip()
        if custom:
            if seq is None or seq == 0:
                return custom
            return f"{custom}_{seq}"
        return os.path.splitext(os.path.basename(input_path))[0]

    def browse_source(self):
        """Apre un selettore di file/directory per scegliere la sorgente"""
        source_dir = QFileDialog.getExistingDirectory(
            self.dialog,
            "Seleziona directory con i file da convertire",
            "",
            QFileDialog.ShowDirsOnly
        )
        
        if source_dir:
            self.dialog.bcsourcepath.setText(source_dir)
    
    def browse_destination(self):
        """Apre un selettore di directory per scegliere la destinazione"""
        dest_dir = QFileDialog.getExistingDirectory(
            self.dialog,
            "Seleziona directory di destinazione",
            "",
            QFileDialog.ShowDirsOnly
        )
        
        if dest_dir:
            self.dialog.bcdestpath.setText(dest_dir)
    
    def add_source_files(self):
        """Aggiunge file dalla directory sorgente alla lista, con filtri"""
        source_dir = self.dialog.bcsourcepath.text()
        if not source_dir or not os.path.isdir(source_dir):
            QMessageBox.warning(self.dialog, "Errore", "Seleziona una directory sorgente valida")
            return
        
        self.clear_files()
        patterns = []
        
        # Raccogli i pattern in base ai checkbox selezionati
        if self.dialog.bcshpcheck.isChecked():
            patterns.append("*.shp")
        if self.dialog.bcgpkgcheck.isChecked():
            patterns.append("*.gpkg")
        if self.dialog.bcgeojsoncheck.isChecked():
            patterns.append("*.geojson")
        if self.dialog.bcgmlcheck.isChecked():
            patterns.append("*.gml")
        if self.dialog.bckmlcheck.isChecked():
            patterns.append("*.kml")
        # Aggiungi altri formati supportati...
        
        if not patterns:
            QMessageBox.warning(self.dialog, "Errore", "Seleziona almeno un tipo di file da convertire")
            return
        
        files_found = []
        
        # Cerca i file nelle sottocartelle se l'opzione è selezionata
        if self.dialog.bcrecursive.isChecked():
            for pattern in patterns:
                for root, dirs, files in os.walk(source_dir):
                    full_pattern = os.path.join(root, pattern)
                    files_found.extend(glob.glob(full_pattern))
        else:
            # Cerca solo nella directory principale
            for pattern in patterns:
                full_pattern = os.path.join(source_dir, pattern)
                files_found.extend(glob.glob(full_pattern))
        
        # Applica filtro per nome se specificato
        name_filter = self.dialog.bcnamefilter.text().strip().lower()
        if name_filter:
            files_found = [f for f in files_found if name_filter in os.path.basename(f).lower()]
        
        # Nessun file trovato
        if not files_found:
            QMessageBox.information(self.dialog, "Info", "Nessun file trovato con i criteri specificati")
            return
        
        # Aggiungi i file trovati alla tabella
        self.add_files_to_table(files_found)

        # Cambia il testo del pulsante per indicare che è stato premuto
        original_text = self.dialog.bcaddsources.text()
        self.dialog.bcaddsources.setText(f"Aggiornato ({len(files_found)} file)")

        # Ripristina il testo originale dopo 1,5 secondi
        QtCore.QTimer.singleShot(1500, lambda: self.dialog.bcaddsources.setText(original_text))
    
    def add_files_to_table(self, file_paths):
        """Aggiunge i file trovati alla tabella, mostrando solo il nome file e non il percorso completo"""
        for file_path in file_paths:
            # Controlla se il file è già nella tabella (controlla il percorso completo)
            file_exists = False
            for row in range(self.dialog.bctable.rowCount()):
                # Usa un attributo personalizzato per memorizzare il percorso completo
                item = self.dialog.bctable.item(row, 0)
                if item and item.data(Qt.UserRole) == file_path:
                    file_exists = True
                    break
            
            if file_exists:
                continue
            
            # Estrai solo il nome del file dal percorso completo
            file_name = os.path.basename(file_path)
            
            # Crea una nuova riga
            row_position = self.dialog.bctable.rowCount()
            self.dialog.bctable.insertRow(row_position)
            
            # Crea l'item per il nome del file con tooltip
            name_item = QTableWidgetItem(file_name)
            name_item.setData(Qt.UserRole, file_path)  # Memorizza il percorso completo
            name_item.setToolTip(file_path)  # Aggiunge tooltip con percorso completo
            self.dialog.bctable.setItem(row_position, 0, name_item)
            
            # Determina il tipo (vector/raster)
            file_ext = os.path.splitext(file_path)[1].lower()
            file_type = "Vector" if file_ext in ['.shp', '.gpkg', '.geojson', '.gml', '.kml'] else "Raster"
            type_item = QTableWidgetItem(file_type)
            type_item.setToolTip(f"Tipo di file: {file_type}")
            self.dialog.bctable.setItem(row_position, 1, type_item)
            
            # Dimensione del file
            file_size = os.path.getsize(file_path)
            size_str = self.format_size(file_size)
            size_item = QTableWidgetItem(size_str)
            size_item.setData(Qt.UserRole, file_size)  # Memorizza la dimensione in byte per ordinamento
            size_item.setToolTip(f"Dimensione: {size_str} ({file_size} bytes)")
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # Allinea a destra
            self.dialog.bctable.setItem(row_position, 2, size_item)
            
            # Data di modifica
            mod_time = os.path.getmtime(file_path)
            mod_date = datetime.datetime.fromtimestamp(mod_time)
            date_str = mod_date.strftime("%Y-%m-%d %H:%M")
            date_item = QTableWidgetItem(date_str)
            date_item.setData(Qt.UserRole, mod_time)  # Memorizza il timestamp per ordinamento
            date_item.setToolTip(f"Ultima modifica: {date_str}")
            self.dialog.bctable.setItem(row_position, 3, date_item)
            
            # Stato iniziale
            self.update_file_status(row_position, "In attesa")
        
        # Aggiorna il conteggio dei file
        self.update_file_count()

    # Nuovo metodo per aggiornare lo stato con colori
    def update_file_status(self, row, status, error_message=None):
        """
        Aggiorna lo stato di un file nella tabella con colori appropriati
        
        Args:
            row: Indice di riga nella tabella
            status: Stato da impostare ("In attesa", "In elaborazione", "Completato", "Errore")
            error_message: Messaggio di errore opzionale per tooltip
        """
        status_item = QTableWidgetItem(status)
        
        # Imposta il colore in base allo stato
        if status == "Completato":
            status_item.setForeground(QtGui.QColor(0, 128, 0))  # Verde
            status_item.setToolTip("Conversione completata con successo")
            # Opzionale: aggiungi un'icona di successo
            # status_item.setIcon(QtGui.QIcon(":/plugins/qutility/images/success.png"))
        elif status == "Errore":
            status_item.setForeground(QtGui.QColor(255, 0, 0))  # Rosso
            tooltip = "Si è verificato un errore durante la conversione"
            if error_message:
                tooltip += f": {error_message}"
            status_item.setToolTip(tooltip)
            # Opzionale: aggiungi un'icona di errore
            # status_item.setIcon(QtGui.QIcon(":/plugins/qutility/images/error.png"))
        elif status == "In elaborazione":
            status_item.setForeground(QtGui.QColor(0, 0, 255))  # Blu
            status_item.setToolTip("Conversione in corso...")
            # Opzionale: aggiungi un'icona di elaborazione
            # status_item.setIcon(QtGui.QIcon(":/plugins/qutility/images/processing.png"))
        else:  # "In attesa" o altro
            status_item.setForeground(QtGui.QColor(128, 128, 128))  # Grigio
            status_item.setToolTip("In attesa di conversione")
        
        # Centra il testo nella cella
        status_item.setTextAlignment(Qt.AlignCenter)
        
        # Imposta l'item nella tabella
        self.dialog.bctable.setItem(row, 4, status_item)
    
    def format_size(self, size_bytes):
        """Formatta la dimensione del file in unità leggibili"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def remove_selected_files(self):
        """Rimuove i file selezionati dalla tabella"""
        selected_rows = []
        for item in self.dialog.bctable.selectedItems():
            row = item.row()
            if row not in selected_rows:
                selected_rows.append(row)
        
        # Rimuovi le righe in ordine decrescente
        for row in sorted(selected_rows, reverse=True):
            self.dialog.bctable.removeRow(row)
        
        # Aggiorna il conteggio dei file
        self.update_file_count()
    
    def clear_files(self):
        """Cancella tutti i file dalla tabella"""
        self.dialog.bctable.setRowCount(0)
        self.update_file_count()
    
    def update_file_count(self):
        """Aggiorna l'etichetta del conteggio dei file"""
        count = self.dialog.bctable.rowCount()
        self.dialog.bcfilecount.setText(f"File da convertire: {count}")
    
    
    def start_conversion(self):
        """Avvia il processo di conversione"""
        # Controlla se ci sono file da convertire
        if self.dialog.bctable.rowCount() == 0:
            QMessageBox.warning(self.dialog, "Errore", "Aggiungi file da convertire")
            return
        
        # Controlla il percorso di destinazione
        dest_dir = self.dialog.bcdestpath.text()
        if not dest_dir or not os.path.isdir(dest_dir):
            QMessageBox.warning(self.dialog, "Errore", "Seleziona una directory di destinazione valida")
            return
        
        # Ottieni il formato di output
        output_format = self.dialog.bcoutputformat.currentText()
        if not output_format:
            QMessageBox.warning(self.dialog, "Errore", "Seleziona un formato di output")
            return
        
        # Flag per unire tutto in un unico GeoPackage
        use_single_geopackage = output_format == 'GeoPackage' and self.dialog.bcsinglefile.isChecked()
        
        # Chiedi conferma
        file_count = self.dialog.bctable.rowCount()
        message = f"Stai per convertire {file_count} file in formato {output_format}.\n\n"
        custom_name = self.dialog.bclayername.text().strip()
        if file_count > 1 and custom_name:
            message += (f"Verranno creati i file:\n"
                        f"  {custom_name}, {custom_name}_1, {custom_name}_2 …\n"
                        "Procedere?\n\n")
        message += f"I file convertiti saranno salvati in: {dest_dir}\n\n"
        if output_format == 'DXF':
            message += ("ATTENZIONE: il formato DXF non supporta campi attributo; "
                        "i valori dei campi saranno persi.\n\n")
        if output_format == 'MapInfo File':
            message += ("ATTENZIONE: il formato TAB supporta solo campi interi, "
                        "real e testo. Gli altri campi saranno convertiti in stringa "
                        "o omessi.\n\n")
        
        if use_single_geopackage:
            pkg_base = self.gpkgNameLine.text().strip() or "output"
            message += f"Tutti i layer saranno uniti in «{pkg_base}.gpkg».\n"
            
        
        message += "\nVuoi procedere con la conversione?"
        
        reply = QMessageBox.question(
            self.dialog, 
            "Conferma", 
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # Disabilita i controlli durante la conversione
        self.toggle_controls(False)

        # RESET degli stati
        for row in range(self.dialog.bctable.rowCount()):
            self.update_file_status(row, "In attesa")
        
        # Crea e mostra la finestra di progresso
        progress_dialog = ConversionProgressDialog(self.dialog, file_count)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setWindowFlags(progress_dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        progress_dialog.show()
        
        success_count = 0
        error_count = 0
        
        # Per un GeoPackage singolo, definisci il percorso del file
        single_gpkg_path = None
        
        try:
            # Importa modulo processing
            import processing # type: ignore
            from processing.core.Processing import Processing # type: ignore
            
            # Assicurati che Processing sia inizializzato
            Processing.initialize()
            
            if use_single_geopackage:
                pkg_base = self.gpkgNameLine.text().strip() or "output"
                single_gpkg_path = os.path.join(dest_dir, f"{pkg_base}.gpkg").replace("\\", "/")
                
                # Se il file esiste, chiedi conferma per sovrascriverlo
                if os.path.exists(single_gpkg_path):
                    reply = QMessageBox.question(
                        self.dialog, 
                        "File esistente", 
                        f"Il file {single_gpkg_path} esiste già.\nSovrascriverlo?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        # Cancella il file esistente
                        try:
                            os.remove(single_gpkg_path)
                        except Exception as e:
                            QMessageBox.warning(
                                self.dialog, 
                                "Errore", 
                                f"Impossibile eliminare il file esistente: {str(e)}"
                            )
                            self.toggle_controls(True)
                            progress_dialog.close()
                            return
                    else:
                        # Utente ha annullato
                        self.toggle_controls(True)
                        progress_dialog.close()
                        return
            
            # Processa tutti i file nella tabella
            for row in range(self.dialog.bctable.rowCount()):
                # Aggiorna l'UI e la progress bar
                progress_dialog.update_progress(
                    success_count + error_count, 
                    file_count, 
                    f"Elaborazione di {self.dialog.bctable.item(row, 0).text()}\n\nNon chiudere QGIS..."
                )
                QApplication.processEvents()
                
                # Ottieni il percorso del file
                item = self.dialog.bctable.item(row, 0)
                file_path = item.data(Qt.UserRole)  # Recupera il percorso completo
                file_type = self.dialog.bctable.item(row, 1).text()
                
                # Aggiorna lo stato
                self.update_file_status(row, "In elaborazione")
                QApplication.processEvents()
                
                try:
                    # Determina il nome di output
                    # file_name = os.path.basename(file_path)
                    # base_name = os.path.splitext(file_name)[0]
                    
                    # Pulisci il nome base per usarlo come nome layer
                    clean_base_name = re.sub(r'[^a-zA-Z0-9_]', '_',
                         self._output_basename(file_path, row))


                    
                    if use_single_geopackage:
                        # Determina il nome del layer
                        layer_name = clean_base_name
                        
                        # Se l'utente ha specificato un nome di layer, usalo come prefisso
                        # if layer_name:
                            # Se ci sono più file, aggiungi un suffisso per distinguerli
                            # if file_count > 1:
                                # layer_name = f"{layer_name}_{row+1}"
                        # else:
                            # Altrimenti usa il nome del file
                            # layer_name = clean_base_name
                        
                        try:
                            # APPROCCIO IBRIDO: Usa algoritmi di processing e subprocess
                            
                            # Carica il layer vettoriale
                            vector_layer = QgsVectorLayer(file_path, layer_name, "ogr")
                            
                            if not vector_layer.isValid():
                                raise Exception(f"Layer non valido: {file_path}")
                            
                            # Determina se è il primo layer o un layer successivo
                            is_first_layer = row == 0 or not os.path.exists(single_gpkg_path)
                            
                            # Se è richiesta una riproiezione, eseguila prima
                            if self.dialog.bctransformcrs.isChecked() and self.dialog.bcoutputcrs.crs().isValid():
                                # Crea un layer temporaneo riproiettato
                                reprojected_layer_path = 'memory:'
                                
                                # Parametri per la riproiezione
                                params = {
                                    'INPUT': vector_layer,
                                    'TARGET_CRS': self.dialog.bcoutputcrs.crs(),
                                    'OUTPUT': reprojected_layer_path
                                }
                                
                                # Esegui la riproiezione
                                result = processing.run("native:reprojectlayer", params)
                                input_layer = result['OUTPUT']
                            else:
                                # Usa il layer originale
                                input_layer = vector_layer
                            
                            # Per il primo layer, crea un nuovo file GPKG
                            if is_first_layer:
                                # Parametri per il salvataggio
                                params = {
                                    'INPUT': input_layer,
                                    'OUTPUT': single_gpkg_path,
                                    'LAYER_NAME': layer_name
                                }
                                
                                # Esegui il salvataggio
                                processing.run("native:savefeatures", params)
                            else:
                                # Per i layer successivi, usa ogr2ogr tramite subprocess
                                # poiché supporta meglio l'aggiunta di layer a un GPKG esistente
                                import subprocess
                                
                                # Salva temporaneamente il layer in un GeoJSON
                                temp_geojson = os.path.join(
                                    dest_dir, 
                                    f"temp_{clean_base_name}.geojson"
                                ).replace("\\", "/")
                                
                                # Parametri per il salvataggio temporaneo
                                params = {
                                    'INPUT': input_layer,
                                    'OUTPUT': temp_geojson
                                }
                                
                                # Salva temporaneamente come GeoJSON
                                processing.run("native:savefeatures", params)
                                
                                try:
                                    # Costruisci il comando ogr2ogr per aggiungere il layer al GPKG
                                    command = ["ogr2ogr", "-append", "-f", "GPKG"]
                                    
                                    # Nome del layer di output
                                    command.extend(["-nln", layer_name])
                                    
                                    # Se è richiesta una riproiezione
                                    if self.dialog.bctransformcrs.isChecked() and self.dialog.bcoutputcrs.crs().isValid():
                                        srid = self.dialog.bcoutputcrs.crs().postgisSrid()
                                        command.extend(["-t_srs", f"EPSG:{srid}"])
                                    
                                    # Destinazione e sorgente
                                    command.append(single_gpkg_path)  # Destinazione
                                    command.append(temp_geojson)      # Sorgente
                                    
                                    # Esecuzione del comando
                                    QgsMessageLog.logMessage(
                                        f"Esecuzione comando: {' '.join(command)}", 
                                        "BatchConverter", 
                                        level=0
                                    )
                                    
                                    # Esegui il comando
                                    process = subprocess.Popen(
                                        command,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        universal_newlines=True
                                    )
                                    
                                    # Attendi il completamento e ottieni l'output
                                    stdout, stderr = process.communicate()
                                    
                                    # Verifica se ci sono errori
                                    if process.returncode != 0:
                                        error_message = stderr.strip()
                                        QgsMessageLog.logMessage(
                                            f"Errore ogr2ogr: {error_message}", 
                                            "BatchConverter", 
                                            level=2
                                        )
                                        raise Exception(f"Errore ogr2ogr: {error_message}")
                                    
                                    # Rimuovi il file temporaneo
                                    os.remove(temp_geojson)
                                    
                                except Exception as e:
                                    QgsMessageLog.logMessage(
                                        f"Errore nell'aggiunta del layer: {str(e)}", 
                                        "BatchConverter", 
                                        level=2
                                    )
                                    
                                    # Piano B: provare con un approccio alternativo
                                    # Salviamo il layer con un nome diverso
                                    alternate_gpkg = os.path.join(
                                        dest_dir, 
                                        f"{clean_base_name}.gpkg"
                                    ).replace("\\", "/")
                                    
                                    # Parametri per il salvataggio
                                    params = {
                                        'INPUT': input_layer,
                                        'OUTPUT': alternate_gpkg
                                    }
                                    
                                    # Esegui il salvataggio
                                    processing.run("native:savefeatures", params)
                                    
                                    # Informa l'utente
                                    QgsMessageLog.logMessage(
                                        f"Layer salvato come file separato: {alternate_gpkg}", 
                                        "BatchConverter", 
                                        level=1
                                    )
                                    
                                    # Rimuovi il file temporaneo se esiste
                                    if os.path.exists(temp_geojson):
                                        os.remove(temp_geojson)
                                    
                                    # Interrompi con errore
                                    raise Exception("Impossibile aggiungere il layer al GeoPackage")
                            
                            # Verifica che il file esista
                            if os.path.exists(single_gpkg_path):
                                self.update_file_status(row, "Completato")
                                success_count += 1
                            else:
                                self.update_file_status(row, "Errore", "File non creato")
                                error_count += 1
                        
                        except Exception as e:
                            # Errore in processing
                            QgsMessageLog.logMessage(
                                f"Errore in processing: {str(e)}", 
                                "BatchConverter", 
                                level=2
                            )
                            self.update_file_status(row, "Errore", str(e))
                            error_count += 1
                    
                    else:
                        # Conversione normale (un file per ogni input)
                        file_extension = self.supported_formats.get(output_format, '.unknown')
                        output_file = os.path.join(dest_dir, f"{clean_base_name}{file_extension}").replace("\\", "/")
                        
                        # Per file separati, usa la funzione di conversione normale
                        success = self.convert_single_file(file_path, output_file, output_format)
                        
                        if success:
                            self.update_file_status(row, "Completato")
                            success_count += 1
                        else:
                            self.update_file_status(row, "Errore", "Conversione fallita")
                            error_count += 1
                    
                    # Aggiorna la progress bar
                    progress_dialog.update_progress(
                        success_count + error_count, 
                        file_count
                    )
                
                except Exception as e:
                    # Gestione degli errori
                    error_message = str(e)
                    self.update_file_status(row, "Errore", error_message)
                    error_count += 1
                    QgsMessageLog.logMessage(
                        f"Errore nella conversione di {file_path}: {error_message}", 
                        "BatchConverter", 
                        level=2
                    )
                    
                    # Aggiorna la progress bar
                    progress_dialog.update_progress(
                        success_count + error_count, 
                        file_count, 
                        f"Errore: {error_message}"
                    )
            
            # Chiudi la finestra di progresso
            progress_dialog.close()
            
            # Mostra il messaggio di completamento
            completion_message = f"Conversione completata.\n\n"
            completion_message += f"File convertiti con successo: {success_count}\n"
            completion_message += f"File con errori: {error_count}"
            
            if use_single_geopackage and success_count > 0:
                completion_message += f"\n\nTutti i layer sono stati salvati nel file:\n{single_gpkg_path}"
            
            QMessageBox.information(self.dialog, "Completato", completion_message)
        
        except Exception as e:
            # Gestione degli errori generali
            QgsMessageLog.logMessage(
                f"Errore generale nella conversione: {str(e)}", 
                "BatchConverter", 
                level=2
            )
            QMessageBox.critical(
                self.dialog, 
                "Errore", 
                f"Si è verificato un errore durante la conversione: {str(e)}"
            )
            
            # Chiudi la finestra di progresso in caso di errore
            progress_dialog.close()
        
        finally:
            # Riabilita sempre i controlli alla fine
            self.toggle_controls(True)
            
            # Riattiva/disattiva correttamente il widget CRS in base allo stato del checkbox
            self.toggle_crs_widget(self.dialog.bctransformcrs.checkState())

    # Metodo helper per la conversione di un singolo file
    def convert_single_file(self, input_file, output_file, output_format):
        """Converte un singolo file nel formato specificato"""
        try:
            # Handle MapInfo File format specially
            if output_format == 'MapInfo File':
                return self.convert_to_mapinfo(input_file, output_file)
            
            # For other formats, use the standard approach
            if self.dialog.bctransformcrs.isChecked() and self.dialog.bcoutputcrs.crs().isValid():
                import processing # type: ignore
                
                # Parametri per l'algoritmo di riproiezione
                params = {
                    'INPUT': input_file,
                    'TARGET_CRS': self.dialog.bcoutputcrs.crs(),
                    'OUTPUT': output_file
                }
                
                # Esegui l'algoritmo
                processing.run("native:reprojectlayer", params)
            else:
                # Altrimenti usa l'algoritmo di conversione formato
                import processing # type: ignore
                
                # Parametri per l'algoritmo di conversione
                params = {
                    'INPUT': input_file,
                    'OUTPUT': output_file
                }

                # ⇢ SE l’output è CSV aggiungi l’opzione SEPARATOR
                if output_format.upper() == 'CSV':
                    label = self.dialog.bcdelimiter.currentText()
                    char  = self.supported_delimiters.get(label, ',')        # "," ";" "\t" …
                    sep_map = {
                        ',': 'COMMA',
                        ';': 'SEMICOLON',
                        '\t': 'TAB',
                        ' ': 'SPACE',
                        ':': 'COLON',
                    }
                    sep = sep_map.get(char, 'COMMA')
                    params['LAYER_OPTIONS'] = f'SEPARATOR={sep}'
                    print(f"Separator: {sep}")
                
                # Esegui l'algoritmo
                processing.run("native:savefeatures", params)
            
            # Verifica che il file esista
            return os.path.exists(output_file)
        
        except Exception as e:
            err_msg = str(e)

            # → Se è il warning DXF previsto, considera la conversione riuscita
            if output_format == 'DXF' and \
            "DXF layer does not support arbitrary field creation" in err_msg:
                QgsMessageLog.logMessage(
                    f"DXF: attributi ignorati come previsto per {input_file}", 
                    "BatchConverter", level=1
                )
                return True   # <-- SUCCESSO!

            # Altri errori: gestiscili normalmente
            QgsMessageLog.logMessage(
                f"Errore nella conversione di {input_file}: {err_msg}", 
                "BatchConverter", level=2
            )
            return False
    
    def convert_vector_file(self, input_file, output_file, driver_name, layer_options, dataset_options):
        """Converte un file vettoriale con approccio semplificato per la riproiezione"""
        # Carica il layer
        input_layer = QgsVectorLayer(input_file, "temp_layer", "ogr")
        if not input_layer.isValid():
            QgsMessageLog.logMessage(
                f"Layer non valido: {input_file}", 
                "BatchConverter", 
                level=2
            )
            return False
        
        # Normalizza il percorso di output (sostituisci backslash con slash)
        output_file = output_file.replace("\\", "/")
        
        # Crea la directory di output se non esiste
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        try:
            # Se è richiesta una riproiezione
            if self.dialog.bctransformcrs.isChecked():
                # Ottieni il CRS di destinazione
                dest_crs = self.dialog.bcoutputcrs.crs()
                
                if dest_crs and dest_crs.isValid():
                    # Log
                    QgsMessageLog.logMessage(
                        f"Riproiezione a {dest_crs.authid()} richiesta", 
                        "BatchConverter", 
                        level=0
                    )
                    
                    # 1. Crea un layer temporaneo con la riproiezione
                    # Il modo più semplice è usare processing.run
                    from processing.core.Processing import Processing # type: ignore
                    from processing.tools import general # type: ignore
                    
                    # Inizializza processing se necessario
                    if not hasattr(general, 'run'):
                        Processing.initialize()
                    
                    # Usa l'algoritmo di riproiezione
                    params = {
                        'INPUT': input_file,
                        'TARGET_CRS': dest_crs,
                        'OUTPUT': 'memory:'
                    }
                    
                    # Esegui l'algoritmo
                    result = general.run("native:reprojectlayer", params)
                    
                    if 'OUTPUT' in result:
                        # Ottieni il layer riproiettato
                        reprojected_layer = result['OUTPUT']
                        
                        # Ora salva il layer riproiettato nel formato richiesto
                        options = QgsVectorFileWriter.SaveVectorOptions()
                        options.driverName = driver_name
                        options.layerOptions = layer_options
                        options.datasetOptions = dataset_options

                        if driver_name == 'DXF':
                            try:
                                # QGIS ≥ 3.34 → basta svuotare la lista degli attributi
                                options.attributes = []
                                # QGIS 3.28‑3.32 → proprietà sperimentale
                                options.skipAttributeCreation = True
                            except AttributeError:
                                pass

                        # Se il driver è MapInfo File, usa il layer temporaneo 
                        # per evitare problemi di compatibilità
                        if driver_name == 'MapInfo File':
                            reprojected_layer = self._sanitize_for_tab(reprojected_layer)

                        
                        # Usa writeAsVectorFormat con il layer riproiettato
                        error_code = QgsVectorFileWriter.writeAsVectorFormat(
                            reprojected_layer,
                            output_file,
                            options
                        )
                        
                        # Verifica l'errore (potrebbe essere un tuple o un int a seconda della versione)
                        if isinstance(error_code, tuple):
                            error, error_message = error_code
                            if error != QgsVectorFileWriter.NoError:
                                QgsMessageLog.logMessage(
                                    f"Errore nella scrittura: {error_message}", 
                                    "BatchConverter", 
                                    level=2
                                )
                                return False
                        elif error_code != QgsVectorFileWriter.NoError:
                            QgsMessageLog.logMessage(
                                f"Errore nella scrittura (codice: {error_code})", 
                                "BatchConverter", 
                                level=2
                            )
                            return False
                        
                        QgsMessageLog.logMessage(
                            f"Riproiezione e salvataggio completati con successo", 
                            "BatchConverter", 
                            level=0
                        )
                        return True
                    else:
                        QgsMessageLog.logMessage(
                            "Errore nell'algoritmo di riproiezione", 
                            "BatchConverter", 
                            level=2
                        )
                        # Continua con il metodo standard come fallback
                else:
                    QgsMessageLog.logMessage(
                        "CRS di destinazione non valido", 
                        "BatchConverter", 
                        level=2
                    )
            
            # Metodo standard senza riproiezione o come fallback
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = driver_name
            options.layerOptions = layer_options
            options.datasetOptions = dataset_options

            if driver_name == 'DXF':
                try:
                    # QGIS ≥ 3.34 → basta svuotare la lista degli attributi
                    options.attributes = []
                    # QGIS 3.28‑3.32 → proprietà sperimentale
                    options.skipAttributeCreation = True
                except AttributeError:
                    pass

            # Se il driver è MapInfo File, usa il layer temporaneo 
            # per evitare problemi di compatibilità
            if driver_name == 'MapInfo File':
                input_layer = self._sanitize_for_tab(input_layer)
            
            # Usa writeAsVectorFormat in modo compatibile con la tua versione
            error_code = QgsVectorFileWriter.writeAsVectorFormat(
                input_layer,
                output_file,
                options
            )
            
            # Verifica l'errore
            if isinstance(error_code, tuple):
                error, error_message = error_code
                if error != QgsVectorFileWriter.NoError:
                    QgsMessageLog.logMessage(
                        f"Errore nella scrittura: {error_message}", 
                        "BatchConverter", 
                        level=2
                    )
                    return False
            elif error_code != QgsVectorFileWriter.NoError:
                QgsMessageLog.logMessage(
                    f"Errore nella scrittura (codice: {error_code})", 
                    "BatchConverter", 
                    level=2
                )
                return False
            
            return True
        
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Errore durante la conversione: {str(e)}", 
                "BatchConverter", 
                level=2
            )
            
            # Fallback estremo senza opzioni, solo il formato di base
            try:
                QgsMessageLog.logMessage(
                    "Tentativo con metodo base senza opzioni", 
                    "BatchConverter", 
                    level=0
                )
                
                if driver_name == 'DXF':
                    try:
                        # QGIS ≥ 3.34 → basta svuotare la lista degli attributi
                        options.attributes = []
                        # QGIS 3.28‑3.32 → proprietà sperimentale
                        options.skipAttributeCreation = True
                    except AttributeError:
                        pass

                # Se il driver è MapInfo File, usa il layer temporaneo 
                # per evitare problemi di compatibilità
                if driver_name == 'MapInfo File':
                    input_layer = self._sanitize_for_tab(input_layer)

                # Il metodo più semplice possibile
                result = QgsVectorFileWriter.writeAsVectorFormat(
                    input_layer, 
                    output_file, 
                    "UTF-8"
                )
                
                return isinstance(result, tuple) and result[0] == QgsVectorFileWriter.NoError or result == QgsVectorFileWriter.NoError
            
            except Exception as e2:
                QgsMessageLog.logMessage(
                    f"Errore nel fallback base: {str(e2)}", 
                    "BatchConverter", 
                    level=2
                )
                return False
    
    def convert_raster_file(self, input_file, output_file, driver_name):
        """Converte un file raster (implementazione base)"""
        # Potresti usare GDAL direttamente o le classi di QGIS per la conversione raster
        # Questa è una implementazione semplificata
        
        # Carica il layer raster
        layer = QgsRasterLayer(input_file, "temp_raster")
        if not layer.isValid():
            QgsMessageLog.logMessage(
                f"Layer raster non valido: {input_file}", 
                "BatchConverter", 
                level=2
            )
            return False
        
        # Per la conversione dei raster, dovresti utilizzare GDAL o QgsRasterFileWriter
        # Qui è solo un placeholder
        QgsMessageLog.logMessage(
            f"La conversione raster non è ancora implementata per: {input_file}", 
            "BatchConverter", 
            level=1
        )
        return False  # Implementazione da completare
    
    def _sanitize_for_tab(self, src_layer: QgsVectorLayer) -> QgsVectorLayer:
        """
        Restituisce un layer in memoria con uno schema compatibile con
        il driver "MapInfo File".

        •  Consente solo Integer / Real / String
        •  Se il campo è Double → lunghezza 30, precisione 15
        •  Per valori molto grandi (>10^15), converte in String(254)
        •  Tutti gli altri tipi (Date, Bool, ecc.) diventano String(254)
        """
        # Log per debug
        QgsMessageLog.logMessage(
            f"Sanitizzazione per TAB: layer {src_layer.name()} con {src_layer.fields().count()} campi", 
            "BatchConverter", level=0
        )
        
        # Analizza i valori per determinare le lunghezze e precisioni necessarie
        field_stats = {}
        for fld in src_layer.fields():
            if fld.type() == QVariant.Double:
                max_val = 0
                max_decimals = 0
                for feat in src_layer.getFeatures():
                    val = feat[fld.name()]
                    if val is not None:
                        try:
                            val_float = float(val)
                            # Controlla se il valore è troppo grande
                            max_val = max(max_val, abs(val_float))
                            
                            # Controlla il numero di decimali
                            val_str = str(val_float)
                            if '.' in val_str:
                                decimals = len(val_str.split('.')[1])
                                max_decimals = max(max_decimals, decimals)
                        except:
                            pass
                
                field_stats[fld.name()] = {'max_val': max_val, 'max_decimals': max_decimals}
                QgsMessageLog.logMessage(
                    f"Statistiche campo {fld.name()}: max_val={max_val}, max_decimals={max_decimals}", 
                    "BatchConverter", level=0
                )
        
        fixed_fields = QgsFields()
        for fld in src_layer.fields():
            QgsMessageLog.logMessage(
                f"Campo: {fld.name()} - tipo: {fld.typeName()} - lunghezza: {fld.length()}", 
                "BatchConverter", level=0
            )
            
            if fld.type() == QVariant.Int or fld.type() == QVariant.LongLong:
                # Integer o LongLong vanno bene così
                fixed_fields.append(QgsField(fld.name(), QVariant.Int, "Integer"))
            elif fld.type() == QVariant.Double:
                # Verifica se il valore è troppo grande per un Real in MapInfo
                if fld.name() in field_stats and field_stats[fld.name()]['max_val'] > 9.99e14:
                    # Converte in String per valori molto grandi
                    QgsMessageLog.logMessage(
                        f"Campo {fld.name()} contiene valori troppo grandi, convertito in String", 
                        "BatchConverter", level=0
                    )
                    new_fld = QgsField(fld.name(), QVariant.String, "String")
                    new_fld.setLength(254)
                    fixed_fields.append(new_fld)
                else:
                    # Double: assicura lunghezza e precisione adeguata
                    new_fld = QgsField(fld.name(), QVariant.Double, "Real")
                    # Determina la lunghezza totale necessaria
                    if fld.name() in field_stats:
                        max_val = field_stats[fld.name()]['max_val']
                        max_decimals = field_stats[fld.name()]['max_decimals']
                        
                        # Calcola lunghezza necessaria:
                        # digit interi + punto decimale + decimali + eventuale segno
                        int_digits = len(str(int(max_val)))
                        total_length = int_digits + 1 + max_decimals + 1
                        
                        # Imposta lunghezza e precisione
                        new_fld.setLength(min(total_length, 30))  # MapInfo supporta max 30
                        new_fld.setPrecision(min(max_decimals, 15))  # MapInfo supporta max 15
                    else:
                        # Default per sicurezza
                        new_fld.setLength(20)
                        new_fld.setPrecision(10)
                    
                    QgsMessageLog.logMessage(
                        f"Campo {fld.name()} impostato come Real({new_fld.length()},{new_fld.precision()})", 
                        "BatchConverter", level=0
                    )
                    fixed_fields.append(new_fld)
            else:
                # Tutto il resto (Date, DateTime, Bool, Uuid, ecc.) diventa String
                new_fld = QgsField(fld.name(), QVariant.String, "String")
                new_fld.setLength(254)  # MapInfo supporta fino a 254 caratteri
                fixed_fields.append(new_fld)
        
        # Crea layer memory con lo stesso tipo di geometria
        mem_uri = f"{src_layer.geometryType()}?crs={src_layer.crs().authid()}"
        mem = QgsVectorLayer(mem_uri, "tab_tmp", "memory")
        
        # Aggiungi i campi
        mem.dataProvider().addAttributes(fixed_fields.toList())
        mem.updateFields()
        
        # Log dei campi finali
        QgsMessageLog.logMessage(
            f"Layer memory creato con {mem.fields().count()} campi", 
            "BatchConverter", level=0
        )
        
        # Copia feature & valori
        features = []
        for feat in src_layer.getFeatures():
            new_feat = QgsFeature(mem.fields())
            new_feat.setGeometry(feat.geometry())
            
            attrs = []
            for i, fld in enumerate(mem.fields()):
                if i < len(feat.attributes()):
                    val = feat.attributes()[i]
                    
                    # Converti in base al tipo di campo di destinazione
                    if fld.type() == QVariant.String and val is not None:
                        attrs.append(str(val))
                    elif fld.type() == QVariant.Int and val is not None:
                        try:
                            attrs.append(int(val))
                        except (ValueError, TypeError):
                            attrs.append(None)
                    elif fld.type() == QVariant.Double and val is not None:
                        try:
                            # Controlla se il valore è troppo grande per la precisione
                            float_val = float(val)
                            # Tronca i decimali alla precisione specificata
                            precision = fld.precision()
                            if precision > 0:
                                # Arrotonda a 'precision' decimali
                                float_val = round(float_val, precision)
                            attrs.append(float_val)
                        except (ValueError, TypeError):
                            attrs.append(None)
                    else:
                        attrs.append(val)
                else:
                    attrs.append(None)
            
            new_feat.setAttributes(attrs)
            features.append(new_feat)
        
        # Aggiungi tutte le feature in un'unica operazione
        mem.dataProvider().addFeatures(features)
        mem.updateExtents()
        
        QgsMessageLog.logMessage(
            f"Copiate {len(features)} feature nel layer memory", 
            "BatchConverter", level=0
        )
        
        return mem
    
    def convert_to_mapinfo(self, input_file, output_file):
        """
        Conversione specificamente per formato MapInfo Tab con gestione attributi
        """
        # Normalizza i percorsi dei file
        input_file = input_file.replace("\\", "/")
        output_file = output_file.replace("\\", "/")
        
        # Crea la directory di output se non esiste
        output_dir = os.path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)
        
        # Definisci il percorso del file temporaneo
        temp_geojson = os.path.join(output_dir, "temp_mapinfo_conversion.geojson").replace("\\", "/")
        
        # Assicurati che non esistano file temporanei da precedenti esecuzioni
        if os.path.exists(temp_geojson):
            try:
                os.remove(temp_geojson)
            except:
                pass
        
        try:
            # Prima soluzione: prova con ogr2ogr direttamente
            QgsMessageLog.logMessage(
                f"Tentativo 1: conversione diretta da {input_file} a {output_file}", 
                "BatchConverter", level=0
            )
            result = self._convert_to_mapinfo_with_ogr(input_file, output_file)
            if result:
                QgsMessageLog.logMessage("Conversione diretta con ogr2ogr riuscita", "BatchConverter", level=0)
                return True
            
            # Se fallisce, prova con l'approccio della sanitizzazione
            QgsMessageLog.logMessage("Tentativo 2: sanitizzazione e conversione in due passi", "BatchConverter", level=0)
            
            # Carica il layer originale
            input_layer = QgsVectorLayer(input_file, "temp_layer", "ogr")
            if not input_layer.isValid():
                QgsMessageLog.logMessage(f"Layer non valido: {input_file}", "BatchConverter", level=2)
                return False
            
            # Crea un layer temporaneo con attributi modificati per MapInfo
            memory_layer = self._sanitize_for_tab(input_layer)
            
            # Verifica che il layer memory sia valido
            if not memory_layer.isValid() or memory_layer.featureCount() == 0:
                QgsMessageLog.logMessage("Layer memory non valido o vuoto dopo sanitizzazione", "BatchConverter", level=2)
                return False
            
            # Salva il layer temporaneo in un formato intermedio (GeoJSON)
            QgsMessageLog.logMessage(f"Salvataggio layer memory in: {temp_geojson}", "BatchConverter", level=0)
            
            # Usa QgsVectorFileWriter per salvare il layer memory in GeoJSON
            geojson_options = QgsVectorFileWriter.SaveVectorOptions()
            geojson_options.driverName = "GeoJSON"
            
            # Esegui il salvataggio
            error = QgsVectorFileWriter.writeAsVectorFormat(memory_layer, temp_geojson, geojson_options)
            
            # Verifica che il salvataggio sia andato a buon fine
            if isinstance(error, tuple):
                error_code, error_message = error
                if error_code != QgsVectorFileWriter.NoError:
                    QgsMessageLog.logMessage(
                        f"Errore nel salvataggio del GeoJSON temporaneo: {error_message}", 
                        "BatchConverter", level=2
                    )
                    return False
            elif error != QgsVectorFileWriter.NoError:
                QgsMessageLog.logMessage(
                    f"Errore nel salvataggio del GeoJSON temporaneo (codice: {error})", 
                    "BatchConverter", level=2
                )
                return False
            
            # Verifica che il file temporaneo sia stato creato
            if not os.path.exists(temp_geojson):
                QgsMessageLog.logMessage(
                    f"File temporaneo non creato: {temp_geojson}", 
                    "BatchConverter", level=2
                )
                return False
            
            # Ora prova a convertire da GeoJSON a MapInfo
            try:
                # Prova l'algoritmo di processing
                import processing # type: ignore
                
                QgsMessageLog.logMessage(
                    f"Tentativo di conversione da GeoJSON ({temp_geojson}) a MapInfo ({output_file})", 
                    "BatchConverter", level=0
                )
                
                # Verifica se il file GeoJSON è valido
                temp_layer = QgsVectorLayer(temp_geojson, "temp", "ogr")
                if not temp_layer.isValid():
                    QgsMessageLog.logMessage(
                        f"File GeoJSON temporaneo non valido: {temp_geojson}", 
                        "BatchConverter", level=2
                    )
                    return False
                
                # Usa native:savefeatures per la conversione
                params = {
                    'INPUT': temp_geojson,
                    'OUTPUT': output_file
                }
                
                # Se è richiesta una riproiezione, includi il TARGET_CRS
                if self.dialog.bctransformcrs.isChecked() and self.dialog.bcoutputcrs.crs().isValid():
                    params['TARGET_CRS'] = self.dialog.bcoutputcrs.crs()
                    QgsMessageLog.logMessage("Aggiunta riproiezione nella conversione", "BatchConverter", level=0)
                    processing.run("native:reprojectlayer", params)
                else:
                    processing.run("native:savefeatures", params)
                
                # Verifica il risultato prima di rimuovere il file temporaneo
                if os.path.exists(output_file):
                    QgsMessageLog.logMessage(
                        f"Conversione riuscita, file creato: {output_file}", 
                        "BatchConverter", level=0
                    )
                    # Rimuovi il file temporaneo
                    if os.path.exists(temp_geojson):
                        os.remove(temp_geojson)
                    return True
                else:
                    QgsMessageLog.logMessage(
                        f"File di output non creato: {output_file}", 
                        "BatchConverter", level=2
                    )
            
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Errore con algoritmo di processing: {str(e)}", 
                    "BatchConverter", level=2
                )
            
            # Se siamo qui, i tentativi precedenti sono falliti
            # Ultimo tentativo: usa ogr2ogr direttamente sul file GeoJSON
            if os.path.exists(temp_geojson):
                QgsMessageLog.logMessage(
                    f"Tentativo 3: conversione da GeoJSON a MapInfo con ogr2ogr", 
                    "BatchConverter", level=0
                )
                result = self._convert_temp_geojson_to_mapinfo_with_ogr(temp_geojson, output_file)
                
                # Rimuovi il file temporaneo anche in caso di fallimento
                try:
                    os.remove(temp_geojson)
                except:
                    pass
                    
                return result
            
            # Se non abbiamo nemmeno il file GeoJSON, non possiamo fare altro
            return False
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Errore durante la conversione a MapInfo: {str(e)}", 
                "BatchConverter", level=2
            )
            
            # Assicurati di rimuovere il file temporaneo
            if os.path.exists(temp_geojson):
                try:
                    os.remove(temp_geojson)
                except:
                    pass
                    
            return False
        
    def _convert_temp_geojson_to_mapinfo_with_ogr(self, temp_geojson, output_file):
        """
        Ultimo tentativo con ogr2ogr da GeoJSON a MapInfo
        """
        try:
            # Verifica che il file temporaneo esista
            if not os.path.exists(temp_geojson):
                QgsMessageLog.logMessage(
                    f"File temporaneo GeoJSON non trovato: {temp_geojson}", 
                    "BatchConverter", level=2
                )
                return False
            
            import subprocess
            
            # Prepara il comando ogr2ogr
            command = ["ogr2ogr", "-f", "MapInfo File", "-skipfailures"]
            
            # Se è richiesta una riproiezione
            if self.dialog.bctransformcrs.isChecked() and self.dialog.bcoutputcrs.crs().isValid():
                srid = self.dialog.bcoutputcrs.crs().postgisSrid()
                command.extend(["-t_srs", f"EPSG:{srid}"])
            
            # Forza alcune opzioni per la struttura TAB
            command.extend(["-lco", "BOUNDS_CHECKER=OFF"])
            
            # Destinazione e sorgente
            command.append(output_file)     # Destinazione
            command.append(temp_geojson)    # Sorgente
            
            # Esecuzione del comando
            command_str = ' '.join(command)
            QgsMessageLog.logMessage(
                f"Ultimo tentativo di conversione con ogr2ogr: {command_str}", 
                "BatchConverter", level=0
            )
            
            # Esegui il comando
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Attendi il completamento e ottieni l'output
            stdout, stderr = process.communicate()
            
            # Verifica se ci sono errori
            if process.returncode != 0:
                error_message = stderr.strip()
                QgsMessageLog.logMessage(
                    f"Errore ogr2ogr finale: {error_message}", 
                    "BatchConverter", level=2
                )
                return False
            
            # Verifica che il file esista
            result = os.path.exists(output_file)
            QgsMessageLog.logMessage(
                f"Risultato conversione ogr2ogr finale: {result}", 
                "BatchConverter", level=0
            )
            return result
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Errore nel fallback finale per MapInfo: {str(e)}", 
                "BatchConverter", level=2
            )
            return False

    def _convert_to_mapinfo_with_ogr(self, input_file, output_file):
        """
        Converte a MapInfo usando ogr2ogr come ultima risorsa
        """
        try:
            import subprocess
            
            # Prepara il comando ogr2ogr
            command = ["ogr2ogr", "-f", "MapInfo File"]
            
            # Aggiungi skipfailures per gestire i problemi di conversione
            command.append("-skipfailures")
            
            # Se è richiesta una riproiezione
            if self.dialog.bctransformcrs.isChecked() and self.dialog.bcoutputcrs.crs().isValid():
                srid = self.dialog.bcoutputcrs.crs().postgisSrid()
                command.extend(["-t_srs", f"EPSG:{srid}"])
            
            # Destinazione e sorgente
            command.append(output_file)  # Destinazione
            command.append(input_file)   # Sorgente
            
            # Esecuzione del comando
            QgsMessageLog.logMessage(
                f"Tentativo di conversione con ogr2ogr: {' '.join(command)}", 
                "BatchConverter", level=0
            )
            
            # Esegui il comando
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Attendi il completamento e ottieni l'output
            stdout, stderr = process.communicate()
            
            # Verifica se ci sono errori
            if process.returncode != 0:
                error_message = stderr.strip()
                QgsMessageLog.logMessage(
                    f"Errore ogr2ogr per MapInfo: {error_message}", 
                    "BatchConverter", level=2
                )
                return False
            
            # Verifica che il file esista
            return os.path.exists(output_file)
        
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Errore nel fallback ogr2ogr per MapInfo: {str(e)}", 
                "BatchConverter", level=2
            )
            return False
    
    def toggle_controls(self, enable):
        """Attiva/disattiva i controlli durante l'elaborazione"""
        # Controlla i principali controlli dell'interfaccia
        self.dialog.bcbrowsesource.setEnabled(enable)
        self.dialog.bcbrowsedest.setEnabled(enable)
        self.dialog.bcaddsources.setEnabled(enable)
        self.dialog.bcremovefiles.setEnabled(enable)
        self.dialog.bcclearfiles.setEnabled(enable)
        self.dialog.bcrun.setEnabled(enable)
        
        # Disattiva altri controlli come necessario
        self.dialog.bcsourcepath.setEnabled(enable)
        self.dialog.bcdestpath.setEnabled(enable)
        self.dialog.bcoutputformat.setEnabled(enable)
        self.dialog.bcshpcheck.setEnabled(enable)
        self.dialog.bcgpkgcheck.setEnabled(enable)
        self.dialog.bcgeojsoncheck.setEnabled(enable)
        self.dialog.bcgmlcheck.setEnabled(enable)
        self.dialog.bckmlcheck.setEnabled(enable)
        self.dialog.bcrecursive.setEnabled(enable)
        self.dialog.bcnamefilter.setEnabled(enable)
        # self.dialog.bctransformcrs.setEnabled(enable)
        
        # ───────── checkbox & widget CRS ─────────
        is_csv = self.dialog.bcoutputformat.currentText() == 'CSV'

        # Il checkbox deve restare DISABILITATO se il formato è CSV
        self.dialog.bctransformcrs.setEnabled(enable and not is_csv)

        # Il widget CRS segue il checkbox
        if enable and not is_csv:
            self.toggle_crs_widget(self.dialog.bctransformcrs.checkState())
        else:
            # o lo disattivi del tutto
            self.dialog.bcoutputcrs.setEnabled(False)

        # ───────── controlli specifici per CSV ─────────
        self.dialog.bcdelimiter.setEnabled(enable and is_csv)
        self.dialog.bcdelimiterlabel.setEnabled(enable and is_csv)


        
        # IMPORTANTE: Attiva il widget CRS solo se il checkbox è selezionato
        # Quando i controlli vengono riattivati
        if enable:
            # Applica lo stato corrente del checkbox per il widget CRS
            self.toggle_crs_widget(self.dialog.bctransformcrs.checkState())
        else:
            # Durante l'elaborazione, disabilita sempre il widget CRS
            self.dialog.bcoutputcrs.setEnabled(False)
        
        # Controlli specifici per formato
        # self.dialog.bcdelimiter.setEnabled(enable and self.dialog.bcoutputformat.currentText() == 'CSV')
        # self.dialog.bclayername.setEnabled(enable and self.dialog.bcoutputformat.currentText() == 'GeoPackage')
        self.dialog.bcsinglefile.setEnabled(enable and self.dialog.bcoutputformat.currentText() == 'GeoPackage')