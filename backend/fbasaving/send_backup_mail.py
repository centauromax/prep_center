#!/usr/bin/env python3
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
import locale
import logging

# Imposta la localizzazione italiana per la data
locale.setlocale(locale.LC_TIME, "it_IT.utf8")

# Configura il logging
logging.basicConfig(
    filename='/var/www/html/logs/backup_email_sender.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def send_backup_email():
    backup_dir = '/var/www/html/logs/contatti/da_rinviare'
    
    # Controlla se la directory esiste
    if not os.path.exists(backup_dir):
        logging.info(f"Directory {backup_dir} non trovata")
        return
    
    email_body = ""
    files_processed = []

    # Processa tutti i file nella directory
    for filename in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, filename)
        
        # Estrae data e ora dal nome del file
        try:
            file_datetime = datetime.strptime(filename[:13], '%Y%m%d-%H%M')
            data_ora = file_datetime.strftime("Data contatto: %A %d %B %Y, Ora: %H:%M")
        except ValueError:
            logging.error(f"Formato del nome file non valido: {filename}")
            continue

        try:
            # Leggi il contenuto del file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Aggiungi i contenuti del file al corpo della mail
            email_body += f"{data_ora}\n{content}\n\n"
            files_processed.append(file_path)
        
        except Exception as e:
            logging.error(f"Errore nella lettura del file {filename}: {str(e)}")
            continue

    # Invia l'email solo se ci sono file processati
    if files_processed:
        try:
            # Configura l'email
            msg = EmailMessage()
            msg.set_content(email_body)
            msg['Subject'] = "Fba Saving: mail di backup contatti"
            msg['From'] = "info@wifiexpress.it"
            msg['To'] = "info@wifiexpress.it"
            
            # Invia l'email usando la configurazione della macchina
            with smtplib.SMTP('localhost') as server:  # Presuppone un mail server configurato localmente
                server.send_message(msg)
            
            # Sposta i file processati nella cartella superiore
            for file_path in files_processed:
                processed_dir = os.path.join(backup_dir, '..')
                os.rename(file_path, os.path.join(processed_dir, os.path.basename(file_path)))
            
            logging.info("Email di backup inviata con successo contenente tutti i contatti.")
        
        except Exception as e:
            logging.error(f"Errore nell'invio dell'email di backup: {str(e)}")

if __name__ == '__main__':
    send_backup_email()

