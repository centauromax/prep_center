# Amazon SP-API Integration - Prep Center

## 🚀 Panoramica

L'integrazione Amazon SP-API (Selling Partner API) permette di gestire direttamente ordini, inventario, report e informazioni account Amazon dal sistema Prep Center.

## 📋 Funzionalità Implementate

### ✅ Sistema Completo Implementato

- **Client SP-API Centralizzato**: `libs/api_client/amazon_sp_api.py`
- **Modello Configurazioni**: `AmazonSPAPIConfig` nel database
- **Views API REST**: 8 endpoint funzionali
- **Interface Admin**: Gestione configurazioni via Django Admin
- **Templates Web**: Dashboard interattiva per utilizzo
- **Sistema di Testing**: Test automatici connessione
- **Multi-Marketplace**: Supporto IT, DE, FR, ES, GB, US
- **Error Handling**: Gestione errori avanzata
- **Logging**: Sistema di logging dettagliato
- **Statistiche**: Tracciamento utilizzo API

## 🏗️ Architettura

```
backend/
├── libs/api_client/amazon_sp_api.py    # Client SP-API centralizzato
├── prep_management/
│   ├── models.py                       # AmazonSPAPIConfig model
│   ├── admin.py                        # Admin interface
│   ├── views.py                        # 8 API endpoints
│   ├── urls.py                         # URL routing
│   └── templates/prep_management/
│       └── sp_api_config_list.html     # Dashboard SP-API
└── requirements.txt                    # python-amazon-sp-api==1.9.38
```

## 🔧 Installazione e Setup

### 1. Dipendenze Installate
```bash
# Già presente in requirements.txt
python-amazon-sp-api==1.9.38
```

### 2. Database Migration
```bash
# Modello già migrato
python manage.py migrate
```

### 3. Credenziali Amazon SP-API

Per utilizzare il sistema, è necessario ottenere le credenziali Amazon:

1. **Developer Console Amazon**: Registrare un'applicazione
2. **LWA Credentials**: App ID e Client Secret
3. **Refresh Token**: Token di autorizzazione seller
4. **Marketplace**: Codice marketplace (IT, DE, FR, ES, GB, US)

### 4. Configurazione via Admin

1. Accedere a: `/admin/prep_management/amazonspiapiconfig/`
2. Cliccare "Aggiungi Amazon S P API Config"
3. Inserire:
   - **Nome**: Nome identificativo configurazione
   - **Refresh Token**: Token di refresh
   - **LWA App ID**: ID applicazione Login with Amazon
   - **LWA Client Secret**: Secret applicazione
   - **Marketplace**: Selezionare marketplace
   - **Is Active**: Abilitare configurazione
   - **Is Sandbox**: Abilitare per ambiente test

## 🌐 Endpoints API Disponibili

### Configurazioni
- `GET /prep_management/sp-api/config/` - Lista configurazioni
- `POST /prep_management/sp-api/test/{id}/` - Test connessione

### Ordini Amazon
- `GET /prep_management/sp-api/orders/` - Lista ordini
  - Parametri: `marketplace`, `days_back`, `max_results`
- `GET /prep_management/sp-api/orders/{order_id}/` - Dettaglio ordine

### Inventario
- `GET /prep_management/sp-api/inventory/` - Riepilogo inventario
  - Parametri: `marketplace`

### Report
- `GET /prep_management/sp-api/reports/` - Tipi report disponibili
- `POST /prep_management/sp-api/reports/create/` - Crea nuovo report

### Account Info
- `GET /prep_management/sp-api/account/` - Informazioni account seller

## 🎯 Dashboard Web

### Accesso Dashboard
- **URL**: `/prep_management/sp-api/config/`
- **Dalla Homepage**: Card "Amazon SP-API"
- **Quick Access**: Link nella sezione debug

### Funzionalità Dashboard
- ✅ **Lista Configurazioni**: Visualizzazione configurazioni attive
- ✅ **Test Connessioni**: Test automatico credenziali
- ✅ **Statistiche Utilizzo**: Contatori chiamate API
- ✅ **Stato Libreria**: Verifica disponibilità SP-API
- ✅ **Gestione Multipla**: Supporto multi-marketplace
- ✅ **Interface Responsive**: Compatibile mobile/desktop

## 📊 Esempi di Utilizzo

### Test Configurazione via cURL

```bash
# Lista configurazioni
curl http://localhost:8000/prep_management/sp-api/config/

# Recupera ordini Italia ultimi 7 giorni
curl "http://localhost:8000/prep_management/sp-api/orders/?marketplace=IT&days_back=7&max_results=50"

# Inventario Amazon Italia
curl "http://localhost:8000/prep_management/sp-api/inventory/?marketplace=IT"

# Info account seller
curl "http://localhost:8000/prep_management/sp-api/account/?marketplace=IT"
```

### Utilizzo Client Python

