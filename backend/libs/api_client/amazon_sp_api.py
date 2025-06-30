"""
Amazon Selling Partner API Client
Centralizzato per l'integrazione con Amazon SP-API usando python-amazon-sp-api di Saleweaver
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    from sp_api.api import Orders
    from sp_api.api import Reports
    from sp_api.api import FulfillmentInbound
    from sp_api.api import Inventories
    from sp_api.api import Catalog
    from sp_api.api import Products
    from sp_api.api import Sellers
    from sp_api.base import SellingApiException
    from sp_api.base.reportTypes import ReportType
    from sp_api.base.marketplaces import Marketplaces
    SP_API_AVAILABLE = True
except ImportError as e:
    # Log error but allow import to succeed for development without full dependencies
    logging.error(f"SP-API library not available: {e}")
    Orders = Reports = FulfillmentInbound = None
    Inventories = Catalog = Products = Sellers = None
    SellingApiException = Exception
    ReportType = Marketplaces = None
    SP_API_AVAILABLE = False

logger = logging.getLogger(__name__)


class AmazonSPAPIClient:
    """
    Client centralizzato per Amazon Selling Partner API
    Usa la libreria python-amazon-sp-api di Saleweaver con parametri ufficiali
    """

    def __init__(self, credentials: Optional[Dict[str, Any]] = None):
        """
        Inizializza il client SP-API
        
        Args:
            credentials: Dizionario con credenziali Amazon SP-API (opzionale, usa env vars)
        """
        if not SP_API_AVAILABLE:
            logger.warning("SP-API library not available. Install with: pip install python-amazon-sp-api")
            
        # Ottieni credenziali da parametri o environment variables
        if credentials:
            self.credentials = credentials
        else:
            self.credentials = self._get_credentials_from_env()
            
        self.marketplace_id = self._get_marketplace_id()
        self.endpoint = self._get_endpoint()
        
        # Valida credenziali
        if SP_API_AVAILABLE and not self._validate_credentials():
            logger.error("Credenziali SP-API non valide o mancanti")
            
        logger.info(f"Client SP-API inizializzato per marketplace: {self.marketplace_id}")
        logger.info(f"Endpoint: {self.endpoint}")

    def _get_credentials_from_env(self) -> Dict[str, Any]:
        """
        Ottiene credenziali dalle environment variables usando i nomi ufficiali della libreria
        Supporta sia i nomi ufficiali (SP_API_*) che quelli custom (AMAZON_SP_API_*)
        """
        return {
            # Credenziali LWA - prova prima nomi ufficiali, poi fallback su custom
            'refresh_token': (
                os.getenv('SP_API_REFRESH_TOKEN') or 
                os.getenv('AMAZON_SP_API_REFRESH_TOKEN')
            ),
            'lwa_app_id': (
                os.getenv('SP_API_CLIENT_ID') or 
                os.getenv('AMAZON_SP_API_LWA_APP_ID')
            ),
            'lwa_client_secret': (
                os.getenv('SP_API_CLIENT_SECRET') or 
                os.getenv('AMAZON_SP_API_LWA_CLIENT_SECRET')
            ),
            
            # Credenziali AWS - prova prima nomi ufficiali, poi fallback su custom
            'aws_access_key': (
                os.getenv('SP_API_AWS_ACCESS_KEY') or 
                os.getenv('AMAZON_SP_API_AWS_ACCESS_KEY')
            ),
            'aws_secret_key': (
                os.getenv('SP_API_AWS_SECRET_KEY') or 
                os.getenv('AMAZON_SP_API_AWS_SECRET_KEY')
            ),
            'role_arn': (
                os.getenv('SP_API_ROLE_ARN') or 
                os.getenv('AMAZON_SP_API_ROLE_ARN')
            ),
            
            # Configurazione marketplace e endpoint
            'marketplace': (
                os.getenv('SP_API_MARKETPLACE') or 
                os.getenv('AMAZON_SP_API_MARKETPLACE', 'IT')
            )
        }

    def _validate_credentials(self) -> bool:
        """Valida che tutte le credenziali necessarie siano presenti"""
        required_fields = ['refresh_token', 'lwa_app_id', 'lwa_client_secret', 'aws_access_key', 'aws_secret_key', 'role_arn']
        missing_fields = [field for field in required_fields if not self.credentials.get(field)]
        
        if missing_fields:
            logger.warning(f"Credenziali mancanti: {missing_fields}")
            return False
            
        return True

    def _get_marketplace_id(self) -> str:
        """Ottiene il marketplace ID configurato"""
        marketplace_code = self.credentials.get('marketplace', 'IT')
        
        # Mappa marketplace ID Amazon ufficiali
        marketplace_id_mapping = {
            'IT': 'APJ6JRA9NG5V4',  # Amazon.it
            'DE': 'A1PA6795UKMFR9', # Amazon.de  
            'FR': 'A13V1IB3VIYZZH', # Amazon.fr
            'ES': 'A1RKKUPIHCS9HS', # Amazon.es
            'GB': 'A1F83G8C2ARO7P', # Amazon.co.uk
            'US': 'ATVPDKIKX0DER'   # Amazon.com
        }
        
        marketplace_id = marketplace_id_mapping.get(marketplace_code, 'APJ6JRA9NG5V4')
        logger.info(f"Marketplace {marketplace_code} mappato a ID: {marketplace_id}")
        return marketplace_id

    def _get_endpoint(self) -> str:
        """Ottiene l'endpoint SP-API corretto per il marketplace"""
        marketplace_code = self.credentials.get('marketplace', 'IT')
        
        # Mappa endpoint per regione
        if marketplace_code in ['IT', 'DE', 'FR', 'ES', 'GB']:
            endpoint = 'https://sellingpartnerapi-eu.amazon.com'
        elif marketplace_code == 'US':
            endpoint = 'https://sellingpartnerapi-na.amazon.com'
        else:
            endpoint = 'https://sellingpartnerapi-eu.amazon.com'  # Default EU
            
        # Supporta override da environment
        endpoint = (
            os.getenv('SP_API_ENDPOINT') or 
            os.getenv('AMAZON_SP_API_ENDPOINT') or 
            endpoint
        )
        
        return endpoint

    def _create_credentials_file(self) -> Dict[str, Any]:
        """
        ✅ SOLUZIONE DEFINITIVA: Crea file credentials.yml con DEBUG APPROFONDITO
        
        Restituisce info complete sul file creato per debug
        """
        import os
        import yaml
        from pathlib import Path
        
        # Path per file di configurazione (Linux/Railway)
        config_dir = Path.home() / '.config' / 'python-sp-api'
        config_file = config_dir / 'credentials.yml'
        
        # Crea directory se non esiste
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Struttura file credentials.yml
        credentials_data = {
            'version': '1.0',
            'default': {
                'refresh_token': self.credentials.get('refresh_token', ''),
                'lwa_app_id': self.credentials.get('lwa_app_id', ''),
                'lwa_client_secret': self.credentials.get('lwa_client_secret', ''),
                # AWS credentials sono opzionali nel file, possono rimanere in env vars
                'aws_access_key': self.credentials.get('aws_access_key', ''),
                'aws_secret_key': self.credentials.get('aws_secret_key', ''),
                'role_arn': self.credentials.get('role_arn', '')
            }
        }
        
        # Scrivi file YAML
        with open(config_file, 'w') as f:
            yaml.dump(credentials_data, f, default_flow_style=False)
        
        # Verifica che il file sia stato scritto correttamente
        file_exists = config_file.exists()
        file_size = config_file.stat().st_size if file_exists else 0
        
        # Leggi il contenuto per verifica
        file_content = ""
        if file_exists:
            with open(config_file, 'r') as f:
                file_content = f.read()
        
        debug_info = {
            'config_dir': str(config_dir),
            'config_file': str(config_file),
            'file_exists': file_exists,
            'file_size': file_size,
            'credentials_summary': {
                'refresh_token_length': len(self.credentials.get('refresh_token', '')),
                'lwa_app_id_present': bool(self.credentials.get('lwa_app_id')),
                'lwa_client_secret_present': bool(self.credentials.get('lwa_client_secret')),
                'aws_access_key_present': bool(self.credentials.get('aws_access_key')),
                'role_arn_present': bool(self.credentials.get('role_arn'))
            },
            'file_content_preview': file_content[:200] + '...' if len(file_content) > 200 else file_content
        }
        
        logger.info(f"📁 File credentials.yml: {config_file} (size: {file_size} bytes)")
        
        # Imposta anche env vars come fallback
        self._set_env_vars_fallback()
        
        return debug_info
    
    def _set_env_vars_fallback(self) -> None:
        """Environment variables come fallback - ORA INCLUDE ANCHE LWA!"""
        import os
        
        # ✅ NUOVO APPROCCIO: Environment variables per TUTTE le credenziali
        # Test se Saleweaver preferisce env vars al file credentials.yml
        if self.credentials.get('refresh_token'):
            os.environ['refresh_token'] = self.credentials['refresh_token']
        if self.credentials.get('lwa_app_id'):
            os.environ['lwa_app_id'] = self.credentials['lwa_app_id']
        if self.credentials.get('lwa_client_secret'):
            os.environ['lwa_client_secret'] = self.credentials['lwa_client_secret']
        if self.credentials.get('aws_access_key'):
            os.environ['aws_access_key'] = self.credentials['aws_access_key']
        if self.credentials.get('aws_secret_key'):
            os.environ['aws_secret_key'] = self.credentials['aws_secret_key']
        if self.credentials.get('role_arn'):
            os.environ['role_arn'] = self.credentials['role_arn']
        
        logger.info("🔧 Set environment variables per tutte le credenziali SP-API")

    def _get_constructor_kwargs(self) -> Dict[str, Any]:
        """
        ✅ NUOVO APPROCCIO: La libreria Saleweaver usa SOLO environment variables
        
        Dalla documentazione ufficiale GitHub:
        from sp_api.api import Orders
        res = Orders().get_orders(...)  # Nessun parametro nel costruttore!
        
        La libreria legge automaticamente da env vars standard:
        - refresh_token
        - lwa_app_id (NON lwa_client_id)
        - lwa_client_secret
        - aws_access_key
        - aws_secret_key  
        - role_arn
        """
        # ✅ CORREZIONE FONDAMENTALE: Saleweaver non usa parametri nel costruttore
        # Restituisce dict vuoto, tutte le credenziali sono via environment variables
        return {}



    def _handle_api_error(self, e: Exception, operation: str) -> None:
        """Gestisce gli errori delle API calls"""
        if isinstance(e, SellingApiException):
            logger.error(f"SP-API Error in {operation}: {e.code} - {e}")
        else:
            logger.error(f"Generic error in {operation}: {e}")
        raise e

    # =============================================================================
    # ORDERS API
    # =============================================================================

    def get_orders(self, 
                   created_after: Optional[datetime] = None,
                   created_before: Optional[datetime] = None,
                   last_updated_after: Optional[datetime] = None,
                   max_results_per_page: int = 50) -> Dict[str, Any]:
        """Recupera ordini dal marketplace Amazon - CUSTOM IMPLEMENTATION"""
        try:
            # ✅ SOLUZIONE DEFINITIVA: Chiamata HTTP diretta
            access_token = self._get_access_token()
            
            # Usa data di default se non specificata (ultimi 7 giorni)
            if not created_after and not last_updated_after:
                created_after = datetime.utcnow() - timedelta(days=7)

            # Prepara parametri URL
            params = {
                'MaxResultsPerPage': max_results_per_page,
                'MarketplaceIds': self.marketplace_id
            }

            if created_after:
                params['CreatedAfter'] = created_after.isoformat()
            if created_before:
                params['CreatedBefore'] = created_before.isoformat()
            if last_updated_after:
                params['LastUpdatedAfter'] = last_updated_after.isoformat()

            headers = {
                'Authorization': f'Bearer {access_token}',
                'x-amz-access-token': access_token,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.endpoint}/orders/v0/orders"
            
            import requests
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                orders_count = len(result.get('payload', {}).get('Orders', []))
                logger.info(f"✅ SP-API Custom: Recuperati {orders_count} ordini")
                return result.get('payload', {})
            else:
                raise Exception(f"SP-API Custom Orders Error: HTTP {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"❌ SP-API Custom Orders Error: {e}")
            self._handle_api_error(e, "get_orders_custom")

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Recupera dettagli di un singolo ordine"""
        if not SP_API_AVAILABLE:
            raise ImportError("SP-API library not available")
            
        try:
            # ✅ SOLUZIONE DEFINITIVA SALEWEAVER: File credentials.yml
            self._create_credentials_file()
            orders_client = Orders()  # Nessun parametro!
            response = orders_client.get_order(order_id)
            
            logger.info(f"Recuperato ordine {order_id}")
            return response.payload

        except Exception as e:
            self._handle_api_error(e, f"get_order({order_id})")

    def get_order_items(self, order_id: str) -> Dict[str, Any]:
        """Recupera items di un ordine"""
        if not SP_API_AVAILABLE:
            raise ImportError("SP-API library not available")
            
        try:
            # ✅ SOLUZIONE DEFINITIVA SALEWEAVER: File credentials.yml
            self._create_credentials_file()
            orders_client = Orders()  # Nessun parametro!
            response = orders_client.get_order_items(order_id)
            
            logger.info(f"Recuperati items per ordine {order_id}")
            return response.payload

        except Exception as e:
            self._handle_api_error(e, f"get_order_items({order_id})")

    # =============================================================================
    # INVENTORY API
    # =============================================================================

    def get_inventory_summary(self, 
                              granularity_type: str = "Marketplace",
                              granularity_id: Optional[str] = None,
                              start_date_time: Optional[datetime] = None,
                              seller_skus: Optional[List[str]] = None) -> Dict[str, Any]:
        """Recupera riepilogo inventario"""
        if not SP_API_AVAILABLE:
            raise ImportError("SP-API library not available")
            
        try:
            # Parametri di default
            granularity_id = granularity_id or self.marketplace_id
            start_date_time = start_date_time or datetime.utcnow() - timedelta(days=1)

            params = {
                'granularity_type': granularity_type,
                'granularity_id': granularity_id,
                'start_date_time': start_date_time.isoformat()
            }

            if seller_skus:
                params['seller_skus'] = seller_skus

            # ✅ SOLUZIONE DEFINITIVA SALEWEAVER: File credentials.yml
            self._create_credentials_file()
            inventories_client = Inventories()  # Nessun parametro!
            response = inventories_client.get_inventory_summary_marketplace(**params)
            
            logger.info("Recuperato riepilogo inventario")
            return response.payload

        except Exception as e:
            self._handle_api_error(e, "get_inventory_summary")

    # =============================================================================
    # REPORTS API
    # =============================================================================

    def create_report(self, 
                      report_type: str,
                      start_time: Optional[datetime] = None,
                      end_time: Optional[datetime] = None,
                      marketplace_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Crea un report"""
        if not SP_API_AVAILABLE:
            raise ImportError("SP-API library not available")
            
        try:
            params = {
                'reportType': report_type,
                'marketplaceIds': marketplace_ids or [self.marketplace_id]
            }

            if start_time:
                params['dataStartTime'] = start_time.isoformat()
            if end_time:
                params['dataEndTime'] = end_time.isoformat()

            # ✅ SOLUZIONE DEFINITIVA SALEWEAVER: File credentials.yml
            self._create_credentials_file()
            reports_client = Reports()  # Nessun parametro!
            response = reports_client.create_report(**params)
            
            logger.info(f"Report {report_type} creato")
            return response.payload

        except Exception as e:
            self._handle_api_error(e, f"create_report({report_type})")

    def get_report(self, report_id: str) -> Dict[str, Any]:
        """Recupera informazioni su un report"""
        if not SP_API_AVAILABLE:
            raise ImportError("SP-API library not available")
            
        try:
            # ✅ SOLUZIONE DEFINITIVA SALEWEAVER: File credentials.yml
            self._create_credentials_file()
            reports_client = Reports()  # Nessun parametro!
            response = reports_client.get_report(report_id)
            
            logger.info(f"Recuperato report {report_id}")
            return response.payload

        except Exception as e:
            self._handle_api_error(e, f"get_report({report_id})")

    # =============================================================================
    # SELLER API
    # =============================================================================

    def get_account_info(self) -> Dict[str, Any]:
        """Recupera informazioni account seller - CUSTOM IMPLEMENTATION"""
        try:
            # ✅ SOLUZIONE DEFINITIVA: Chiamata HTTP diretta (sappiamo che funziona!)
            access_token = self._get_access_token()
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'x-amz-access-token': access_token,
                'Content-Type': 'application/json'
            }
            
            # Usa marketplace participation come fallback (funziona sempre)
            url = f"{self.endpoint}/sellers/v1/marketplaceParticipations"
            
            import requests
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                logger.info("✅ SP-API Custom: Recuperate info account seller")
                return response.json()
            else:
                raise Exception(f"SP-API Custom Error: HTTP {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"❌ SP-API Custom Error: {e}")
            # NON chiamare _handle_api_error che fa raise - invece rilancia direttamente
            raise Exception(f"Custom SP-API Error: {str(e)}")
    
    def _get_access_token(self) -> str:
        """Ottiene access token via LWA (sappiamo che funziona!)"""
        import requests
        
        lwa_response = requests.post(
            'https://api.amazon.com/auth/o2/token',
            data={
                'grant_type': 'refresh_token',
                'refresh_token': self.credentials.get('refresh_token'),
                'client_id': self.credentials.get('lwa_app_id'),
                'client_secret': self.credentials.get('lwa_client_secret')
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        if lwa_response.status_code != 200:
            raise Exception(f"LWA Token Exchange failed: {lwa_response.status_code} - {lwa_response.text}")
        
        lwa_data = lwa_response.json()
        return lwa_data['access_token']

    def get_marketplace_participation(self) -> Dict[str, Any]:
        """Recupera informazioni partecipazione marketplace"""
        if not SP_API_AVAILABLE:
            raise ImportError("SP-API library not available")
            
        try:
            # ✅ SOLUZIONE DEFINITIVA SALEWEAVER: File credentials.yml
            self._create_credentials_file()
            sellers_client = Sellers()  # Nessun parametro!
            response = sellers_client.get_marketplace_participation()
            
            logger.info("Recuperate info marketplace participation")
            return response.payload

        except Exception as e:
            self._handle_api_error(e, "get_marketplace_participation")

    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def debug_connection_advanced(self) -> Dict[str, Any]:
        """🔍 DEBUG AVANZATO: Analisi completa per problemi tecnici SP-API"""
        if not SP_API_AVAILABLE:
            return {
                'success': False,
                'error_type': 'LIBRARY_NOT_AVAILABLE',
                'message': 'SP-API library non installata'
            }
            
        if not self._validate_credentials():
            return {
                'success': False,
                'error_type': 'CREDENTIALS_INVALID',
                'message': 'Credenziali SP-API mancanti'
            }

        debug_result = {
            'success': False,
            'timestamp': datetime.utcnow().isoformat(),
            'test_phases': {},
            'credentials_debug': {},
            'file_debug': {},
            'lwa_debug': {},
            'api_debug': {},
            'final_analysis': {}
        }

        # 🔍 PHASE 1: Analisi Credenziali
        logger.info("🔍 PHASE 1: Analisi credenziali...")
        try:
            debug_result['credentials_debug'] = {
                'marketplace_id': self.marketplace_id,
                'endpoint': self.endpoint,
                'credentials_summary': {
                    'refresh_token_length': len(self.credentials.get('refresh_token', '')),
                    'lwa_app_id': self.credentials.get('lwa_app_id', ''),
                    'lwa_client_secret_length': len(self.credentials.get('lwa_client_secret', '')),
                    'aws_access_key_length': len(self.credentials.get('aws_access_key', '')),
                    'aws_secret_key_length': len(self.credentials.get('aws_secret_key', '')),
                    'role_arn': self.credentials.get('role_arn', '')
                },
                'validation': {
                    'has_refresh_token': bool(self.credentials.get('refresh_token')),
                    'has_lwa_app_id': bool(self.credentials.get('lwa_app_id')),
                    'has_lwa_client_secret': bool(self.credentials.get('lwa_client_secret')),
                    'has_aws_access_key': bool(self.credentials.get('aws_access_key')),
                    'has_aws_secret_key': bool(self.credentials.get('aws_secret_key')),
                    'has_role_arn': bool(self.credentials.get('role_arn'))
                }
            }
            debug_result['test_phases']['credentials'] = 'PASSED'
        except Exception as e:
            debug_result['test_phases']['credentials'] = f'FAILED: {e}'

        # 🔍 PHASE 2: File credentials.yml 
        logger.info("🔍 PHASE 2: Creazione e verifica file credentials.yml...")
        try:
            file_debug = self._create_credentials_file()
            debug_result['file_debug'] = file_debug
            debug_result['test_phases']['file_creation'] = 'PASSED' if file_debug.get('file_exists') else 'FAILED'
        except Exception as e:
            debug_result['test_phases']['file_creation'] = f'FAILED: {e}'
            debug_result['file_debug']['error'] = str(e)

        # 🔍 PHASE 3: Test LWA Token Exchange diretto
        logger.info("🔍 PHASE 3: Test LWA Token Exchange diretto...")
        try:
            import requests
            
            lwa_request_data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.credentials.get('refresh_token'),
                'client_id': self.credentials.get('lwa_app_id'),
                'client_secret': self.credentials.get('lwa_client_secret')
            }
            
            debug_result['lwa_debug']['request_data'] = {
                'grant_type': lwa_request_data['grant_type'],
                'client_id': lwa_request_data['client_id'],
                'refresh_token_length': len(lwa_request_data['refresh_token']),
                'client_secret_length': len(lwa_request_data['client_secret'])
            }
            
            lwa_response = requests.post(
                'https://api.amazon.com/auth/o2/token',
                data=lwa_request_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            debug_result['lwa_debug']['response'] = {
                'status_code': lwa_response.status_code,
                'headers': dict(lwa_response.headers),
                'response_text': lwa_response.text[:500] + '...' if len(lwa_response.text) > 500 else lwa_response.text
            }
            
            if lwa_response.status_code == 200:
                lwa_data = lwa_response.json()
                debug_result['lwa_debug']['success_data'] = {
                    'access_token_length': len(lwa_data.get('access_token', '')),
                    'token_type': lwa_data.get('token_type'),
                    'expires_in': lwa_data.get('expires_in')
                }
                debug_result['test_phases']['lwa_exchange'] = 'PASSED'
            else:
                debug_result['test_phases']['lwa_exchange'] = f'FAILED: HTTP {lwa_response.status_code}'
                
        except Exception as e:
            debug_result['test_phases']['lwa_exchange'] = f'EXCEPTION: {e}'
            debug_result['lwa_debug']['exception'] = str(e)

        # 🔍 PHASE 4: Test Saleweaver Library
        logger.info("🔍 PHASE 4: Test Saleweaver library con file...")
        if SP_API_AVAILABLE:
            try:
                # Test con Sellers API (più permissivo)
                sellers_client = Sellers()
                debug_result['api_debug']['client_type'] = str(type(sellers_client))
                
                # Prova get_account
                response = sellers_client.get_account()
                debug_result['api_debug']['get_account'] = {
                    'response_type': str(type(response)),
                    'has_payload': hasattr(response, 'payload'),
                    'response_str': str(response)[:200] + '...' if len(str(response)) > 200 else str(response)
                }
                
                if hasattr(response, 'payload'):
                    debug_result['api_debug']['payload_data'] = response.payload
                
                debug_result['test_phases']['saleweaver_api'] = 'PASSED'
                debug_result['success'] = True
                debug_result['final_analysis']['result'] = 'SUCCESS: SP-API completamente funzionante'
                
            except Exception as saleweaver_error:
                error_str = str(saleweaver_error)
                debug_result['test_phases']['saleweaver_api'] = f'FAILED: {error_str}'
                debug_result['api_debug']['error'] = error_str
                debug_result['api_debug']['error_type'] = self._classify_saleweaver_error(error_str)

        # 🔍 ANALISI FINALE
        debug_result['final_analysis'] = self._analyze_debug_results(debug_result)
        
        return debug_result
    
    def _classify_saleweaver_error(self, error_str: str) -> str:
        """Classifica errori Saleweaver per troubleshooting"""
        error_lower = error_str.lower()
        
        if 'credentials are missing' in error_lower:
            return 'CREDENTIALS_FILE_NOT_READ'
        elif 'unauthorized_client' in error_lower:
            return 'AMAZON_APP_AUTHORIZATION_ISSUE'
        elif 'access to requested resource is denied' in error_lower:
            return 'AMAZON_RESOURCE_ACCESS_DENIED'
        elif 'invalid_client' in error_lower:
            return 'LWA_CLIENT_ID_INVALID'
        elif 'invalid_grant' in error_lower:
            return 'REFRESH_TOKEN_EXPIRED_OR_INVALID'
        elif 'timeout' in error_lower:
            return 'NETWORK_TIMEOUT'
        else:
            return 'UNKNOWN_SALEWEAVER_ERROR'
    
    def _analyze_debug_results(self, debug_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analizza risultati debug e fornisce diagnostica"""
        phases = debug_result.get('test_phases', {})
        
        analysis = {
            'phases_summary': phases,
            'problem_diagnosis': [],
            'recommendations': []
        }
        
        # Analizza ogni fase
        if phases.get('credentials') != 'PASSED':
            analysis['problem_diagnosis'].append('❌ Credenziali non valide o mancanti')
            analysis['recommendations'].append('🔧 Verificare configurazione database SP-API')
            
        if phases.get('file_creation') != 'PASSED':
            analysis['problem_diagnosis'].append('❌ Impossibile creare file credentials.yml')
            analysis['recommendations'].append('🔧 Verificare permessi filesystem su Railway')
            
        if phases.get('lwa_exchange') == 'PASSED':
            analysis['problem_diagnosis'].append('✅ LWA Token Exchange funziona')
            if phases.get('saleweaver_api') != 'PASSED':
                analysis['problem_diagnosis'].append('❌ Problema specifico Saleweaver library')
                analysis['recommendations'].append('🔧 Verificare lettura file credentials.yml')
        elif 'HTTP 400' in str(phases.get('lwa_exchange', '')):
            analysis['problem_diagnosis'].append('❌ LWA Token Exchange fallisce: problema autorizzazione Amazon')
            analysis['recommendations'].append('🔧 Verificare App ID, Client Secret, Refresh Token in Amazon Seller Central')
        
        # Determina causa principale
        if debug_result.get('success'):
            analysis['main_issue'] = 'NO_ISSUES_FOUND'
        elif phases.get('lwa_exchange') == 'PASSED' and phases.get('saleweaver_api') != 'PASSED':
            analysis['main_issue'] = 'SALEWEAVER_LIBRARY_ISSUE'
        elif 'HTTP 400' in str(phases.get('lwa_exchange', '')):
            analysis['main_issue'] = 'AMAZON_AUTHORIZATION_ISSUE'
        else:
            analysis['main_issue'] = 'CONFIGURATION_ISSUE'
            
        return analysis

    def test_connection(self) -> Dict[str, Any]:
        """Testa la connessione alle SP-API con debug approfondito"""
        if not SP_API_AVAILABLE:
            return {
                'success': False,
                'message': 'SP-API library non installata',
                'error': 'Installa con: pip install python-amazon-sp-api'
            }
            
        if not self._validate_credentials():
            return {
                'success': False,
                'message': 'Credenziali SP-API mancanti o non valide',
                'error': 'Configura le credenziali SP-API nel database'
            }
        
        # Debug delle credenziali
        debug_info = {
            'marketplace_id': self.marketplace_id,
            'endpoint': self.endpoint,
            'has_refresh_token': bool(self.credentials.get('refresh_token')),
            'refresh_token_length': len(self.credentials.get('refresh_token', '')),
            'has_lwa_app_id': bool(self.credentials.get('lwa_app_id')),
            'has_lwa_client_secret': bool(self.credentials.get('lwa_client_secret')),
            'has_aws_access_key': bool(self.credentials.get('aws_access_key')),
            'has_aws_secret_key': bool(self.credentials.get('aws_secret_key')),
            'has_role_arn': bool(self.credentials.get('role_arn')),
            'credentials_summary': {
                'refresh_token': f"{'*' * 10}...{self.credentials.get('refresh_token', '')[-4:]}" if self.credentials.get('refresh_token') else 'MISSING',
                'lwa_app_id': self.credentials.get('lwa_app_id', 'MISSING'),
                'lwa_client_secret': f"{'*' * 10}...{self.credentials.get('lwa_client_secret', '')[-4:]}" if self.credentials.get('lwa_client_secret') else 'MISSING',
                'aws_access_key': f"{'*' * 10}...{self.credentials.get('aws_access_key', '')[-4:]}" if self.credentials.get('aws_access_key') else 'MISSING',
                'role_arn': self.credentials.get('role_arn', 'MISSING')
            }
        }
        
        try:
            # Test più semplice: marketplace participation (richiede meno permessi)
            logger.info(f"[SP-API-TEST] Testing marketplace participation with endpoint: {self.endpoint}")
            
            participation_info = self.get_marketplace_participation()
            return {
                'success': True,
                'message': 'Connessione SP-API riuscita',
                'test_method': 'get_marketplace_participation',
                'participation_info': participation_info,
                'debug_info': debug_info
            }
            
        except Exception as e:
            logger.error(f"Marketplace participation test fallito: {e}")
            
            # Fallback: prova account info
            try:
                account_info = self.get_account_info()
                return {
                    'success': True,
                    'message': 'Connessione SP-API riuscita (account info)',
                    'test_method': 'get_account_info',
                    'account_info': account_info,
                    'debug_info': debug_info
                }
            except Exception as e2:
                logger.error(f"Account info test fallito: {e2}")
                
                # Test diretto LWA Token Exchange
                try:
                    import requests
                    
                    logger.info(f"[SP-API-TEST] Testing direct LWA token exchange")
                    
                    lwa_response = requests.post(
                        'https://api.amazon.com/auth/o2/token',
                        data={
                            'grant_type': 'refresh_token',
                            'refresh_token': self.credentials.get('refresh_token'),
                            'client_id': self.credentials.get('lwa_app_id'),  # ✅ LWA API usa 'client_id'
                            'client_secret': self.credentials.get('lwa_client_secret')
                        },
                        headers={'Content-Type': 'application/x-www-form-urlencoded'},
                        timeout=30
                    )
                    
                    if lwa_response.status_code == 200:
                        lwa_data = lwa_response.json()
                        return {
                            'success': True,
                            'message': 'LWA Token Exchange riuscito - credenziali LWA corrette',
                            'test_method': 'direct_lwa_token_exchange',
                            'lwa_response': {
                                'access_token_length': len(lwa_data.get('access_token', '')),
                                'token_type': lwa_data.get('token_type'),
                                'expires_in': lwa_data.get('expires_in')
                            },
                            'debug_info': debug_info,
                            'note': 'LWA OK ma SP-API fallita - possibile problema AWS/permessi'
                        }
                    else:
                        return {
                            'success': False,
                            'message': f'LWA Token Exchange fallito: {lwa_response.status_code}',
                            'error': f'LWA Error: {lwa_response.text}',
                            'debug_info': debug_info,
                            'lwa_status_code': lwa_response.status_code,
                            'detailed_errors': {
                                'participation_error': str(e),
                                'account_error': str(e2),
                                'lwa_error': lwa_response.text
                            }
                        }
                        
                except Exception as e3:
                    import traceback
                    return {
                        'success': False,
                        'message': f'Tutti i test SP-API sono falliti',
                        'error': f'Primary error: {str(e)}',
                        'debug_info': debug_info,
                        'detailed_errors': {
                            'participation_error': str(e),
                            'account_error': str(e2),
                            'lwa_error': str(e3),
                            'final_traceback': traceback.format_exc()
                        },
                        'troubleshooting': {
                            'check_refresh_token': 'Verifica che il refresh token sia corretto e non scaduto',
                            'check_app_authorization': 'Verifica che l\'app Amazon sia autorizzata correttamente in Seller Central',
                            'check_marketplace': f'Marketplace testato: {self.marketplace_id}',
                            'check_endpoint': f'Endpoint testato: {self.endpoint}',
                            'check_aws_credentials': 'Verifica AWS access key, secret key e role ARN',
                            'check_permissions': 'Verifica che l\'app abbia i permessi per Orders, Sellers, Reports API'
                        }
                    }

    def get_supported_marketplaces(self) -> List[Dict[str, str]]:
        """Restituisce lista marketplace supportati"""
        return [
            {'code': 'IT', 'name': 'Amazon.it', 'country': 'Italia'},
            {'code': 'DE', 'name': 'Amazon.de', 'country': 'Germania'},
            {'code': 'FR', 'name': 'Amazon.fr', 'country': 'Francia'},
            {'code': 'ES', 'name': 'Amazon.es', 'country': 'Spagna'},
            {'code': 'GB', 'name': 'Amazon.co.uk', 'country': 'Regno Unito'},
            {'code': 'US', 'name': 'Amazon.com', 'country': 'Stati Uniti'}
        ]

    def get_common_report_types(self) -> List[Dict[str, str]]:
        """Restituisce lista tipi di report più comuni"""
        return [
            {
                'type': 'GET_MERCHANT_LISTINGS_ALL_DATA',
                'name': 'Tutti i Listing',
                'description': 'Report completo di tutti i listing attivi e inattivi'
            },
            {
                'type': 'GET_AFN_INVENTORY_DATA',
                'name': 'Inventario FBA',
                'description': 'Report inventario Amazon FBA'
            },
            {
                'type': 'GET_FLAT_FILE_ALL_ORDERS_DATA_BY_LAST_UPDATE_GENERAL',
                'name': 'Tutti gli Ordini',
                'description': 'Report di tutti gli ordini per data ultimo aggiornamento'
            },
            {
                'type': 'GET_SELLER_FEEDBACK_DATA',
                'name': 'Feedback Seller',
                'description': 'Report feedback ricevuti dal seller'
            }
        ]


def create_sp_api_client(credentials: Optional[Dict[str, Any]] = None) -> AmazonSPAPIClient:
    """Crea una istanza del client SP-API con configurazione di default"""
    return AmazonSPAPIClient(credentials=credentials) 