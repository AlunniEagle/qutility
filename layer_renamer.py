# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LayerRenamer
                                 A QGIS plugin component
 Tool to rename layers in multiple ways
                             -------------------
        begin                : 2025-05-06
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
from qgis.PyQt.QtCore import Qt # type: ignore
from qgis.core import QgsProject, QgsMapLayer # type: ignore
from qgis.PyQt.QtWidgets import QApplication, QMessageBox # type: ignore


class LayerRenamer:
    """A class to handle layer renaming operations"""
    
    def __init__(self, dialog):
        """Constructor.
        
        :param dialog: The dialog instance that contains the UI elements
        """
        self.dialog = dialog
        
        # Connect signals
        self.dialog.rllayerlist.itemSelectionChanged.connect(self.update_selection_count)
        self.dialog.rlrun.clicked.connect(self.rename_layers)
        self.dialog.rlsos.textChanged.connect(self.toggle_replace_field)
        
        # Set validators for number fields
        # int_validator = QtGui.QIntValidator(0, 999, self.dialog)
        # self.dialog.rlsx.setValidator(int_validator)
        # self.dialog.rldx.setValidator(int_validator)
        
        # Initially disable replacement field
        self.dialog.rlcon.setEnabled(False)
        
    def populate_layers(self):
        """Popola la lista dei layer"""
        self.dialog.rllayerlist.clear()
        
        # Ottieni tutti i layer dal progetto
        layers = QgsProject.instance().mapLayers().values()
        
        for layer in layers:
            item = QtWidgets.QListWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer)
            self.dialog.rllayerlist.addItem(item)

        # Update selection count if needed
        self.update_selection_count()
    
    def update_selection_count(self):
        """Aggiorna il conteggio dei layer selezionati"""
        selected_count = len(self.dialog.rllayerlist.selectedItems())
        if selected_count > 0:
            self.dialog.rlrun.setText(f"  Rinomina Selezionati ({selected_count})")
        else:
            self.dialog.rlrun.setText("  Rinomina Selezionati")
    
    def toggle_replace_field(self, text):
        """Attiva/disattiva il campo di sostituzione in base al contenuto del campo 'Sostituisci'"""
        self.dialog.rlcon.setEnabled(len(text) > 0)
        
        # Se il campo 'Sostituisci' viene svuotato, svuota anche il campo 'Con'
        if len(text) == 0:
            self.dialog.rlcon.setText("")
    
    def get_selected_layers(self):
        """Restituisce una lista dei layer selezionati"""
        selected_layers = []
        
        for item in self.dialog.rllayerlist.selectedItems():
            layer = item.data(Qt.UserRole)
            if layer:
                selected_layers.append(layer)
        
        return selected_layers
    
    def rename_layers(self):
        """Rinomina i layer selezionati in base ai parametri inseriti"""
        # Ottieni i layer selezionati
        selected_layers = self.get_selected_layers()
        if not selected_layers:
            QMessageBox.warning(self.dialog, "Attenzione", "Seleziona almeno un layer")
            return
        
        # Ottieni i valori dai campi
        prefix = self.dialog.rlpre.text()
        suffix = self.dialog.rlsuf.text()
        search_text = self.dialog.rlsos.text()
        replace_text = self.dialog.rlcon.text()
        
        try:
            remove_left = int(self.dialog.rlsx.text() or "0")
            remove_right = int(self.dialog.rldx.text() or "0")
        except ValueError:
            QMessageBox.warning(self.dialog, "Errore", "I valori per rimuovere i caratteri devono essere numeri")
            return
        
        # Verifica se è stato inserito almeno un parametro
        if not (prefix or suffix or search_text or remove_left > 0 or remove_right > 0):
            QMessageBox.warning(self.dialog, "Attenzione", "Inserisci almeno un parametro di rinomina")
            return
        
        # Verifica se è stato inserito un testo di ricerca ma non di sostituzione
        if search_text and not replace_text:
            reply = QMessageBox.question(
                self.dialog,
                "Conferma",
                "Hai inserito un testo da sostituire ma non un testo sostitutivo.\n"
                "Vuoi procedere eliminando il testo da sostituire?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            replace_text = ""
        
        # Chiedi conferma
        operations = []
        if prefix:
            operations.append(f"Aggiungere il prefisso: '{prefix}'")
        if suffix:
            operations.append(f"Aggiungere il suffisso: '{suffix}'")
        if search_text:
            operations.append(f"Sostituire '{search_text}' con '{replace_text}'")
        if remove_left > 0:
            operations.append(f"Rimuovere {remove_left} caratteri da sinistra")
        if remove_right > 0:
            operations.append(f"Rimuovere {remove_right} caratteri da destra")
        
        operation_text = "\n".join([f"- {op}" for op in operations])
        
        reply = QMessageBox.question(
            self.dialog,
            "Conferma",
            f"Applicare le seguenti operazioni ai {len(selected_layers)} layer selezionati?\n\n{operation_text}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
        
        # Disabilita i controlli
        self.toggle_controls(False)
        
        # Crea e mostra il popup di elaborazione
        progress_dialog = QMessageBox(self.dialog)
        progress_dialog.setWindowTitle("Elaborazione in corso")
        progress_dialog.setText("Rinomina dei layer in corso...\nNon chiudere QGIS.")
        progress_dialog.setStandardButtons(QMessageBox.NoButton)
        progress_dialog.setIcon(QMessageBox.Information)
        
        # Mostra il popup senza bloccare
        progress_dialog.show()
        QApplication.processEvents()
        
        renamed_layers = []
        error_layers = []
        
        # Processa ogni layer
        for layer in selected_layers:
            try:
                # Aggiorna l'UI
                QApplication.processEvents()
                
                old_name = layer.name()
                new_name = old_name
                
                # Rimuovi caratteri da sinistra
                if remove_left > 0:
                    if len(new_name) > remove_left:
                        new_name = new_name[remove_left:]
                    else:
                        new_name = ""
                
                # Rimuovi caratteri da destra
                if remove_right > 0 and new_name:
                    if len(new_name) > remove_right:
                        new_name = new_name[:-remove_right]
                    else:
                        new_name = ""
                
                # Sostituisci testo
                if search_text and new_name:
                    new_name = new_name.replace(search_text, replace_text)
                
                # Aggiungi prefisso
                if prefix:
                    new_name = prefix + new_name
                
                # Aggiungi suffisso
                if suffix:
                    new_name = new_name + suffix
                
                # Verifica che il nuovo nome non sia vuoto
                if not new_name:
                    error_layers.append(f"{old_name} (nome risultante vuoto)")
                    continue
                
                # Applica il nuovo nome
                layer.setName(new_name)
                renamed_layers.append(f"{old_name} -> {new_name}")
                
            except Exception as e:
                error_layers.append(f"{layer.name()} ({str(e)})")
        
        # Chiudi il popup di elaborazione
        progress_dialog.accept()
        
        # Riabilita i controlli
        self.toggle_controls(True)
        
        # Crea un messaggio di completamento dettagliato
        result_message = ""
        
        if renamed_layers:
            result_message += f"Rinomina completata per {len(renamed_layers)} layer:\n"
            result_message += "\n".join(renamed_layers)
        
        if error_layers:
            if result_message:
                result_message += "\n\n"
            result_message += f"Errori in {len(error_layers)} layer:\n"
            result_message += "\n".join(error_layers)
        
        if not result_message:
            result_message = "Nessun layer rinominato."
        
        # Mostra messaggio di completamento
        QMessageBox.information(self.dialog, "Completato", result_message)
        
        # Aggiorna la lista dei layer nel plugin
        self.populate_layers()
    
    def toggle_controls(self, enable):
        """Attiva/disattiva i controlli durante l'elaborazione"""
        self.dialog.rllayerlist.setEnabled(enable)
        self.dialog.rlpre.setEnabled(enable)
        self.dialog.rlsuf.setEnabled(enable)
        self.dialog.rlsos.setEnabled(enable)
        self.dialog.rlcon.setEnabled(enable and len(self.dialog.rlsos.text()) > 0)
        self.dialog.rlsx.setEnabled(enable)
        self.dialog.rldx.setEnabled(enable)
        self.dialog.rlrun.setEnabled(enable)