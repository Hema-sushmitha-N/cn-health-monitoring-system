#!/bin/bash
# gen_certs.sh — Generate self-signed TLS cert for the monitoring server
# Run ONCE on the server machine, then copy server.crt to all client machines

set -e

echo "Generating self-signed TLS certificate..."

# Change CN to your server's actual LAN IP if needed
SERVER_IP="0.0.0.0"

openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout server.key \
    -out    server.crt \
    -days   365 \
    -subj   "/CN=monitor-server" \
    -addext "subjectAltName=IP:127.0.0.1,IP:${SERVER_IP}"

echo ""
echo "Done! Files created:"
echo "  server.key  (KEEP PRIVATE — server only)"
echo "  server.crt  (copy this to ALL client machines)"
echo ""
echo "Next steps:"
echo "  1. Copy server.crt to each client laptop (same folder as client.py)"
echo "  2. Run:  python3 server.py"
