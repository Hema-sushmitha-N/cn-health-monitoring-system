import socket

HOST = '127.0.0.1'
PORT = 65432

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print("[*] UDP Server listening...")

while True:
    data, addr = sock.recvfrom(1024)
    message = data.decode()

    print(f"[DATA] {addr} → {message}")