```python
from libs.api_client.amazon_sp_api import AmazonSPAPIClient
from prep_management.models import AmazonSPAPIConfig

# Ottieni configurazione attiva
config = AmazonSPAPIConfig.get_config_for_marketplace('IT')
if config:
    # Crea client
    credentials = config.get_credentials_dict()
    client = AmazonSPAPIClient(credentials=credentials)
    
    # Test connessione
    test_result = client.test_connection()
    
    if test_result['success']:
        # Recupera ordini
        orders = client.get_orders()
        
        # Recupera inventario
        inventory = client.get_inventory_summary()
        
        # Info account
        account = client.get_account_info()
```

## 🔒 Sicurezza e Best Practices

### Credenziali
- ❌ **Mai hardcodare** credenziali nel codice
- ✅ **Usare configurazioni database** per flessibilità
- ✅ **Environment variables** per deployment
- ✅ **Sandbox mode** per testing

### Rate Limiting
- Amazon SP-API ha limiti di rate per tipo di endpoint
- Il client gestisce automaticamente retry con backoff
- Statistiche utilizzo monitorate nel database

### Error Handling
- Tutte le chiamate API sono in try/catch
- Errori loggati con livello appropriato
- Fallback graceful quando libreria non disponibile

## 🛠️ Troubleshooting

### Libreria SP-API Non Disponibile
```bash
# Installare la libreria
pip install python-amazon-sp-api==1.9.38

# Verificare installazione
python -c "from sp_api.api import Orders; print('OK')"
```

### Errori di Autenticazione
1. Verificare credenziali LWA in configurazione
2. Controllare che refresh token sia valido
3. Verificare che marketplace sia corretto
4. Testare con ambiente sandbox prima

### Problemi di Rate Limiting
- Monitorare statistiche utilizzo in dashboard
- Implementare cache per dati non real-time
- Usare batch processing per operazioni multiple

### Debug API Calls
```python
# Abilitare logging dettagliato
import logging
logging.getLogger('libs.api_client.amazon_sp_api').setLevel(logging.DEBUG)

# Verificare configurazione
from prep_management.models import AmazonSPAPIConfig
configs = AmazonSPAPIConfig.objects.filter(is_active=True)
for config in configs:
    print(f"Config: {config.name}, Marketplace: {config.marketplace}")
```

## 📈 Monitoring e Analytics

### Dashboard Admin
- **URL**: `/admin/prep_management/amazonspiapiconfig/`
- **Filtri**: Per marketplace, stato, sandbox
- **Azioni**: Test connessione, attivazione/disattivazione
- **Statistiche**: Success rate, total calls, errori

### Database Tracking
```sql
-- Configurazioni attive
SELECT name, marketplace, is_active, total_api_calls, total_api_errors 
FROM prep_management_amazonspiapiconfig 
WHERE is_active = true;

-- Configurazioni con problemi
SELECT name, last_test_success, last_test_message, last_test_at
FROM prep_management_amazonspiapiconfig 
WHERE last_test_success = false;
```

## 🚀 Deployment su Railway

### Environment Variables
```bash
# Opzionali - per configurazione di default
AMAZON_SP_API_REFRESH_TOKEN=Atzr|...
AMAZON_SP_API_LWA_APP_ID=amzn1.application...
AMAZON_SP_API_LWA_CLIENT_SECRET=...
AMAZON_SP_API_MARKETPLACE=IT
```

### Health Check
```bash
# Verifica che tutto funzioni in produzione
curl https://backend.fbaprepcenteritaly.com/prep_management/sp-api/config/
```

## 🔄 Aggiornamenti Futuri

### Funzionalità Pianificate
- [ ] **Cache Redis**: Per risultati frequenti
- [ ] **Webhook Support**: Per notifiche real-time Amazon
- [ ] **Batch Operations**: Per operazioni multiple
- [ ] **Analytics Dashboard**: Grafici utilizzo
- [ ] **Export Funzioni**: CSV/Excel per dati
- [ ] **Scheduler Tasks**: Automatizzazione periodica

### Endpoint Aggiuntivi
- [ ] **Products API**: Gestione catalogo prodotti
- [ ] **FBA Inbound**: Gestione spedizioni FBA
- [ ] **Financial Events**: Eventi finanziari
- [ ] **Pricing API**: Gestione prezzi
- [ ] **Advertising API**: Gestione campagne pubblicitarie

## 📞 Supporto

### Debugging
- **Logs**: Controllare logs Django per errori SP-API
- **Admin**: Usare interfaccia admin per configurazioni
- **Dashboard**: Monitorare statistiche utilizzo

### Documentazione Amazon
- [SP-API Documentation](https://developer.amazonservices.com/sp-api)
- [python-amazon-sp-api Library](https://github.com/python-amazon-sp-api/python-amazon-sp-api)

### Support Prep Center
- **Dashboard**: `/prep_management/sp-api/config/`
- **Debug API**: `/prep_management/api-debug/`
- **Admin Panel**: `/admin/prep_management/amazonspiapiconfig/`

---

**✅ Integrazione Amazon SP-API Completata e Operativa**

*Sistema pronto per l'uso in produzione con tutte le funzionalità implementate e testate.* 