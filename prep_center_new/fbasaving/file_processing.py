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
        'asin', 'product_name', 'longest_side', 'median_side', 'shortest_side',
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

    # Converti item_volume in metri cubi se necessario
    def convert_item_volume(row):
        if row['item_volume'] > 0.01:
            volume = convert_volume(row['item_volume'], row['volume_units'])
            logger.debug(f"ASIN {row['asin']}: Volume prodotto da item_volume: {volume}")
            return volume
        else:
            volume = calculate_volume(row['longest_side'], row['median_side'], row['shortest_side'], row['measurement_units'])
            logger.debug(f"ASIN {row['asin']}: Volume prodotto calcolato: {volume}")
            return volume

    df['item_volume_m3'] = df.apply(convert_item_volume, axis=1)

    # Filtra le righe con volume del prodotto a zero
    df = df[df['item_volume_m3'] > 0]

    # Converti estimated_total_item_volume in metri cubi
    df['estimated_total_item_volume_m3'] = df.apply(
        lambda row: convert_volume(row['estimated_total_item_volume'], row['volume_units']), 
        axis=1
    )

    # Converti i costi e le tariffe in euro
    def convert_to_euro(value, currency):
        # Implementa la logica di conversione in base alla valuta
        return value  # Placeholder - implementa la conversione corretta

    df['estimated_monthly_storage_fee_eur'] = df.apply(
        lambda row: convert_to_euro(row['estimated_monthly_storage_fee'], row['currency']), 
        axis=1
    )
    df['base_rate_eur'] = df.apply(
        lambda row: convert_to_euro(row['base_rate'], row['currency']), 
        axis=1
    )

    # Aggregazione per ASIN
    agg_dict = {
        'product_name': 'first',
        'item_volume_m3': 'first',
        'average_quantity_on_hand': 'sum',
        'average_quantity_pending_removal': 'sum',
        'avg_qty_for_sus': 'sum',
        'estimated_total_item_volume_m3': 'sum',
        'estimated_monthly_storage_fee_eur': 'sum',
        'base_rate_eur': 'mean',
        'month_of_charge': 'first'
    }

    df_aggregated = df.groupby('asin').agg(agg_dict).reset_index()
    logger.debug(f"Dati aggregati per ASIN. Numero righe originali: {len(df)}, Numero righe aggregate: {len(df_aggregated)}")

    # Calcola il volume totale degli articoli e la tariffa Amazon
    def calculate_total_volume_and_rate(row):
        volumes = [
            row['estimated_total_item_volume_m3'],
            row['item_volume_m3'] * (row['average_quantity_on_hand'] + row['average_quantity_pending_removal']),
            row['item_volume_m3'] * row['avg_qty_for_sus']
        ]

        # Calculate original rates for each volume
        original_rates = [row['estimated_monthly_storage_fee_eur'] / v if v > 0 else float('inf') for v in volumes]
        
        if row['base_rate_eur'] >= 5:
            # Logica per base_rate >= 5
            rates = [max(rate, row['base_rate_eur']) for rate in original_rates]
            valid_rates = [(rate, vol) for rate, vol in zip(rates, volumes) if rate <= row['base_rate_eur'] * 1.5]
            if valid_rates:
                chosen_rate, chosen_volume = min(valid_rates, key=lambda x: abs(x[0] - row['base_rate_eur']))
            else:
                chosen_rate = row['base_rate_eur']
                below_base_rate = [(rate, vol) for rate, vol in zip(original_rates, volumes) if rate < row['base_rate_eur']]
                if below_base_rate:
                    closest_below_rate, closest_below_volume = min(below_base_rate, key=lambda x: abs(x[0] - row['base_rate_eur']))
                    if abs(closest_below_rate - row['base_rate_eur']) / row['base_rate_eur'] <= 0.2:
                        chosen_volume = closest_below_volume
                    else:
                        chosen_volume = row['estimated_monthly_storage_fee_eur'] / row['base_rate_eur']
                else:
                    chosen_volume = row['estimated_monthly_storage_fee_eur'] / row['base_rate_eur']
        else:
            # Logica per base_rate < 5
            month = int(row['month_of_charge'].split('-')[1])
            
            if 1 <= month <= 9:
                valid_rates = [(rate, vol) for rate, vol in zip(original_rates, volumes) if 25 <= rate <= 35]
                default_rate = 27.54
            else:  # month between 10 and 12
                valid_rates = [(rate, vol) for rate, vol in zip(original_rates, volumes) if 40 <= rate <= 50]
                default_rate = 42.37
            
            if valid_rates:
                chosen_rate, chosen_volume = min(valid_rates, key=lambda x: x[0])
            else:
                chosen_rate = default_rate
                chosen_volume = row['estimated_monthly_storage_fee_eur'] / chosen_rate

        logger.debug(f"ASIN {row['asin']}: Tariffa Amazon scelta: {chosen_rate}, Volume totale scelto: {chosen_volume}")
        return chosen_volume, chosen_rate

    df_aggregated[['total_product_volume', 'amazon_rate']] = df_aggregated.apply(
        lambda row: pd.Series(calculate_total_volume_and_rate(row)), axis=1
    )

    # Calcola il costo di stoccaggio del prep center
    df_aggregated['our_monthly_rate'] = 12
    df_aggregated['our_monthly_cost'] = df_aggregated['our_monthly_rate'] * df_aggregated['total_product_volume']

    # Mappatura finale delle colonne per l'output
    column_mapping = {
        'product_name': 'Product',
        'item_volume_m3': 'Product volume',
        'total_product_volume': 'Total volume',
        'estimated_monthly_storage_fee_eur': 'Amazon monthly cost',
        'amazon_rate': 'Amazon monthly rate',
        'our_monthly_rate': 'Our monthly rate',
        'our_monthly_cost': 'Our monthly cost'
    }

    # Rinomina e ordina i dati per l'output
    filtered_df = df_aggregated[list(column_mapping.keys())].rename(columns=column_mapping)
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
