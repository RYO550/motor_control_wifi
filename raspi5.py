# raspi5_tcp_persistent_sender.py

import socket
import time

pico_ip = '192.168.11.2'  # Pico W の IP
port = 5000

# 一度だけ接続を確立
s = socket.socket()
s.connect((pico_ip, port))
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # 遅延削減オプション

angle = 0

try:
    while True:
        message = f"{angle}\n"
        s.send(message.encode())
        print(f"Sent: {angle}")
        angle += 90
        time.sleep(1)
except Exception as e:
    print("Error:", e)
    s.close()
