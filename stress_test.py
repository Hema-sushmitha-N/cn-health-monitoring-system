#!/usr/bin/env python3
"""
Stress Test — Simulates N virtual clients from a single machine.
Measures throughput, latency distribution, and packet loss.

Usage:
    python3 stress_test.py --server <SERVER_IP> --clients 50 --duration 60
"""

import socket
import json
import time
import threading
import argparse
import random
import statistics
from collections import defaultdict

# ─── CONFIG ────────────────────────────────────────────────────────────────────
UDP_PORT = 9000

# ─── SHARED RESULTS ────────────────────────────────────────────────────────────
results_lock    = threading.Lock()
sent_total      = 0
success_total   = 0
latencies_ms    = []
errors_by_type  = defaultdict(int)
active_clients  = 0

# ─── VIRTUAL CLIENT ────────────────────────────────────────────────────────────
def virtual_client(server_ip, node_id, interval, duration, start_barrier):
    global sent_total, success_total, active_clients

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)

    start_barrier.wait()   # all clients launch together

    deadline = time.time() + duration
    local_sent = 0
    local_ok   = 0
    local_lats = []

    with results_lock:
        active_clients += 1

    while time.time() < deadline:
        ts = time.time()
        payload = json.dumps({
            "node_id":        node_id,
            "timestamp":      ts,
            "cpu_percent":    random.uniform(10, 95),
            "memory_percent": random.uniform(30, 90),
            "disk_percent":   random.uniform(20, 85),
            "net_bytes_sent": random.randint(0, 200_000_000),
            "net_bytes_recv": random.randint(0, 300_000_000),
        }).encode()

        send_ts = time.time()
        try:
            sock.sendto(payload, (server_ip, UDP_PORT))
            local_sent += 1
            local_ok   += 1
            local_lats.append((time.time() - send_ts) * 1000)
        except Exception as e:
            local_sent += 1
            with results_lock:
                errors_by_type[type(e).__name__] += 1

        time.sleep(interval)

    sock.close()

    with results_lock:
        sent_total    += local_sent
        success_total += local_ok
        latencies_ms.extend(local_lats)
        active_clients -= 1

# ─── RESULT PRINTER ────────────────────────────────────────────────────────────
def live_monitor(num_clients, duration):
    start = time.time()
    while time.time() - start < duration + 2:
        time.sleep(5)
        elapsed = time.time() - start
        with results_lock:
            s = sent_total
            ok = success_total
            lats = list(latencies_ms)
            ac = active_clients

        rate = s / elapsed if elapsed > 0 else 0
        loss = ((s - ok) / s * 100) if s > 0 else 0
        avg  = statistics.mean(lats)    if lats else 0
        p95  = sorted(lats)[int(len(lats)*0.95)] if len(lats) > 20 else 0
        mx   = max(lats) if lats else 0

        print(f"\n[{elapsed:5.0f}s] active={ac}/{num_clients}  "
              f"sent={s}  rate={rate:.1f}pkt/s  loss={loss:.2f}%")
        print(f"         latency: avg={avg:.3f}ms  p95={p95:.3f}ms  max={mx:.3f}ms")

# ─── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test — Virtual UDP Clients")
    parser.add_argument("--server",   required=True)
    parser.add_argument("--clients",  type=int,   default=20,  help="Number of virtual clients")
    parser.add_argument("--duration", type=int,   default=60,  help="Test duration in seconds")
    parser.add_argument("--interval", type=float, default=0.5, help="Send interval per client (s)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  STRESS TEST")
    print(f"  Server   : {args.server}:{UDP_PORT}")
    print(f"  Clients  : {args.clients}")
    print(f"  Duration : {args.duration}s")
    print(f"  Interval : {args.interval}s/client")
    print(f"  Max rate : ~{args.clients / args.interval:.0f} pkt/s")
    print(f"{'='*60}\n")

    barrier = threading.Barrier(args.clients + 1)

    threads = []
    for i in range(args.clients):
        nid = f"stress-node-{i:04d}"
        t = threading.Thread(
            target=virtual_client,
            args=(args.server, nid, args.interval, args.duration, barrier),
            daemon=True,
        )
        threads.append(t)
        t.start()

    mon = threading.Thread(target=live_monitor, args=(args.clients, args.duration), daemon=True)
    mon.start()

    print(f"Launching {args.clients} clients simultaneously...")
    start_ts = time.time()
    barrier.wait()
    print("All clients running!\n")

    for t in threads:
        t.join()

    total_time = time.time() - start_ts
    print(f"\n{'='*60}")
    print(f"  FINAL RESULTS")
    print(f"{'='*60}")
    print(f"  Duration       : {total_time:.1f}s")
    print(f"  Total sent     : {sent_total}")
    print(f"  Successful     : {success_total}")
    print(f"  Packet loss    : {(sent_total - success_total)/max(1,sent_total)*100:.2f}%")
    print(f"  Avg throughput : {sent_total/total_time:.1f} pkt/s")

    if latencies_ms:
        lats_sorted = sorted(latencies_ms)
        print(f"  Latency avg    : {statistics.mean(latencies_ms):.3f} ms")
        print(f"  Latency median : {statistics.median(latencies_ms):.3f} ms")
        print(f"  Latency p95    : {lats_sorted[int(len(lats_sorted)*0.95)]:.3f} ms")
        print(f"  Latency p99    : {lats_sorted[int(len(lats_sorted)*0.99)]:.3f} ms")
        print(f"  Latency max    : {max(latencies_ms):.3f} ms")

    if errors_by_type:
        print(f"\n  Errors by type:")
        for k, v in errors_by_type.items():
            print(f"    {k}: {v}")
    print(f"{'='*60}\n")
