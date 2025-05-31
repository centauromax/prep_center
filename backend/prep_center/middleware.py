import logging
from django.http import HttpResponse

logger = logging.getLogger('prep_center')

class DomainDebugMiddleware:
    """
    Middleware per debuggare le richieste da domini diversi.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        path = request.get_full_path()
        
        logger.info(f"[DomainDebug] Host: {host}, Path: {path}")
        
        # Se arriva da apppc, logga tutto e fai redirect
        if host == 'apppc.fbaprepcenteritaly.com':
            logger.info(f"[DomainDebug] Richiesta da apppc: {path}")
            
            # Se non è picture_check, fai redirect a backend
            if not path.startswith('/picture_check'):
                redirect_url = f'https://backend.fbaprepcenteritaly.com{path}'
                logger.info(f"[DomainDebug] Redirect a: {redirect_url}")
                
                # Restituisci una risposta di debug invece del redirect per ora
                return HttpResponse(f"""
                    <h1>Debug Domain Redirect</h1>
                    <p><strong>Host originale:</strong> {host}</p>
                    <p><strong>Path:</strong> {path}</p>
                    <p><strong>Redirect URL:</strong> {redirect_url}</p>
                    <p><a href="{redirect_url}">Clicca qui per andare alla pagina corretta</a></p>
                """, content_type='text/html')
        
        response = self.get_response(request)
        return response 