# code written by nathan shaw
import socket
import json
import threading


def lucas_lehmer(p):
    if p == 2:
        return True
    M = 2**p - 1
    s = 4
    for _ in range(p-2):
        s = (s*s - 2) % M
    return s == 0

work_queue = [{"id": i, "p": p} for i, p in enumerate(range(3, 31, 2))] # p values to be passed out
lock = threading.Lock()

def get_next_work():
    with lock:
        if work_queue:
            return work_queue.pop(0)
        return None

def handle_worker(conn, addr):
    print(f"[+] Connected: {addr}")
    while True:
        work = get_next_work()
        if not work:
            break
        # send work unit
        conn.sendall(json.dumps(work).encode('utf-8') + b"\n")
        # receive result
        try:
            data = conn.recv(1024).decode('utf-8')
            result = json.loads(data.strip())
            print(f"[RESULT] Worker {addr} -> {result}")
        except Exception as e:
            print(f"[ERROR] {addr}: {e}")
    conn.close()
    print(f"[-] Disconnected: {addr}")


HOST = '0.0.0.0'  # bind all local interfaces on hotspot
PORT = 5000

#start server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
print(f"[+] Server listening on {HOST}:{PORT}")

while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_worker, args=(conn, addr), daemon=True).start()
