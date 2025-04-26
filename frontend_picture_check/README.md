# Frontend Picture Check

App React per la gestione della funzionalità Picture Check.

## Comandi utili

- **Installazione dipendenze:**
  ```bash
  npm install
  ```

- **Avvio locale:**
  ```bash
  npm start
  ```

- **Build produzione:**
  ```bash
  npm run build
  ```

- **Deploy:**
  Deploy automatico tramite Railway.

---

## Note
- Assicurati che le chiamate API puntino a `https://prepcenter-production.up.railway.app`.
- Per sviluppo locale, puoi usare `http://localhost:8000` come backend.

## Descrizione

Questa applicazione permette di verificare se per un determinato codice EAN sono già state scattate le foto del prodotto. 
L'app è composta da:

- Un selettore per scegliere il cliente
- Un campo di input per inserire l'EAN da verificare
- Un'area messaggi per visualizzare l'esito della verifica
- Una lista degli EAN già verificati

## Tecnologie utilizzate

- React.js
- Fetch API per le chiamate al backend
- CSS personalizzato

## Struttura del progetto

```
src/
├── components/           # Componenti React
│   ├── ClienteSelect.js  # Selettore clienti
│   ├── EanInput.js       # Input per EAN
│   ├── EsitoMessage.js   # Messaggio esito
│   └── EanHistory.js     # Cronologia EAN
├── utils/
│   └── suoni.js          # Gestione suoni
├── api.js                # Chiamate API
├── App.js                # Componente principale
├── index.js              # Entry point
└── styles.css            # Stili CSS
```

## Sviluppo locale

1. Assicurarsi di avere Node.js installato
2. Installare le dipendenze: `npm install`
3. Avviare il server di sviluppo: `npm start`

## Variabili d'ambiente

Le seguenti variabili d'ambiente possono essere configurate:

- `REACT_APP_API_URL`: URL base per le API (predefinito: `/picture_check/api`)
- `NODE_ENV`: Ambiente di esecuzione (`development` o `production`)
- `GENERATE_SOURCEMAP`: Se generare o meno le source map in produzione (consigliato: `false`)

Per lo sviluppo locale, è possibile creare un file `.env.local` con queste variabili.
Per la produzione su Railway, configurare queste variabili attraverso l'interfaccia di Railway.

## Deployment su Railway

Questa app è configurata per essere deployata su Railway. Il file `railway.json` contiene la configurazione necessaria per il build e il deployment.

### Processo di deployment

1. Ogni push al repository attiva automaticamente un build su Railway
2. Railway eseguirà `npm install && npm run build` come specificato nel file di configurazione
3. I file compilati verranno serviti attraverso un server web
4. Lo script `postbuild.js` sposterà i file compilati nelle directory corrette per l'integrazione con Django

## Integrazione con Django

Questa applicazione React comunica con il backend Django attraverso le API REST esposte dall'app `picture_check`. L'integrazione avviene nel modo seguente:

1. Il frontend React viene compilato durante il processo di build su Railway
2. Lo script `postbuild.js` copia i file statici compilati nelle directory appropriate:
   - I file JS e CSS vanno in `backend/static/picture_check/react/static/`
   - L'HTML va in `backend/picture_check/templates/picture_check/react/`
3. Le API del backend sono accessibili attraverso gli endpoint definiti in `api.js` 