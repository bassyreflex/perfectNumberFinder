import socket
import json
import multiprocessing as mp
import psutil
import time
import os

# -------------------------------------------------
# LUCAS-LEHMER TEST
# -------------------------------------------------

def lucas_lehmer(p):
    if p == 2:
        return True
    M = (1 << p) - 1
    s = 4
    for _ in range(p - 2):
        s = (s * s - 2) % M
    return s == 0


# -------------------------------------------------
# WORKER PROCESS
# -------------------------------------------------

def worker_process(worker_id, running_flag, server_ip, port):

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

                job = json.loads(line)
                p = job["p"]

                start = time.time()
                is_mers = lucas_lehmer(p)
                duration = time.time() - start

                cpu_now = psutil.cpu_percent(interval=0.0)
                #print(f"{worker_id} measured cpu as {cpu_now}")

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
    print(f"[-] Worker {worker_id} stopped")


# -------------------------------------------------
# CPU MANAGER PROCESS
# -------------------------------------------------

def cpu_manager(running_flag, target_cpu, max_proc, min_proc, command_q):
    """
    CPU manager does NOT own worker processes!
    It only sends commands to the main process:
      - "spawn"
      - "kill"
    """
    while running_flag.value:
        cpu = psutil.cpu_percent(interval=1)

        if cpu < target_cpu - 10:
            command_q.put("spawn")
        elif cpu > target_cpu + 10:
            command_q.put("kill")

        time.sleep(1)


# -------------------------------------------------
# MAIN PROCESS HELPERS (These run only in main!)
# -------------------------------------------------

def spawn_worker(process_list, running_flag, server_ip, port):
    worker_id = len(process_list)
    p = mp.Process(
        target=worker_process,
        args=(worker_id, running_flag, server_ip, port),
        daemon=True
    )
    p.start()
    process_list.append(p)
    print(f"[+] Spawned worker {worker_id}")


def remove_worker(process_list):
    if not process_list:
        return

    p = process_list.pop()
    print(f"[-] Killing worker PID {p.pid}")
    p.terminate()
    p.join()


# -------------------------------------------------
# MAIN
# -------------------------------------------------

if __name__ == "__main__":
    mp.set_start_method("spawn")      # Windows safe

    MASTER_IP = "192.168.1.28"
    PORT = 5000
    TARGET_CPU = 80
    MAX_PROCESSES = os.cpu_count() * 2
    MIN_PROCESSES = 1

    # Shared flag for workers
    running_flag = mp.Value('b', True)

    # Queue for CPU manager -> main commands
    command_q = mp.Queue()

    # Track active workers
    process_list = []

    print("[*] Starting initial worker...")
    spawn_worker(process_list, running_flag, MASTER_IP, PORT)

    mgr = mp.Process(
        target=cpu_manager,
        args=(running_flag, TARGET_CPU, MAX_PROCESSES, MIN_PROCESSES, command_q),
        daemon=True
    )
    mgr.start()
    print("[*] CPU manager started.")

    try:
        while True:
            time.sleep(0.1)

            while not command_q.empty():
                cmd = command_q.get()

                if cmd == "spawn" and len(process_list) < MAX_PROCESSES:
                    spawn_worker(process_list, running_flag, MASTER_IP, PORT)

                elif cmd == "kill" and len(process_list) > MIN_PROCESSES:
                    remove_worker(process_list)

    except KeyboardInterrupt:
        print("\n[!] Shutting down...")

        running_flag.value = False

        # Kill workers
        for p in process_list:
            print(f"[-] Terminating worker {p.pid}")
            p.terminate()

        for p in process_list:
            p.join()

        mgr.terminate()
        mgr.join()

        print("[!] Client stopped.")
