import socket
import json

def do_something(x):
    return x * x
    

MASTER_IP = "192.168.137.1"  # master laptop IP
PORT = 5000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((MASTER_IP, PORT))
print("[+] Connected to master")

while True:
    data = client.recv(1024).decode('utf-8')
    if not data:
        break
    work = json.loads(data.strip())
    p = work["p"]
    result = do_something(p)
    send_data = {"id": work["id"], "p": p, "result": result}
    client.sendall(json.dumps(send_data).encode('utf-8') + b"\n")
