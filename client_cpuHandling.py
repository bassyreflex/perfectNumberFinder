# Dynamic Multiprocessing Client (Windows-safe)
# Author: Nathan Shaw

import socket
import json
import multiprocessing as mp
import psutil
import time
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

def worker_process(worker_id, running_flag, server_ip, port):
    """
    Each worker opens its own socket connection to the server.
    Reports p, result, CPU usage, and worker ID.
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
                    "cpu": cpu_now
                }

                sock.sendall((json.dumps(result) + "\n").encode())

        except Exception as e:
            print(f"[!] Worker {worker_id} error: {e}")
            break

    sock.close()
    print(f"[-] Worker {worker_id} disconnected")

# ---------------------------
# CPU MANAGER FUNCTION
# ---------------------------

def cpu_manager(running_flag, target_cpu, max_processes, min_processes, process_list, server_ip, port):
    """
    Dynamically scales worker processes based on CPU usage.
    """
    while running_flag.value:
        cpu = psutil.cpu_percent(interval=1)
        current_count = len(process_list)

        if cpu < target_cpu - 10 and current_count < max_processes:
            # Spawn a new worker
            spawn_worker(process_list, running_flag, server_ip, port)
        elif cpu > target_cpu + 10 and current_count > min_processes:
            # Remove one worker
            remove_worker(process_list)

        print(f"[CPU Manager] CPU={cpu:.1f}% Processes={len(process_list)}")
        time.sleep(1)

# ---------------------------
# HELPER FUNCTIONS
# ---------------------------

def spawn_worker(process_list, running_flag, server_ip, port):
    worker_id = len(process_list)
    p = mp.Process(
        target=worker_process,
        args=(worker_id, running_flag, server_ip, port),
        daemon=True  # automatically stops with main process
    )
    p.start()
    process_list.append(p)
    print(f"[+] Spawned worker {worker_id}")

def remove_worker(process_list):
    if process_list:
        p = process_list.pop()
        p.terminate()
        p.join()
        print(f"[-] Removed worker {p.pid}")

# ---------------------------
# MAIN
# ---------------------------

if __name__ == "__main__":
    mp.set_start_method("spawn")  # Windows-safe

    MASTER_IP = "192.168.1.28"  # server IP
    PORT = 5000
    TARGET_CPU = 60
    MAX_PROCESSES = os.cpu_count() * 2
    MIN_PROCESSES = 1

    # Shared value for all workers
    manager_running = mp.Value('b', True)

    # Regular list to track worker processes
    process_list = []

    # Start initial worker
    spawn_worker(process_list, manager_running, MASTER_IP, PORT)

    # Start CPU manager as a separate process
    mgr = mp.Process(
        target=cpu_manager,
        args=(manager_running, TARGET_CPU, MAX_PROCESSES, MIN_PROCESSES, process_list, MASTER_IP, PORT),
        daemon=True
    )
    mgr.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[!] Shutting down all workers...")
        manager_running.value = False

        for p in process_list:
            p.terminate()
        for p in process_list:
            p.join()

        mgr.terminate()
        mgr.join()
        print("[!] Client stopped.")
