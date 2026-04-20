#!/usr/bin/env python3
"""
Remote System Health Monitoring - Client Node
Run this on Laptop 2 and Laptop 3 (Clients)

Usage:
    python3 client.py --server <SERVER_IP> --node NODE1
    python3 client.py --server <SERVER_IP> --node NODE2
"""

import socket
import ssl
import json
import threading
import time
import argparse
import struct
import os

# Try psutil; graceful fallback for demo without real hardware
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[WARN] psutil not installed. Using simulated metrics.")
    print("       Install with: pip install psutil")

# ─── CONFIG ────────────────────────────────────────────────────────────────────
UDP_PORT       = 9000
TCP_ALERT_PORT = 9001
SEND_INTERVAL  = 1.0    # seconds between metric reports

# ─── METRIC COLLECTION ─────────────────────────────────────────────────────────
_sim_state = {"cpu": 30.0, "mem": 50.0}

def collect_metrics():
    if HAS_PSUTIL:
        net = psutil.net_io_counters()
        disk = psutil.disk_usage("/")
        return {
            "cpu_percent":    psutil.cpu_percent(interval=0.2),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent":   disk.percent,
            "net_bytes_sent": net.bytes_sent,
            "net_bytes_recv": net.bytes_recv,
        }
    else:
        import random, math
        t = time.time()
        # Simulate fluctuating values
        _sim_state["cpu"]  = max(5,  min(100, _sim_state["cpu"]  + random.uniform(-5, 6)))
        _sim_state["mem"]  = max(20, min(100, _sim_state["mem"]  + random.uniform(-2, 2)))
        return {
            "cpu_percent":    round(_sim_state["cpu"], 1),
            "memory_percent": round(_sim_state["mem"], 1),
            "disk_percent":   round(45 + 5 * math.sin(t / 30), 1),
            "net_bytes_sent": int(t * 5000) % 200_000_000,
            "net_bytes_recv": int(t * 8000) % 300_000_000,
        }

# ─── UDP SENDER ────────────────────────────────────────────────────────────────
def udp_sender(server_ip, node_id, stop_event):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[UDP ] Sending to {server_ip}:{UDP_PORT} as '{node_id}'")
    sent = 0

    while not stop_event.is_set():
        loop_start = time.time()
        metrics = collect_metrics()
        metrics["node_id"]   = node_id
        metrics["timestamp"] = time.time()

        payload = json.dumps(metrics).encode()
        try:
            sock.sendto(payload, (server_ip, UDP_PORT))
            sent += 1
            if sent % 30 == 0:
                print(f"[UDP ] Sent {sent} packets  | CPU:{metrics['cpu_percent']:.1f}%  "
                      f"MEM:{metrics['memory_percent']:.1f}%  "
                      f"DISK:{metrics['disk_percent']:.1f}%")
        except Exception as e:
            print(f"[UDP ERR] {e}")

        elapsed = time.time() - loop_start
        time.sleep(max(0, SEND_INTERVAL - elapsed))

    sock.close()

# ─── TLS ALERT RECEIVER ────────────────────────────────────────────────────────
def tls_alert_receiver(server_ip, node_id, stop_event):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations("server.crt")

    while not stop_event.is_set():
        try:
            raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn = ctx.wrap_socket(raw, server_hostname=server_ip)
            conn.connect((server_ip, TCP_ALERT_PORT))
            print(f"[TLS ] Connected to alert channel {server_ip}:{TCP_ALERT_PORT}")

            while not stop_event.is_set():
                # Read 4-byte length prefix
                hdr = b""
                while len(hdr) < 4:
                    chunk = conn.recv(4 - len(hdr))
                    if not chunk:
                        raise ConnectionError("Server closed connection")
                    hdr += chunk

                length = struct.unpack(">I", hdr)[0]
                body = b""
                while len(body) < length:
                    chunk = conn.recv(min(4096, length - len(body)))
                    if not chunk:
                        raise ConnectionError("Truncated payload")
                    body += chunk

                data = json.loads(body.decode())
                my_data = data["clients"].get(node_id, {})
                alerts  = [a for a in data.get("alerts", []) if node_id in a]
                perf    = data.get("perf", {}).get(node_id, {})

                if alerts:
                    print(f"\n{'!'*50}")
                    for a in alerts[:5]:
                        print(f"  {a}")
                    print(f"{'!'*50}\n")

                if perf:
                    print(f"[PERF] {node_id}: avg_lat={perf.get('avg_ms',0):.2f}ms  "
                          f"max={perf.get('max_ms',0):.2f}ms  "
                          f"samples={perf.get('samples',0)}")

        except Exception as e:
            print(f"[TLS ERR] {e} — retrying in 3s")
            try: conn.close()
            except: pass
            time.sleep(3)

# ─── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Health Monitor Client")
    parser.add_argument("--server", required=True, help="Server IP address")
    parser.add_argument("--node",   default="node-default", help="Unique node name")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="Metric send interval in seconds (default 1.0)")
    args = parser.parse_args()

    SEND_INTERVAL = args.interval

    if not os.path.exists("server.crt"):
        print("[ERR] server.crt not found — copy it from the server machine")
        raise SystemExit(1)

    stop = threading.Event()
    threads = [
        threading.Thread(target=udp_sender,
                         args=(args.server, args.node, stop), daemon=True),
        threading.Thread(target=tls_alert_receiver,
                         args=(args.server, args.node, stop), daemon=True),
    ]
    for t in threads:
        t.start()

    print(f"[CLI ] Client '{args.node}' running. Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[CLI ] Stopping.")
        stop.set()
        time.sleep(1)
