#!/usr/bin/env python3

import polib
import os

# Percorsi dei file .po di origine e destinazione
SOURCE_PO_FILE = './locale/en/LC_MESSAGES/django.po'  # File sorgente (inglese)
TARGET_PO_FILE = './locale/it/LC_MESSAGES/django.po'  # File di destinazione (italiano)

def create_specular_po_file(source, target):
    # Se il file di destinazione esiste, eliminalo
    if os.path.exists(target):
        os.remove(target)
        print(f"Il file {target} esisteva ed è stato eliminato.")

    # Carica il file di origine con polib
    source_po = polib.pofile(source)

    # Crea un nuovo file .po per la lingua di destinazione
    target_po = polib.POFile()

    # Copia i metadati dal file di origine al file di destinazione
    target_po.metadata = source_po.metadata

    # Copia le voci di traduzione in modo speculare (msgid = msgstr)
    for entry in source_po:
        new_entry = polib.POEntry(
            msgid=entry.msgid,
            msgstr=entry.msgid  # Copia msgid come msgstr per la traduzione speculare
        )
        target_po.append(new_entry)
        print(f"Aggiunta voce speculare per: {entry.msgid}")

    # Salva il file di destinazione con l'header e le traduzioni speculari
    target_po.save(target)
    print(f"File speculare creato in: {target}")

# Esegui la creazione del file speculare
create_specular_po_file(SOURCE_PO_FILE, TARGET_PO_FILE)

