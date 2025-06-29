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

    def _set_env_vars(self) -> None:
        """
        Imposta le environment variables usando i nomi che la libreria effettivamente cerca
        Basato sull'errore: "Credentials are missing: lwa_app_id, lwa_client_secret"
        """
        import os
        
        # Imposta environment variables con i nomi che la libreria python-amazon-sp-api cerca
        os.environ['refresh_token'] = self.credentials.get('refresh_token', '')
        os.environ['lwa_app_id'] = self.credentials.get('lwa_app_id', '')
        os.environ['lwa_client_secret'] = self.credentials.get('lwa_client_secret', '')
        os.environ['aws_access_key'] = self.credentials.get('aws_access_key', '')
        os.environ['aws_secret_key'] = self.credentials.get('aws_secret_key', '')
        os.environ['role_arn'] = self.credentials.get('role_arn', '')
        
        # Anche i nomi "ufficiali" per compatibilità
        os.environ['SP_API_REFRESH_TOKEN'] = self.credentials.get('refresh_token', '')
        os.environ['SP_API_CLIENT_ID'] = self.credentials.get('lwa_app_id', '')
        os.environ['SP_API_CLIENT_SECRET'] = self.credentials.get('lwa_client_secret', '')
        os.environ['SP_API_AWS_ACCESS_KEY'] = self.credentials.get('aws_access_key', '')
        os.environ['SP_API_AWS_SECRET_KEY'] = self.credentials.get('aws_secret_key', '')
        os.environ['SP_API_ROLE_ARN'] = self.credentials.get('role_arn', '')
        os.environ['SP_API_ENDPOINT'] = self.endpoint
        
        logger.info(f"Environment variables SP-API impostate - lwa_app_id: {self.credentials.get('lwa_app_id', 'MISSING')[:20]}...")



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
        """Recupera ordini dal marketplace Amazon"""
        if not SP_API_AVAILABLE:
            raise ImportError("SP-API library not available")
            
        try:
            # Usa data di default se non specificata (ultimi 7 giorni)
            if not created_after and not last_updated_after:
                created_after = datetime.utcnow() - timedelta(days=7)

            # Prepara parametri
            params = {
                'MaxResultsPerPage': max_results_per_page,
                'MarketplaceIds': [self.marketplace_id]
            }

            if created_after:
                params['CreatedAfter'] = created_after.isoformat()
            if created_before:
                params['CreatedBefore'] = created_before.isoformat()
            if last_updated_after:
                params['LastUpdatedAfter'] = last_updated_after.isoformat()

            # Imposta environment variables secondo guida ufficiale (metodo raccomandato)
            self._set_env_vars()
            orders_client = Orders()
            response = orders_client.get_orders(**params)
            
            logger.info(f"Recuperati {len(response.payload.get('Orders', []))} ordini")
            return response.payload

        except Exception as e:
            self._handle_api_error(e, "get_orders")

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Recupera dettagli di un singolo ordine"""
        if not SP_API_AVAILABLE:
            raise ImportError("SP-API library not available")
            
        try:
            self._set_env_vars()
            orders_client = Orders()
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
            self._set_env_vars()
            orders_client = Orders()
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

            self._set_env_vars()
            inventories_client = Inventories()
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

            self._set_env_vars()
            reports_client = Reports()
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
            self._set_env_vars()
            reports_client = Reports()
            response = reports_client.get_report(report_id)
            
            logger.info(f"Recuperato report {report_id}")
            return response.payload

        except Exception as e:
            self._handle_api_error(e, f"get_report({report_id})")

    # =============================================================================
    # SELLER API
    # =============================================================================

    def get_account_info(self) -> Dict[str, Any]:
        """Recupera informazioni account seller"""
        if not SP_API_AVAILABLE:
            raise ImportError("SP-API library not available")
            
        try:
            self._set_env_vars()
            sellers_client = Sellers()
            response = sellers_client.get_account()
            
            logger.info("Recuperate info account seller")
            return response.payload

        except Exception as e:
            self._handle_api_error(e, "get_account_info")

    def get_marketplace_participation(self) -> Dict[str, Any]:
        """Recupera informazioni partecipazione marketplace"""
        if not SP_API_AVAILABLE:
            raise ImportError("SP-API library not available")
            
        try:
            self._set_env_vars()
            sellers_client = Sellers()
            response = sellers_client.get_marketplace_participation()
            
            logger.info("Recuperate info marketplace participation")
            return response.payload

        except Exception as e:
            self._handle_api_error(e, "get_marketplace_participation")

    # =============================================================================
    # UTILITY METHODS
    # =============================================================================

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
                            'client_id': self.credentials.get('lwa_app_id'),  # Note: this stays as lwa_app_id for LWA API
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