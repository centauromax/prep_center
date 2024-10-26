# Funzione per filtrare colonne e rinominare le colonne rimanenti
import sys
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

# Aggiungi il percorso del sito-packages dell'ambiente virtuale
venv_path = os.path.dirname(os.path.dirname(sys.executable))
site_packages = os.path.join(venv_path, 'lib', 'python3.9', 'site-packages')
sys.path.append(site_packages)

print("Python version:", sys.version)
print("Python path:", sys.path)
print("Current working directory:", os.getcwd())

try:
    import pandas as pd
    print("Pandas version:", pd.__version__)
except ImportError as e:
    print(f"Errore nell'importazione di pandas: {e}")

import logging
import io
from datetime import datetime

logger = logging.getLogger(__name__)

def save_uploaded_file(file, total_amazon_cost, saving):
    # Genera il nome del file con il formato richiesto
    current_time = datetime.now()
    file_name = f"{current_time.strftime('%Y%m%d-%H:%M')}-{int(total_amazon_cost)}-{int(saving)}"
    
    # Ottieni l'estensione del file originale
    _, file_extension = os.path.splitext(file.name)
    
    # Aggiungi l'estensione al nuovo nome del file
    file_name += file_extension
    
    # Percorso relativo all'interno di MEDIA_ROOT
    relative_path = os.path.join('report_stoccaggio', file_name)
    
    # Salva il file usando default_storage
    with default_storage.open(relative_path, 'wb') as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    
    # Ottieni il percorso completo del file salvato
    full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    
    logger.info(f"File salvato in: {full_path}")
    return full_path

def filter_columns(file_content, columns_to_keep, new_column_names):
    try:
        # Legge il contenuto del file in un DataFrame pandas
        df = pd.read_csv(io.StringIO(file_content.decode('utf-8')), sep=None, engine='python')

        # Debug: stampa i nomi delle colonne originali
        logger.debug(f"Nomi colonne originali: {df.columns.tolist()}")

        # Rimuovi eventuali caratteri BOM dai nomi delle colonne
        df.columns = df.columns.str.replace('\ufeff', '')

        # Normalizza i nomi delle colonne: rimuove spazi, converte in minuscolo, rimuove caratteri speciali
        df.columns = df.columns.str.strip().str.lower().str.replace(r'[^a-z0-9_]', '', regex=True)

        # Debug: stampa i nomi delle colonne normalizzati
        logger.debug(f"Nomi colonne normalizzati: {df.columns.tolist()}")

        # Aggiungi colonna 'average_quantity_on_hand' se non esiste
        if 'average_quantity_on_hand' not in df.columns:
            raise KeyError("La colonna 'average_quantity_on_hand' non è presente nel file di input.")

        # Calcola 'Total volume' come item_volume * average_quantity_on_hand
        df.loc[:, 'estimated_total_item_volume'] = df['item_volume'] * df['average_quantity_on_hand']

        # Filtra le righe con 'estimated_monthly_storage_fee' diverso da zero
        df = df[df['estimated_monthly_storage_fee'] != 0]

        # Filtra le colonne specificate
        filtered_df = df.loc[:, columns_to_keep]

        # Rinomina le colonne
        filtered_df.columns = new_column_names

        return filtered_df
    except KeyError as e:
        logger.error(f"Errore durante il filtraggio delle colonne: Colonna non trovata {e}")
        raise
    except Exception as e:
        logger.error(f"Errore durante il filtraggio delle colonne: {e}")
        raise

# Funzione per calcolare il tasso mensile Amazon
def amazon_costs(df):
    try:
        # Calcola 'Amazon monthly rate applied' come Amazon monthly cost / Total volume
        df['Amazon monthly cost'] = df['Amazon monthly cost'].apply(lambda x: str(x).replace(',', '.')).astype(float)
        df['Total volume'] = df['Total volume'].apply(lambda x: str(x).replace(',', '.')).astype(float)
        df['Amazon monthly rate applied'] = df['Amazon monthly cost'] / df['Total volume']
        return df
    except Exception as e:
        logger.error(f"Errore durante il calcolo del tasso mensile Amazon: {e}")
        raise

# Funzione per calcolare il costo mensile del prep center
def prep_center_costs(df):
    try:
        # Aggiungi la colonna 'Our monthly rate' con un valore fisso di 12
        df['Our monthly rate'] = 12

        # Calcola 'Our monthly cost' come 12 * Total volume
        df['Our monthly cost'] = df['Our monthly rate'] * df['Total volume']
        return df
    except Exception as e:
        logger.error(f"Errore durante il calcolo del costo mensile del prep center: {e}")
        raise

def file_processing(file):
    try:
        columns_to_keep = ["asin", "fnsku", "product_name", "country_code", "item_volume", "estimated_total_item_volume", "estimated_monthly_storage_fee"]
        new_column_names = ["ASIN", "FNSKU", "Product", "Marketplace", "Product volume", "Total volume", "Amazon monthly cost"]

        # Leggi il contenuto del file
        file_content = file.read()

        # Chiama la funzione per filtrare le colonne
        filtered_data = filter_columns(file_content, columns_to_keep, new_column_names)

        # Chiama la funzione per calcolare il tasso mensile Amazon
        filtered_data = amazon_costs(filtered_data)

        # Chiama la funzione per calcolare il costo mensile del prep center
        filtered_data = prep_center_costs(filtered_data)

        # Assicuriamoci che i nomi delle colonne corrispondano esattamente
        filtered_data = filtered_data.rename(columns={
            'product_name': 'Product',
            'country_code': 'Marketplace',
            'item_volume': 'Product volume',
            'estimated_total_item_volume': 'Total volume',
            'estimated_monthly_storage_fee': 'Amazon monthly cost',
            'our_monthly_rate': 'Our monthly rate',
            'our_monthly_cost': 'Our monthly cost'
        })

        # Rimuoviamo le colonne ASIN e FNSKU
        filtered_data = filtered_data.drop(columns=['ASIN', 'FNSKU'])

        # Calcoli come forniti nel tuo codice
        total_amazon_cost = filtered_data['Amazon monthly cost'].sum()
        total_prep_center_cost = filtered_data['Our monthly cost'].sum()
        saving = total_amazon_cost - total_prep_center_cost
        saving_percentage = (saving / total_amazon_cost) * 100 if total_amazon_cost != 0 else 0

        # Converti il DataFrame in una lista di dizionari per il rendering JSON
        table_data = filtered_data.to_dict('records')

        # Salva il file caricato (manteniamo questa funzione, ma non restituiamo il percorso)
        save_uploaded_file(file, total_amazon_cost, saving)

        return {
            'total_amazon_cost': float(total_amazon_cost),
            'total_prep_center_cost': float(total_prep_center_cost),
            'saving': float(saving),
            'saving_percentage': float(saving_percentage),
            'table_data': table_data
        }
    except Exception as e:
        logger.error(f"Errore nel processamento del file: {e}")
        raise ValueError(f"Errore nel processamento del file: {str(e)}")
