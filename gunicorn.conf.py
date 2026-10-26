"""
Gunicorn production configuration file.
Automatically loaded by Gunicorn when executing `gunicorn app:app`.
Binds dynamically to 0.0.0.0 and the port assigned by Render ($PORT).
"""
import os

# Port assigned dynamically by Render / cloud platform (defaults to 10000 or 8000)
port = os.getenv("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Worker processes (Render recommends 1-2 workers for standard instance sizes)
workers = int(os.getenv("WEB_CONCURRENCY", "2"))

# Worker timeout in seconds
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))

# Keepalive connections
keepalive = 5

# Logging to stdout / stderr for Render log streaming
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
