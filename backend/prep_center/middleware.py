import logging

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('request_logger')

    def __call__(self, request):
        self.logger.info(f'[RequestLoggingMiddleware] {request.method} {request.path}')
        return self.get_response(request) 