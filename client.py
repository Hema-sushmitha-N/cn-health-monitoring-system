import socket
import ssl
import time
import psutil

# Configuration
HOST = '127.0.0.1'
PORT = 65432

def start_client():
    # Setup Secure Context [cite: 8]
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # Using self-signed certificates

    # Create and wrap the socket 
    raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    secure_socket = context.wrap_socket(raw_socket, server_hostname=HOST)
    
    try:
        secure_socket.connect((HOST, PORT))
        print(f"[+] Connected to Aggregator at {HOST}:{PORT}")

        while True:
            # Collect metrics
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            
            # Send metrics over secure socket
            message = f"CPU:{cpu},RAM:{ram}"
            secure_socket.sendall(message.encode())
            
            time.sleep(5)  # Report every 5 seconds
    except Exception as e:
        print(f"[-] Connection Error: {e}")
    finally:
        secure_socket.close()

if __name__ == "__main__":
    start_client()