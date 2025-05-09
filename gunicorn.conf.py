import multiprocessing
import os

# Numero di worker processi
workers = multiprocessing.cpu_count() * 2 + 1

# Timeout aumentato a 300 secondi (5 minuti)
timeout = 300

# Keep-alive timeout
keepalive = 65

# Worker class
worker_class = 'gevent'

# Max requests per worker prima del riavvio
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Preload app
preload_app = True

# Worker connections
worker_connections = 1000

# Graceful timeout
graceful_timeout = 120

# Forwarded allow ips
forwarded_allow_ips = '*'

# SSL
keyfile = None
certfile = None 