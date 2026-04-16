import socket
import ssl
import threading
import time   # ✅ ADDED

HOST = '127.0.0.1'
PORT = 65432
CPU_THRESHOLD = 20.0
RAM_THRESHOLD = 70.0

# ✅ GLOBAL METRICS (ADDED)
total_requests = 0
total_latency = 0
start_time = time.time()
lock = threading.Lock()

def handle_client(conn, addr):
    print(f"[+] Secure connection established from {addr}")
    global total_requests, total_latency   # ✅ ADDED

    try:
        while True:
           data = conn.recv(1024).decode().strip()
            if not data:
                break
             start_req = time.time()

            print(f"[RAW DATA] {data}")

            try:
                parts = data.split(",")
                cpu_val = float(parts[0].split(":")[1])
                ram_val = float(parts[1].split(":")[1])
            except:
                print(f"[-] Invalid data format from {addr}: {data}")
                continue

            print(f"[DATA] {addr} → CPU: {cpu_val}%, RAM: {ram_val}%")

            if cpu_val < 50 and ram_val < 70:
                print(f"✅ STATUS NORMAL for {addr}")

            if cpu_val > CPU_THRESHOLD:
                print(f"⚠️ ALERT: High CPU usage on {addr}: {cpu_val}%")

            if ram_val > RAM_THRESHOLD:
                print(f"⚠️ ALERT: High RAM usage on {addr}: {ram_val}%")

            # ✅ END LATENCY TIMER
            end_req = time.time()
            latency = (end_req - start_req) * 1000  # ms
            print(f"Latency: {latency:.2f} ms")

            # ✅ UPDATE METRICS (THREAD SAFE)
            with lock:
                total_requests += 1
                total_latency += latency

                elapsed = time.time() - start_time

                if elapsed >= 5:  # print every 5 sec
                    throughput = total_requests / elapsed
                    avg_latency = total_latency / total_requests

                    print("\n--- Performance Stats ---")
                    print(f"Total Requests: {total_requests}")
                    print(f"Throughput: {throughput:.2f} req/sec")
                    print(f"Avg Latency: {avg_latency:.2f} ms\n")

                    # reset counters
                    total_requests = 0
                    total_latency = 0
                    globals()['start_time'] = time.time()

    except Exception as e:
        print(f"[-] Connection with {addr} closed: {e}")
    finally:
        conn.close()

def start_server():
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")

    bind_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bind_socket.bind((HOST, PORT))
    bind_socket.listen(5)

    print(f"[*] Aggregator Server listening on {PORT} (SSL/TLS Enabled)...")

    while True:
        newsocket, fromaddr = bind_socket.accept()
        conn = context.wrap_socket(newsocket, server_side=True)

        thread = threading.Thread(target=handle_client, args=(conn, fromaddr))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    start_server()
