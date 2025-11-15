# Dynamic Multiprocessing Client (Windows-safe)
# Code by Nathan Shaw

import socket
import json
import multiprocessing as mp
import psutil
import time
import math
import os

# ---------------------------
# LUCAS-LEHMER FUNCTION
# ---------------------------

def lucas_lehmer(p):
    if p == 2:
        return True
    M = (1 << p) - 1
    s = 4
    for _ in range(p - 2):
        s = (s * s - 2) % M
    return s == 0

# ---------------------------
# WORKER PROCESS FUNCTION
# ---------------------------

def worker_process(worker_id, running_flag, server_ip, port, process_count_proxy):
    """
    Each worker opens its own socket connection to the server.
    Reports p, result, CPU usage, worker ID, and number of processes.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((server_ip, port))
        print(f"[+] Worker {worker_id} connected")
    except Exception as e:
        print(f"[!] Worker {worker_id} failed to connect: {e}")
        return

    buffer = ""

    while running_flag.value:
        try:
            data = sock.recv(4096).decode("utf-8")
            if not data:
                break

            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue
                job = json.loads(line.strip())
                p = job["p"]

                start_time = time.time()
                is_mers = lucas_lehmer(p)
                duration = time.time() - start_time
                cpu_now = psutil.cpu_percent(interval=None)

                result = {
                    "p": p,
                    "is_mersenne": is_mers,
                    "duration": duration,
                    "worker_id": worker_id,
                    "processes_running": len(process_count_proxy),
                    "cpu": cpu_now
                }

                sock.sendall((json.dumps(result) + "\n").encode())

        except Exception as e:
            print(f"[!] Worker {worker_id} error: {e}")
            break

    sock.close()
    print(f"[-] Worker {worker_id} disconnected")

# ---------------------------
# MAIN
# ---------------------------

if __name__ == "__main__":
    mp.set_start_method("spawn")  # Windows-safe

    # ---------------------------
    # CONFIG
    # ---------------------------
    MASTER_IP = "192.168.1.28"  # server IP
    PORT = 5000
    TARGET_CPU = 60
    MAX_PROCESSES = os.cpu_count() * 2
    MIN_PROCESSES = 1

    # Shared objects (created in main only)
    manager_running = mp.Value('b', True)
    manager = mp.Manager()
    process_list = manager.list()

    # ---------------------------
    # HELPER FUNCTIONS
    # ---------------------------

    def spawn_worker():
        worker_id = len(process_list)
        p = mp.Process(
            target=worker_process,
            args=(worker_id, manager_running, MASTER_IP, PORT, process_list),
            daemon=True
        )
        p.start()
        process_list.append(p)
        print(f"[+] Spawned worker {worker_id}")

    def remove_worker():
        if process_list:
            p = process_list.pop()
            print(f"[-] Stopping worker process {p.pid}")
            p.terminate()
            p.join()

    def cpu_manager():
        """
        Dynamic scaling manager based on CPU usage.
        Spawns or removes workers to stay near TARGET_CPU.
        """
        while manager_running.value:
            cpu = psutil.cpu_percent(interval=1)
            current_count = len(process_list)

            if cpu < TARGET_CPU - 10 and current_count < MAX_PROCESSES:
                spawn_worker()
            elif cpu > TARGET_CPU + 10 and current_count > MIN_PROCESSES:
                remove_worker()

            print(f"[CPU Manager] CPU={cpu:.1f}% Processes={len(process_list)}")
            time.sleep(1)

    # ---------------------------
    # START CLIENT
    # ---------------------------

    # start with one worker
    spawn_worker()

    # start CPU manager in a separate process
    mgr = mp.Process(target=cpu_manager, daemon=True)
    mgr.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[!] Shutting down all workers...")
        manager_running.value = False

        # terminate all worker processes
        for p in process_list:
            p.terminate()
        for p in process_list:
            p.join()

        # terminate CPU manager
        mgr.terminate()
        mgr.join()

        print("[!] Client stopped.")
