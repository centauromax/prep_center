import csv
from datetime import datetime
from return_management.models import ProductReturn

def parse_date(date_str):
    """Converte una data dal formato DD/MM/YYYY al formato YYYY-MM-DD."""
    try:
        return datetime.strptime(date_str, '%d/%m/%Y').date()
    except ValueError:
        return None  # Restituisce None se la data non è valida o vuota

def import_csv(file_path):
    with open(file_path, mode='r') as file:
        reader = csv.DictReader(file)
        row_count = 0
        for row in reader:
            row_count += 1
            notes_value = row.get('Notes;;;;', None) or row.get('Notes', None)
            if notes_value:
                notes_value = notes_value.replace(';', '').strip()
            else:
                notes_value = ''

            # Stampa di debug per vedere cosa è stato letto
            print(f"Riga {row_count}: {row}")

            try:
                ProductReturn.objects.create(
                    box=row.get('Box', '').strip() if row.get('Box') else None,
                    box_type=row.get('Box Type', '').strip() if row.get('Box Type') else '',
                    picked=parse_date(row.get('Picked', '').strip()) if row.get('Picked') else None,
                    shipped=parse_date(row.get('Shipped', '').strip()) if row.get('Shipped') else None,
                    lpn=row.get('LPN', '').strip() if row.get('LPN') else '',
                    brand=row.get('Brand', '').strip() if row.get('Brand') else '',
                    product_description=row.get('Product Description', '').strip() if row.get('Product Description') else '',
                    additional_info=row.get('Additional Info', '').strip() if row.get('Additional Info') else '',
                    other_info=row.get('Other Info', '').strip() if row.get('Other Info') else '',
                    destination=row.get('Destination', '').strip() if row.get('Destination') else '',
                    verification_request=False,
                    verification_question='',
                    verification_response='',
                    asin=row.get('ASIN', '').strip() if row.get('ASIN') else '',
                    sku=row.get('SKU', '').strip() if row.get('SKU') else '',
                    fnsku=row.get('FNSKU', '').strip() if row.get('FNSKU') else '',
                    ean='',  # Valore fisso
                    product_code='',  # Valore fisso
                    serial_number='',  # Valore fisso
                    state_amz=row.get('State (Amz)', '').strip() if row.get('State (Amz)') else '',
                    reason_amz=row.get('Reason (Amz)', '').strip() if row.get('Reason (Amz)') else '',
                    customer_notes=row.get('Customer Notes', '').strip() if row.get('Customer Notes') else '',
                    company='Selley',  # Valore fisso
                    notes=notes_value  # Valore pulito
                )
            except Exception as e:
                print(f"Errore alla riga {row_count}: {e}")
                raise  # Rilancia l'eccezione per debugging
    print("Importazione completata.")

# Esecuzione diretta con il file CSV specificato
import_csv('selley.csv')

