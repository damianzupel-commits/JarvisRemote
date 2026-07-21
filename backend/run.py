import uvicorn

from app.config import settings

if __name__ == "__main__":
    ssl_kwargs = {}
    if settings.tls_enabled:
        # Preparado pero apagado por default — ver el comentario en app/config.py
        # y backend/certs/README.md antes de activar esto con TLS_ENABLED=true.
        ssl_kwargs = {
            "ssl_certfile": settings.tls_cert_path,
            "ssl_keyfile": settings.tls_key_path,
        }

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False, **ssl_kwargs)
