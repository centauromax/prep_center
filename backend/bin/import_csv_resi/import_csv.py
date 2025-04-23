import csv
import json
import re
import html
import mysql.connector
from mysql.connector import Error
from datetime import datetime

def load_config(config_file):
    with open(config_file, 'r') as file:
        config = json.load(file)
    return config

def preprocess_csv(file_path):
    # Pre-processamento: eliminare le prime due righe e la prima colonna
    with open(file_path, 'r') as csv_file:
        reader = csv.reader(csv_file)
        next(reader)  # ignora la prima riga
        next(reader)  # ignora la seconda riga

        processed_rows = []
        for row in reader:
            processed_row = row[1:]  # rimuove la prima colonna
            processed_rows.append(processed_row)

    # La prima riga dei dati processati ora diventa l'header
    header = processed_rows[0]
    rows = processed_rows[1:]

    # Converti i nomi delle colonne: rimuovi le parentesi, converti in minuscolo e sostituisci gli spazi con underscore
    mapped_header = [re.sub(r'[()]', '', col).strip().lower().replace(' ', '_') for col in header]
    
    return mapped_header, rows

def convert_date_format(date_str):
    if not date_str.strip():
        return None  # Se la data è vuota, restituisci None
    try:
        # Converte il formato DD/MM/YYYY in YYYY-MM-DD
        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None  # Se non è una data valida, restituisci None

def clean_text(text):
    if not text.strip():
        return None  # Restituisci None se il campo è vuoto
    # Decodifica le entità HTML e rimuovi i caratteri speciali non desiderati
    cleaned_text = html.unescape(text)
    # Rimuovi i caratteri non ASCII
    cleaned_text = re.sub(r'[^\x00-\x7F]+', '', cleaned_text)
    return cleaned_text

def process_dates_and_integers_in_rows(header, rows):
    # Identifica gli indici delle colonne `picked`, `shipped`, `verification_request`, `box`, `product_description`, e `customer_notes`
    date_columns = [i for i, col in enumerate(header) if col in ['picked', 'shipped']]
    int_columns = [i for i, col in enumerate(header) if col in ['verification_request', 'box']]
    text_columns = [i for i, col in enumerate(header) if col in ['product_description', 'customer_notes']]

    # Converti i valori di data, interi e testo nelle righe
    for row in rows:
        for index in date_columns:
            row[index] = convert_date_format(row[index])
        for index in int_columns:
            # Se il valore non è un numero, impostalo a 0 (default per `verification_request` e `box`)
            row[index] = int(row[index]) if row[index].strip().isdigit() else 0
        for index in text_columns:
            # Pulisci i caratteri speciali nei campi di testo
            row[index] = clean_text(row[index])
    
    return rows

def truncate_table(connection, table_name):
    try:
        cursor = connection.cursor()
        truncate_query = f"TRUNCATE TABLE {table_name}"
        cursor.execute(truncate_query)
        connection.commit()
        print(f"Table {table_name} truncated successfully.")
    except Error as e:
        print(f"Error: {e}")

def insert_data_to_db(connection, table_name, header, rows):
    try:
        cursor = connection.cursor()

        # Aggiungi la colonna `company` all'header e il valore "Selley" alle righe
        header.append('company')
        rows = [row + ["Selley"] for row in rows]

        # Racchiudi i nomi delle colonne con backtick per evitare errori SQL
        columns = ', '.join([f'`{col}`' for col in header])
        placeholders = ', '.join(['%s'] * len(header))
        insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

        # Eseguire l'inserimento di tutte le righe
        cursor.executemany(insert_query, rows)
        connection.commit()
        print(f"{cursor.rowcount} record(s) inserted successfully into {table_name}.")
    except Error as e:
        print(f"Error: {e}")

def main():
    config = load_config('config.json')

    csv_file = config['csv_file']
    db_config = config['db_config']
    table_name = config['table_name']

    # Pre-processamento del CSV
    header, rows = preprocess_csv(csv_file)

    # Conversione delle date, degli interi e pulizia del testo
    rows = process_dates_and_integers_in_rows(header, rows)

    # Connessione al database
    try:
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database']
        )

        if connection.is_connected():
            # Svuota la tabella
            truncate_table(connection, table_name)

            # Inserimento dati nel database
            insert_data_to_db(connection, table_name, header, rows)

    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            connection.close()

if __name__ == "__main__":
    main()

