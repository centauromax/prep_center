import csv

def test_csv(file_path):
    with open(file_path, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            print(row.keys())  # Stampa le chiavi per verificare i nomi delle colonne
            break  # Controlla solo la prima riga

test_csv('selley.csv')

