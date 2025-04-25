# Picture Check

App per la verifica dei prodotti di cui sono state fatte le foto.

## Descrizione

Questa app permette di verificare se per un determinato codice EAN sono già state scattate le foto del prodotto. 
Se le foto non sono ancora state scattate, il sistema emette un suono di affermazione e salva l'EAN nel database.
Se le foto sono già state scattate, il sistema emette un suono di negazione.

## Funzionalità

- Selezione del cliente da una lista
- Verifica di un codice EAN alla volta
- Feedback sonoro sull'esito della verifica
- Visualizzazione degli EAN già verificati
- Registrazione di nuovi EAN nel database

## API

L'app espone le seguenti API:

- `GET /api/clienti/` - Ottiene la lista dei clienti attivi
- `GET /api/check/<ean>/` - Verifica se per un determinato EAN sono già state fatte le foto
- `POST /api/salva/` - Salva un nuovo EAN per cui le foto non sono state fatte
- `GET /api/lista/` - Ottiene la lista degli ultimi EAN verificati

## Installazione

1. Assicurarsi che l'app sia inclusa in `INSTALLED_APPS` nelle impostazioni del progetto
2. Eseguire le migrazioni: `python manage.py migrate picture_check`
3. Popolare il database con clienti di esempio: `python manage.py populate_clienti`
4. Aggiungere i file audio richiesti in `static/picture_check/sounds/`

## Frontend

Il frontend dell'app è sviluppato in React attraverso Lovable. I file sorgente si trovano nella directory
`frontend/picture_check/`. 