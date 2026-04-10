import socket
import psutil
import time

HOST = '127.0.0.1'
PORT = 65432

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

while True:
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent

    message = f"CPU:{cpu},RAM:{ram}"
    sock.sendto(message.encode(), (HOST, PORT))

    time.sleep(2)