import socket
import ssl
import threading

HOST = '127.0.0.1'
PORT = 65432
CPU_THRESHOLD = 20.0
RAM_THRESHOLD = 70.0

def handle_client(conn, addr):
    print(f"[+] Secure connection established from {addr}")
    try:
        while True:
            data = conn.recv(1024).decode().strip()
            if not data:
                break

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