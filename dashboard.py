#!/usr/bin/env python3
"""
Terminal Dashboard — Connect to server over TLS and display live metrics.
Run on any laptop (including the server itself).

Usage:
    python3 dashboard.py --server <SERVER_IP>
"""

import socket
import ssl
import json
import struct
import time
import os
import argparse

TCP_ALERT_PORT = 9001

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def bar(val, max_val=100, width=20):
    filled = int((val / max_val) * width)
    color = GREEN if val < 70 else (YELLOW if val < 85 else RED)
    return f"{color}{'█' * filled}{'░' * (width - filled)}{RESET} {val:5.1f}%"

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def render(data):
    clear()
    clients = data.get("clients", {})
    alerts  = data.get("alerts", [])
    perf    = data.get("perf", {})
    srv_ts  = data.get("server_time", "?")

    print(f"{BOLD}{CYAN}╔══════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║   SYSTEM HEALTH MONITOR — {srv_ts:>10s}               ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════╝{RESET}")
    print(f"  Nodes online: {BOLD}{len(clients)}{RESET}\n")

    for nid, d in clients.items():
        age = round(time.time() - d.get("recv_time", time.time()), 1)
        lat = d.get("latency_ms", 0)
        status = f"{GREEN}●{RESET}" if age < 5 else f"{RED}●{RESET}"

        print(f"  {status} {BOLD}{nid:20s}{RESET}  [{d.get('addr','?')}]  age:{age:.1f}s  lat:{lat:.2f}ms")
        print(f"    CPU  {bar(d.get('cpu_percent', 0))}")
        print(f"    MEM  {bar(d.get('memory_percent', 0))}")
        print(f"    DISK {bar(d.get('disk_percent', 0))}")

        p = perf.get(nid, {})
        if p:
            print(f"    {CYAN}PERF avg={p.get('avg_ms',0):.2f}ms  "
                  f"p95≈max={p.get('max_ms',0):.2f}ms  "
                  f"samples={p.get('samples',0)}{RESET}")
        print()

    if alerts:
        print(f"  {BOLD}{RED}── RECENT ALERTS ──────────────────────────────{RESET}")
        for a in alerts[:8]:
            print(f"  {RED}{a}{RESET}")
        print()

    print(f"  {CYAN}Press Ctrl+C to exit{RESET}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    args = parser.parse_args()

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations("server.crt")

    print(f"Connecting to {args.server}:{TCP_ALERT_PORT} ...")
    while True:
        try:
            raw  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn = ctx.wrap_socket(raw, server_hostname=args.server)
            conn.connect((args.server, TCP_ALERT_PORT))

            while True:
                hdr = b""
                while len(hdr) < 4:
                    c = conn.recv(4 - len(hdr))
                    if not c:
                        raise ConnectionError
                    hdr += c
                length = struct.unpack(">I", hdr)[0]
                body = b""
                while len(body) < length:
                    c = conn.recv(min(4096, length - len(body)))
                    if not c:
                        raise ConnectionError
                    body += c
                render(json.loads(body.decode()))

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Reconnecting... ({e})")
            try: conn.close()
            except: pass
            time.sleep(2)

if __name__ == "__main__":
    main()
