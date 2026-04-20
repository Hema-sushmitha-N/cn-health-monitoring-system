#!/usr/bin/env python3
"""
Remote System Health Monitoring - Central Aggregation Server
Run this on Laptop 1 (Server)
"""

import socket
import ssl
import json
import threading
import time
import datetime
import statistics
import os
import struct
from collections import defaultdict, deque

# ─── CONFIG ────────────────────────────────────────────────────────────────────
UDP_HOST = "0.0.0.0"
UDP_PORT = 9000          # Clients send metrics here (UDP)
TCP_ALERT_PORT = 9001    # SSL/TLS alert channel (TCP)
BUFFER_SIZE = 4096

# Alert thresholds
THRESHOLDS = {
    "cpu_percent":     80.0,
    "memory_percent":  85.0,
    "disk_percent":    90.0,
    "net_bytes_sent":  100_000_000,   # 100 MB
}

# ─── SHARED STATE ──────────────────────────────────────────────────────────────
clients_data   = {}          # { node_id: latest_metric_dict }
clients_lock   = threading.Lock()
alert_log      = deque(maxlen=500)
alert_lock     = threading.Lock()
perf_stats     = defaultdict(list)   # { node_id: [latency_ms, ...] }
perf_lock      = threading.Lock()

# ─── HELPERS ───────────────────────────────────────────────────────────────────
def timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

def check_alerts(node_id, metrics):
    alerts = []
    for key, limit in THRESHOLDS.items():
        val = metrics.get(key)
        if val is not None and val > limit:
            msg = f"[ALERT] {node_id} | {key} = {val:.1f} > {limit}"
            alerts.append(msg)
    if alerts:
        with alert_lock:
            for a in alerts:
                alert_log.appendleft(f"[{timestamp()}] {a}")
                print(a)
    return alerts

# ─── UDP RECEIVER THREAD ───────────────────────────────────────────────────────
def udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_HOST, UDP_PORT))
    print(f"[UDP ] Listening on {UDP_HOST}:{UDP_PORT}")

    pkt_count = 0
    start_time = time.time()

    while True:
        try:
            raw, addr = sock.recvfrom(BUFFER_SIZE)
            recv_ts = time.time()

            try:
                data = json.loads(raw.decode())
            except json.JSONDecodeError:
                continue

            node_id = data.get("node_id", str(addr))
            sent_ts = data.get("timestamp", recv_ts)
            latency_ms = (recv_ts - sent_ts) * 1000

            data["recv_time"]   = recv_ts
            data["latency_ms"]  = round(latency_ms, 3)
            data["addr"]        = f"{addr[0]}:{addr[1]}"

            with clients_lock:
                clients_data[node_id] = data

            with perf_lock:
                perf_stats[node_id].append(latency_ms)

            check_alerts(node_id, data)

            pkt_count += 1
            elapsed = time.time() - start_time
            if elapsed >= 10:
                throughput = pkt_count / elapsed
                print(f"[PERF] Throughput: {throughput:.1f} pkt/s over {elapsed:.0f}s  (total={pkt_count})")
                pkt_count  = 0
                start_time = time.time()

        except Exception as e:
            print(f"[UDP ERR] {e}")

# ─── SSL/TLS ALERT SERVER (TCP) ────────────────────────────────────────────────
def handle_alert_client(conn, addr):
    """Serve dashboard/alert consumers over TLS."""
    print(f"[TLS ] Alert client connected: {addr}")
    try:
        while True:
            with clients_lock:
                snapshot = dict(clients_data)
            with alert_lock:
                recent_alerts = list(alert_log)[:20]
            with perf_lock:
                perf = {}
                for nid, lats in perf_stats.items():
                    if lats:
                        perf[nid] = {
                            "samples":   len(lats),
                            "avg_ms":    round(statistics.mean(lats), 3),
                            "min_ms":    round(min(lats), 3),
                            "max_ms":    round(max(lats), 3),
                            "stdev_ms":  round(statistics.stdev(lats), 3) if len(lats) > 1 else 0,
                        }

            payload = json.dumps({
                "clients":  snapshot,
                "alerts":   recent_alerts,
                "perf":     perf,
                "server_time": timestamp(),
            }).encode()

            length = struct.pack(">I", len(payload))
            conn.sendall(length + payload)
            time.sleep(1)
    except Exception:
        pass
    finally:
        conn.close()
        print(f"[TLS ] Alert client disconnected: {addr}")

def tls_alert_server():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain("server.crt", "server.key")

    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    raw_sock.bind((UDP_HOST, TCP_ALERT_PORT))
    raw_sock.listen(32)
    print(f"[TLS ] Alert server on port {TCP_ALERT_PORT}")

    while True:
        conn, addr = raw_sock.accept()

        try:
             tls_conn = ctx.wrap_socket(conn, server_side=True)
        except ssl.SSLError as e:
              print(f"[TLS ERR] {e}")
              conn.close()
              continue

        t = threading.Thread(target=handle_alert_client, args=(tls_conn, addr), daemon=True)
        t.start()
        
# ─── STATS PRINTER ─────────────────────────────────────────────────────────────
def stats_printer():
    while True:
        time.sleep(15)
        with clients_lock:
            snap = dict(clients_data)
        print(f"\n{'='*60}")
        print(f"  AGGREGATED SNAPSHOT  [{timestamp()}]  nodes={len(snap)}")
        print(f"{'='*60}")
        for nid, d in snap.items():
            age = round(time.time() - d.get("recv_time", time.time()), 1)
            print(f"  {nid:20s} | CPU:{d.get('cpu_percent',0):5.1f}%  "
                  f"MEM:{d.get('memory_percent',0):5.1f}%  "
                  f"DISK:{d.get('disk_percent',0):5.1f}%  "
                  f"lat:{d.get('latency_ms',0):6.2f}ms  age:{age}s")
        print()

# ─── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not (os.path.exists("server.crt") and os.path.exists("server.key")):
        print("[ERR] server.crt / server.key not found — run gen_certs.sh first")
        raise SystemExit(1)

    threads = [
        threading.Thread(target=udp_server,      daemon=True),
        threading.Thread(target=tls_alert_server, daemon=True),
        threading.Thread(target=stats_printer,   daemon=True),
    ]
    for t in threads:
        t.start()

    print("\n[SRV ] Server running. Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SRV ] Shutting down.")
