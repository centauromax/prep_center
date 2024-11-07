import os
import pandas as pd
import logging
import io
from datetime import datetime
from django.core.files.storage import default_storage
from django.conf import settings

# Configura il logger per debug
logger = logging.getLogger('fbasaving')
logger.info(f"Inizio elaborazione del file")

def save_uploaded_file(file, total_amazon_cost, saving):
    """Salva il file di report con un nome specifico in MEDIA_ROOT/report_stoccaggio."""
    logger.debug("Inizio salvataggio del file caricato.")
    current_time = datetime.now()
    file_name = f"{current_time.strftime('%Y%m%d-%H.%M')}-{int(total_amazon_cost)}-{int(saving)}"
    _, file_extension = os.path.splitext(file.name)
    file_name += file_extension
    relative_path = os.path.join('report_stoccaggio', file_name)
    
    with default_storage.open(relative_path, 'wb') as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    
    full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    logger.debug(f"File salvato con successo: {full_path}")
    return full_path

def convert_volume(volume, unit):
    """Converte il volume in metri cubi se necessario."""
    if unit == 'cubic feet':
        logger.debug(f"Conversione da cubic feet")
        return volume * 0.0283168  # Conversione da piedi cubi a metri cubi
    return volume

def calculate_volume(longest, median, shortest, unit):
    """Calcola il volume in metri cubi data la misura dei lati e l'unità di misura."""
    conversion_factor = 0.01 if unit == 'centimeters' else 1.0
    return round((longest * conversion_factor) * (median * conversion_factor) * (shortest * conversion_factor), 8)

