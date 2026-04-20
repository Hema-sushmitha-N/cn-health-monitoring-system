# Remote System Health Monitoring — Socket Programming Project
> Mini Project | UDP + SSL/TLS | Python | Multi-Client

---

## Architecture Overview

```
 Laptop 2 (Client NODE1)              Laptop 3 (Client NODE2)
 ┌─────────────────────┐              ┌─────────────────────┐
 │  client.py          │              │  client.py          │
 │  • psutil metrics   │              │  • psutil metrics   │
 │  • UDP sender  ─────┼─────────┐    │  • UDP sender  ─────┼──────┐
 │  • TLS receiver ◄───┼──────┐  │    │  • TLS receiver ◄───┼───┐  │
 └─────────────────────┘      │  │    └─────────────────────┘   │  │
                               │  │  UDP :9000 (metrics)         │  │
                               │  └──────────────────────────────┘  │
                               │                                      │
 Laptop 1 (Server)             │  TLS TCP :9001 (alerts/stats)        │
 ┌──────────────────────────────▼──────────────────────────────────▼──┤
 │  server.py                                                          │
 │  ┌────────────┐   ┌──────────────────┐   ┌───────────────────────┐ │
 │  │ UDP Recv   │──►│ Threshold Check  │──►│ TLS Alert Broadcast   │ │
 │  │ Thread     │   │ + Aggregator     │   │ Thread (per client)   │ │
 │  └────────────┘   └──────────────────┘   └───────────────────────┘ │
 └─────────────────────────────────────────────────────────────────────┘
```

**Protocol Choices:**
- **UDP** for metric reporting — lightweight, high-frequency, tolerates loss
- **SSL/TLS over TCP** for alerts/stats — reliable, authenticated, secure

---

## Files

| File             | Purpose                                      |
|------------------|----------------------------------------------|
| `server.py`      | Central aggregation server (Laptop 1)        |
| `client.py`      | Node client — sends UDP metrics (Laptop 2/3) |
| `stress_test.py` | Spawns N virtual clients for stress testing  |
| `dashboard.py`   | Live terminal dashboard (any machine)        |
| `gen_certs.sh`   | Generates self-signed TLS cert               |

---

## Step-by-Step Setup

### Prerequisites (all 3 laptops)

```bash
pip install psutil
```

---

### STEP 1 — Set up the Server (Laptop 1)

```bash
# 1. Create a working folder
mkdir monitor && cd monitor

# 2. Copy server.py, gen_certs.sh, dashboard.py into this folder

# 3. Generate TLS certificate
chmod +x gen_certs.sh
./gen_certs.sh
# This creates: server.key (private) and server.crt (share with clients)

# 4. Find your LAN IP address
ip addr show        # Linux/Mac
ipconfig            # Windows
# Look for something like 192.168.x.x

# 5. Start the server
python3 server.py
```

Expected output:
```
[UDP ] Listening on 0.0.0.0:9000
[TLS ] Alert server on port 9001
[SRV ] Server running. Press Ctrl+C to stop.
```

---

### STEP 2 — Transfer server.crt to Client Laptops

On Server (Laptop 1), share `server.crt` to both clients via:

```bash
# Option A: USB stick (copy the file)

# Option B: Python HTTP server (LAN)
python3 -m http.server 8080
# Then on each client: wget http://<SERVER_IP>:8080/server.crt
```

---

### STEP 3 — Run Client on Laptop 2

```bash
mkdir monitor && cd monitor
# Place: client.py, server.crt

python3 client.py --server <SERVER_IP> --node NODE1
# Replace <SERVER_IP> with Laptop 1's LAN IP, e.g. 192.168.1.10
```

Expected output:
```
[UDP ] Sending to 192.168.1.10:9000 as 'NODE1'
[TLS ] Connected to alert channel 192.168.1.10:9001
[UDP ] Sent 30 packets  | CPU: 34.2%  MEM: 61.1%  DISK: 48.5%
```

---

### STEP 4 — Run Client on Laptop 3

```bash
mkdir monitor && cd monitor
# Place: client.py, server.crt

python3 client.py --server <SERVER_IP> --node NODE2
```

---

### STEP 5 — View Live Dashboard (optional, any laptop)

```bash
python3 dashboard.py --server <SERVER_IP>
```

---

## Stress Test (Performance Evaluation)

Run from **any** laptop (clients or server):

```bash
# 20 virtual clients for 60 seconds
python3 stress_test.py --server <SERVER_IP> --clients 20 --duration 60

# For higher stress
python3 stress_test.py --server <SERVER_IP> --clients 100 --duration 120 --interval 0.2
```

### What it measures:
| Metric         | Description                                  |
|----------------|----------------------------------------------|
| **Throughput** | Packets per second delivered to server       |
| **Latency**    | Time for `sendto()` to complete (avg/p95/p99)|
| **Packet loss**| (sent − success) / sent × 100%               |
| **Stress load**| Scales with `--clients` and `--interval`     |

---

## Alert Thresholds

Defined in `server.py`:

| Metric           | Threshold |
|------------------|-----------|
| CPU usage        | > 80%     |
| Memory usage     | > 85%     |
| Disk usage       | > 90%     |
| Net bytes sent   | > 100 MB  |

Change in `server.py` → `THRESHOLDS` dict.

---

## Demo Script for Teacher (3 laptops)

1. **Server terminal** (Laptop 1): `python3 server.py`
2. **Dashboard terminal** (Laptop 1): `python3 dashboard.py --server localhost`
3. **Client** (Laptop 2): `python3 client.py --server <IP> --node NODE1`
4. **Client** (Laptop 3): `python3 client.py --server <IP> --node NODE2`
5. **Stress test** (Laptop 2): `python3 stress_test.py --server <IP> --clients 50 --duration 60`
   - Show live throughput numbers
   - Watch server dashboard spike
6. Manually set `cpu_percent > 80` in `stress_test.py` simulation to trigger an alert live

---

## GitHub Documentation Checklist

- [x] `README.md` — setup, architecture, commands
- [x] `server.py` — fully commented
- [x] `client.py` — fully commented
- [x] `stress_test.py` — performance benchmarking
- [x] `dashboard.py` — live terminal UI
- [x] `gen_certs.sh` — TLS cert generation

---

## Evaluation Mapping

| Rubric Component          | Where it's shown                                      |
|---------------------------|-------------------------------------------------------|
| Problem Definition        | This README + Architecture diagram                    |
| Core Socket Implementation| `server.py` UDP bind/recv; `client.py` sendto(); TLS wrap |
| Feature + SSL             | TLS alert channel; multi-client UDP aggregation       |
| Performance Evaluation    | `stress_test.py` — throughput, latency, loss          |
| Optimization & Fixes      | Reconnect logic, partial-read loop, error handling    |
| Final Demo + GitHub       | All 5 files + README on GitHub                        |
