import socket
import ssl
import threading

# Configuration
HOST = '127.0.0.1'
PORT = 65432
CPU_THRESHOLD = 80.0  # Alert threshold

def handle_client(conn, addr):
    print(f"[+] Secure connection established from {addr}")
    try:
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break
            
            # Data format expected: "CPU:10.5,RAM:45.2"
            print(f"Metrics from {addr}: {data}")
            
            # Simple threshold logic for alerts
            metrics = dict(item.split(":") for item in data.split(","))
            cpu_val = float(metrics['CPU'])
            if cpu_val > CPU_THRESHOLD:
                print(f"!! ALERT: High CPU usage on {addr}: {cpu_val}% !!")
                
    except Exception as e:
        print(f"[-] Connection with {addr} closed: {e}")
    finally:
        conn.close()

def start_server():
    # Setup SSL Context for secure communication 
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")

    # Low-level socket creation 
    bind_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bind_socket.bind((HOST, PORT))
    bind_socket.listen(5)
    print(f"[*] Aggregator Server listening on {PORT} (SSL/TLS Enabled)...")

    while True:
        # Accept and wrap the socket in SSL
        newsocket, fromaddr = bind_socket.accept()
        conn = context.wrap_socket(newsocket, server_side=True)
        
        # Handle multiple clients using threading 
        thread = threading.Thread(target=handle_client, args=(conn, fromaddr))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    start_server()