def process_report_data(file_content):
    """Elabora i dati del file di report e calcola le metriche richieste."""
    logger.debug("Inizio elaborazione del report.")
    try:
        df = pd.read_csv(io.StringIO(file_content.decode('utf-8')), sep=None, engine='python')
        logger.debug("File CSV letto con successo.")
    except Exception as e:
        logger.error(f"Errore durante la lettura del file CSV: {e}")
        raise

    df.columns = df.columns.str.replace('\ufeff', '').str.strip().str.lower().str.replace(r'[^a-z0-9_]', '', regex=True)

    # Campi necessari
    required_columns = [
        'asin', 'product_name', 'country_code', 'longest_side', 'median_side', 'shortest_side',
        'measurement_units', 'item_volume', 'volume_units', 'average_quantity_on_hand', 
        'average_quantity_pending_removal', 'avg_qty_for_sus', 'estimated_total_item_volume',
        'estimated_monthly_storage_fee', 'base_rate', 'currency', 'month_of_charge'
    ]
    df = df[required_columns].copy()

    # Conversioni sicure
    def safe_convert(value, fallback=0.0):
        try:
            return float(str(value).replace(',', '.'))
        except ValueError:
            return fallback

    # Conversioni dei valori numerici
    numeric_columns = [
        'longest_side', 'median_side', 'shortest_side', 'item_volume', 
        'average_quantity_on_hand', 'average_quantity_pending_removal', 
        'avg_qty_for_sus', 'estimated_total_item_volume', 
        'estimated_monthly_storage_fee', 'base_rate'
    ]

    for col in numeric_columns:
        df[col] = df[col].apply(safe_convert)
        logger.debug(f"Colonna {col} convertita: {df[col].head()}")

    # Filtra le righe con estimated_monthly_storage_fee a zero
    df = df[df['estimated_monthly_storage_fee'] > 0]

    # Calcola il volume del prodotto
    def calculate_product_volume(row):
        if row['item_volume'] > 0.01:
            volume = convert_volume(row['item_volume'], row['volume_units'])
            logger.debug(f"ASIN {row['asin']}: Volume prodotto da item_volume: {volume}")
            return volume
        else:
            volume = calculate_volume(row['longest_side'], row['median_side'], row['shortest_side'], row['measurement_units'])
            logger.debug(f"ASIN {row['asin']}: Volume prodotto calcolato: {volume}")
            return volume

    df['product_volume'] = df.apply(calculate_product_volume, axis=1)

    # Filtra le righe con volume del prodotto a zero
    df = df[df['product_volume'] > 0]

    # Calcola il volume totale degli articoli e la tariffa Amazon
    def calculate_total_volume_and_rate(row):
        estimated_volume = convert_volume(row['estimated_total_item_volume'], row['volume_units'])
        volumes = [
            estimated_volume,
            row['product_volume'] * (row['average_quantity_on_hand'] + row['average_quantity_pending_removal']),
            row['product_volume'] * row['avg_qty_for_sus']
        ]

        # Calculate original rates for each volume
        original_rates = [row['estimated_monthly_storage_fee'] / v if v > 0 else float('inf') for v in volumes]
        
        if row['base_rate'] >= 5:
            # Logica esistente per base_rate >= 5
            rates = [max(rate, row['base_rate']) for rate in original_rates]
            valid_rates = [(rate, vol) for rate, vol in zip(rates, volumes) if rate <= row['base_rate'] * 1.5]
            if valid_rates:
                chosen_rate, chosen_volume = min(valid_rates, key=lambda x: abs(x[0] - row['base_rate']))
            else:
                chosen_rate = row['base_rate']
                below_base_rate = [(rate, vol) for rate, vol in zip(original_rates, volumes) if rate < row['base_rate']]
                if below_base_rate:
                    closest_below_rate, closest_below_volume = min(below_base_rate, key=lambda x: abs(x[0] - row['base_rate']))
                    if abs(closest_below_rate - row['base_rate']) / row['base_rate'] <= 0.2:
                        chosen_volume = closest_below_volume
                    else:
                        chosen_volume = row['estimated_monthly_storage_fee'] / row['base_rate']
                else:
                    chosen_volume = row['estimated_monthly_storage_fee'] / row['base_rate']
        else:
            # Nuova logica per base_rate < 5
            # Estrai il mese dal formato YYYY-MM
            month = int(row['month_of_charge'].split('-')[1])
            
            if 1 <= month <= 9:
                # Cerca la tariffa più bassa tra 25 e 35
                valid_rates = [(rate, vol) for rate, vol in zip(original_rates, volumes) if 25 <= rate <= 35]
                default_rate = 27.54
            else:  # month between 10 and 12
                # Cerca la tariffa più bassa tra 40 e 50
                valid_rates = [(rate, vol) for rate, vol in zip(original_rates, volumes) if 40 <= rate <= 50]
                default_rate = 42.37
            
            if valid_rates:
                # Prendi la tariffa più bassa nel range valido
                chosen_rate, chosen_volume = min(valid_rates, key=lambda x: x[0])
            else:
                # Usa la tariffa di default
                chosen_rate = default_rate
                chosen_volume = row['estimated_monthly_storage_fee'] / chosen_rate

        logger.debug(f"ASIN {row['asin']}: Tariffa Amazon scelta: {chosen_rate}, Volume totale scelto: {chosen_volume}")
        return chosen_volume, chosen_rate

    df[['total_product_volume', 'amazon_rate']] = df.apply(lambda row: pd.Series(calculate_total_volume_and_rate(row)), axis=1)

    # Conversione della tariffa in euro
    def convert_currency(value, currency):
        # Implementa la logica di conversione in base alla valuta
        return value  # Placeholder

    df['amazon_rate_euro'] = df.apply(lambda row: convert_currency(row['amazon_rate'], row['currency']), axis=1)

    # Calcola il costo di stoccaggio del prep center
    df['our_monthly_rate'] = 12
    df['our_monthly_cost'] = df['our_monthly_rate'] * df['total_product_volume']
    for index, row in df.iterrows():
        logger.debug(f"ASIN {row['asin']}: Costo mensile prep center calcolato: {row['our_monthly_cost']}")

    # Mappatura finale delle colonne per l'output
    column_mapping = {
        'product_name': 'Product',
        'country_code': 'Market',
        'product_volume': 'Product volume',
        'total_product_volume': 'Total volume',
        'estimated_monthly_storage_fee': 'Amazon monthly cost',
        'amazon_rate': 'Amazon monthly rate',
        'our_monthly_rate': 'Our monthly rate',
        'our_monthly_cost': 'Our monthly cost'
    }

    # Rinomina e ordina i dati per l'output
    filtered_df = df[list(column_mapping.keys())].rename(columns=column_mapping)
    filtered_df = filtered_df.sort_values('Amazon monthly rate', ascending=False)

    logger.debug("Dati del report elaborati con successo.")
    return filtered_df

def file_processing(file):
    """Funzione principale per elaborare il file di report, salvare il file e restituire i risultati."""
    logger.debug("Inizio elaborazione del file.")
    try:
        file_content = file.read()
        logger.debug("Contenuto del file letto con successo.")
        filtered_data = process_report_data(file_content)
        logger.debug("Dati del report processati con successo.")
        logger.debug(f"Prime righe di filtered_data: {filtered_data.head()}")

        # Calcoli finali
        total_amazon_cost = filtered_data['Amazon monthly cost'].sum()
        total_prep_center_cost = filtered_data['Our monthly cost'].sum()
        saving = total_amazon_cost - total_prep_center_cost
        saving_percentage = (saving / total_amazon_cost) * 100 if total_amazon_cost != 0 else 0

        # Log dei calcoli finali
        logger.debug(f"Calcoli finali: total_amazon_cost={total_amazon_cost}, total_prep_center_cost={total_prep_center_cost}, saving={saving}, saving_percentage={saving_percentage}")

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
        logger.error(f"Errore durante l'elaborazione del file: {e}")
        raise ValueError(f"Errore nel processamento del file: {str(e)}")
