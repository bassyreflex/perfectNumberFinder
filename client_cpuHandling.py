import socket
import json
import threading
import math
import psutil
import time

SERVER_IP = "192.168.1.28"
PORT = 5000

TARGET_CPU = 60      # target cpu %
MAX_THREADS = 64     # max threads allowed
MIN_THREADS = 1      # minimum threads allowed

workers = []         # list of worker thread objects
workers_lock = threading.Lock()
running = True


def lucas_lehmer(p):
    if p == 2:
        return True
    M = (1 << p) - 1
    s = 4
    for _ in range(p - 2):
        s = (s * s - 2) % M
    return s == 0


class WorkerThread(threading.Thread):
    def __init__(self, wid):
        super().__init__(daemon=True)
        self.wid = wid
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def run(self):
        try:
            self.sock.connect((SERVER_IP, PORT))
        except Exception as e:
            print(f"[Thread {self.wid}] Failed to connect: {e}")
            return

        buffer = ""

        while self.running:
            try:
                data = self.sock.recv(4096).decode("utf-8")
                if not data:
                    break

                buffer += data
                if "\n" not in buffer:
                    continue

                line, buffer = buffer.split("\n", 1)
                job = json.loads(line.strip())
                p = job["p"]

                start = time.time()
                is_mers = lucas_lehmer(p)
                duration = time.time() - start

                cpu_now = psutil.cpu_percent(interval=None)

                result = {
                    "p": p,
                    "is_mersenne": is_mers,
                    "duration": duration,
                    "thread_id": self.wid,
                    "threads_running": len(workers),
                    "cpu": cpu_now
                }

                self.sock.sendall((json.dumps(result) + "\n").encode())

            except:
                break

        self.sock.close()

    def stop(self):
        self.running = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            self.sock.close()
        except:
            pass


def add_worker():
    with workers_lock:
        wid = len(workers)
        w = WorkerThread(wid)
        workers.append(w)
        w.start()
        print(f"[+] Started worker thread {wid}")


def remove_worker():
    with workers_lock:
        if workers:
            w = workers.pop()
            print(f"[-] Stopping worker thread {w.wid}")
            w.stop()


def cpu_manager():
    """Scales thread count to keep CPU near target."""
    global workers

    while running:
        cpu = psutil.cpu_percent(interval=1)  # non-blocking
        thread_count = len(workers)

        # too low CPU → add worker
        if cpu < TARGET_CPU - 10 and thread_count < MAX_THREADS:
            add_worker()

        # too high CPU → remove worker
        elif cpu > TARGET_CPU + 10 and thread_count > MIN_THREADS:
            remove_worker()

        # report status
        print(f"[CPU Manager] CPU={cpu:.1f}% Threads={thread_count}")

        time.sleep(1)


# -------------------------------------------------------
# STARTUP
# -------------------------------------------------------

# start with one worker
add_worker()

# start the scaling manager
mgr = threading.Thread(target=cpu_manager, daemon=True)
mgr.start()

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("Shutting down...")

    running = False
    with workers_lock:
        for w in workers:
            w.stop()

    time.sleep(1)
