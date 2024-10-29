# Funzione per filtrare colonne e rinominare le colonne rimanenti
import sys
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import pandas as pd
import logging
import io
from datetime import datetime

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

# Ottieni il logger per l'app fbasaving
logger = logging.getLogger('fbasaving')

def save_uploaded_file(file, total_amazon_cost, saving):
    # Genera il nome del file con il formato richiesto
    current_time = datetime.now()
    # Usa - invece di : per l'ora
    file_name = f"{current_time.strftime('%Y%m%d-%H.%M')}-{int(total_amazon_cost)}-{int(saving)}"
    
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

def debug_print(message):
    """Scrive il messaggio in un file di debug dedicato"""
    # Usa la directory corrente del progetto
    current_dir = os.getcwd()
    debug_file = os.path.join(current_dir, 'fbasaving_debug.log')
    
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(debug_file, 'a') as f:
            f.write(f'[{timestamp}] {message}\n')
    except Exception as e:
        print(f"Error writing to debug file: {e}", flush=True)

def filter_columns(file_content):
    try:
        debug_print("=== STARTING FILTER_COLUMNS FUNCTION ===")
        
        # Legge il contenuto del file in un DataFrame pandas
        df = pd.read_csv(io.StringIO(file_content.decode('utf-8')), sep=None, engine='python')
        
        debug_print(f"Numero di righe iniziale: {len(df)}")
        
        # Normalizza i nomi delle colonne
        df.columns = df.columns.str.replace('\ufeff', '').str.strip().str.lower().str.replace(r'[^a-z0-9_]', '', regex=True)

        # Converti le colonne numeriche
        def safe_convert(x):
            if pd.isna(x):
                return None
            if isinstance(x, str):
                return float(x.replace(',', '.'))
            return float(x)

        numeric_columns = ['estimated_monthly_storage_fee', 'item_volume', 'average_quantity_on_hand']
        for col in numeric_columns:
            df[col] = df[col].apply(safe_convert)

        # Filtra subito le righe con storage fee = 0
        df = df[df['estimated_monthly_storage_fee'] != 0]
        
        debug_print(f"Righe dopo filtro storage fee: {len(df)}")

        # Calcola il volume totale del prodotto
        df['total_product_volume'] = df['item_volume'] * df['average_quantity_on_hand']

        # Calcola i rate e i costi
        df['amazon_monthly_rate'] = (df['estimated_monthly_storage_fee'] / df['total_product_volume']).round(6)
        df['our_monthly_rate'] = 12
        df['our_monthly_cost'] = 12 * df['total_product_volume']

        # Debug: verifica calcoli
        debug_print("\nVerifica calcoli:")
        sample_records = df[df['asin'].isin(['B07CYZ3R84', 'B00G7RQXCY'])]
        for _, row in sample_records.iterrows():
            debug_print(f"""
            ASIN: {row['asin']}
            Storage Fee: {row['estimated_monthly_storage_fee']}
            Product Volume: {row['item_volume']}
            Quantity: {row['average_quantity_on_hand']}
            Total Volume: {row['total_product_volume']}
            Amazon Rate: {row['amazon_monthly_rate']}
            Our Cost: {row['our_monthly_cost']}
            """)

        # Mapping finale delle colonne
        column_mapping = {
            'product_name': 'Product',
            'country_code': 'Market',
            'item_volume': 'Product volume',
            'total_product_volume': 'Total volume',
            'estimated_monthly_storage_fee': 'Amazon monthly cost',
            'amazon_monthly_rate': 'Amazon monthly rate',
            'our_monthly_rate': 'Our monthly rate',
            'our_monthly_cost': 'Our monthly cost'
        }

        # Seleziona e rinomina le colonne finali
        filtered_df = df[list(column_mapping.keys())].rename(columns=column_mapping)
        filtered_df = filtered_df.sort_values('Amazon monthly rate', ascending=False)
        
        debug_print(f"Numero di righe finale: {len(filtered_df)}")
        
        return filtered_df

    except Exception as e:
        debug_print(f"ERROR in filter_columns: {str(e)}")
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
        debug_print("=== Starting file_processing ===")
        
        # Leggi il contenuto del file
        file_content = file.read()
        debug_print("File content read successfully")

        # Chiama la funzione per filtrare le colonne
        filtered_data = filter_columns(file_content)

        # Calcoli finali
        total_amazon_cost = filtered_data['Amazon monthly cost'].sum()
        total_prep_center_cost = filtered_data['Our monthly cost'].sum()
        saving = total_amazon_cost - total_prep_center_cost
        saving_percentage = (saving / total_amazon_cost) * 100 if total_amazon_cost != 0 else 0

        # Salva il file caricato
        save_uploaded_file(file, total_amazon_cost, saving)

        return {
            'total_amazon_cost': float(total_amazon_cost),
            'total_prep_center_cost': float(total_prep_center_cost),
            'saving': float(saving),
            'saving_percentage': float(saving_percentage),
            'table_data': filtered_data.to_dict('records')
        }
    except Exception as e:
        debug_print(f"ERROR in file_processing: {str(e)}")
        debug_print(f"Type of error: {type(e)}")
        raise ValueError(f"Errore nel processamento del file: {str(e)}")
