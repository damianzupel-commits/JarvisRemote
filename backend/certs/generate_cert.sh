#!/usr/bin/env bash
# Genera (o regenera) el certificado self-signed que usa el backend cuando
# TLS_ENABLED=true (ver app/config.py y run.py). Correr desde Git Bash.
#
# Regenerar hace falta si:
# - La IP de Tailscale o la de LAN de la PC cambiaron (quedaron hardcodeadas
#   como Subject Alternative Names abajo).
# - El certificado venció (dura 10 años desde que se generó).
#
# El resultado (cert.pem, key.pem) NO se commitea (ver .gitignore) — cert.pem
# no es secreto en sí, pero se regenera fácil y no tiene sentido versionarlo.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Ajustar estas IPs si cambiaron desde la última vez (ver `tailscale status` y
# `ipconfig` / GET /api/health -> network_candidates para los valores actuales).
TAILSCALE_IP="100.116.29.74"
LAN_IP="192.168.1.4"

openssl req -x509 -newkey rsa:2048 \
  -keyout key.pem \
  -out cert.pem \
  -days 3650 -nodes \
  -subj "//CN=jarvisremote-backend" \
  -addext "subjectAltName=IP:${TAILSCALE_IP},IP:${LAN_IP},IP:127.0.0.1,DNS:localhost"

echo "Generado: $DIR/cert.pem y $DIR/key.pem"
openssl x509 -in cert.pem -noout -subject -dates -ext subjectAltName
