# code written by nathan shaw
import socket
import json
import math
import threading
import time
import os
import psutil  # pip install psutil
from rich.console import Console
from rich.table import Table

console = Console()

'''
COMPLETED_FILE = "completed.txt"

if os.path.exists(COMPLETED_FILE):
    with open(COMPLETED_FILE, "r") as f:
        #completed_p = set()
        completed_p = set(int(line.strip()) for line in f)
else:
    print("No completed file found, starting fresh.")
    completed_p = set()

PERFECT_FILE = "perfect.txt"

if os.path.exists(PERFECT_FILE):
    with open(PERFECT_FILE, "r") as f:
        #perfect_numbers = []
        perfect_numbers = [int(line.strip()) for line in f] 
else:
    perfect_numbers = []
'''

#prime checker
def is_prime(n):
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    r = int(math.sqrt(n))
    for i in range(3, r + 1, 2):
        if n % i == 0:
            return False
    return True


#globals
work_queue = []      # {"id": int, "p": prime}
workers = {}         # addr -> {"p": current prime, "processed": count, "start_time": time.time() started, "p_time": time to computer last p, "thread_c": thread count}
perfect_numbers = []  # list of found perfect numbers
completed_p = set()  # set of completed p values
lock = threading.Lock()

stop_flag = False
start_time = time.time()

next_prime_start = 3
next_work_id = 0

BUFFER_MIN = 100  # keep 100 primes ahead


#prime generator thread
def prime_refill_thread():
    global next_prime_start, next_work_id

    while not stop_flag:
        with lock:
            need_more = len(work_queue) < BUFFER_MIN

        if need_more:
            # generate primes in bulk until buffer >= BUFFER_MIN
            while len(work_queue) < BUFFER_MIN and not stop_flag:
                if is_prime(next_prime_start) and next_prime_start not in completed_p:
                    with lock:
                        work_queue.append({"id": next_work_id, "p": next_prime_start})
                        next_work_id += 1
                next_prime_start += 2 if next_prime_start > 2 else 1
        else:
            time.sleep(0.05)


#worker handling
def get_next_work(addr):
    with lock:
        if work_queue:
            job = work_queue.pop(0)
            workers[addr]["p"] = job["p"]
            return job
        else:
            workers[addr]["p"] = None
            return None

def handle_worker(conn, addr):
    workers[addr] = {"p": None, "processed": 0, "start_time": time.time(), "p_time": 0, "thread_c": 0}

    last_count_time = time.time()
    last_count_processed = 0

    while not stop_flag:
        work = get_next_work(addr)
        if not work:
            time.sleep(0.05)
            continue
        
        send_time = time.time()
        conn.sendall(json.dumps(work).encode("utf-8") + b"\n")

        try:
            data = conn.recv(1024).decode("utf-8")
            end_time = time.time()
            duration = end_time - send_time
            if not data:
                break

            result = json.loads(data.strip())

            with lock:
                workers[addr]["processed"] += 1
                workers[addr]["p_time"] = duration
                workers[addr]["thread_c"] = result.get("threads_running")
                workers[addr]["cpu"] = result.get("cpu", 0.0)
                '''
                with open(COMPLETED_FILE, "a") as f:
                    f.write(f"{result['p']}\n")
                completed_p.add(result["p"])'''
                if result.get("is_mersenne"):
                    perfect_numbers.append(result["p"])

            workers[addr]["p"] = None

        except:
            break

    conn.close()
    with lock:
        workers.pop(addr, None)


#dashboard rendering
def render_dashboard():
    with lock:
        cpu = psutil.cpu_percent(interval=0.1)
        queue_len = len(work_queue)

        # Aggregate workers by IP (ignore port)
        ip_stats = {}
        now = time.time()
        for addr, info in workers.items():
            ip = addr[0]  # only consider IP, ignore port
            if ip not in ip_stats:
                ip_stats[ip] = {
                    "processed": 0,
                    "p_time_total": 0.0,
                    "online_time_total": 0.0,
                    "cpu_total": 0.0,
                    "thread_count": 0,      # number of connections
                    "current_p": None
                }
            ip_stats[ip]["processed"] += info.get("processed", 0)
            ip_stats[ip]["p_time_total"] += info.get("p_time") or 0.001
            ip_stats[ip]["online_time_total"] += now - info.get("start_time", now)
            ip_stats[ip]["thread_count"] += 1   # each connection = 1 thread
            ip_stats[ip]["cpu_total"] += info.get("cpu", 0.0)
            if info.get("p") is not None:
                ip_stats[ip]["current_p"] = info["p"]
            
            #print(f"[DEBUG] Worker {addr} CPU: {info.get('cpu')}%")

        # Worker throughput
        total_processed = sum(w["processed"] for w in workers.values())
        total_elapsed = max(time.time() - start_time, 0.001)
        total_throughput = total_processed / total_elapsed

        # ETA
        eta = (queue_len / total_throughput) if total_throughput > 0 else float('inf')

        # Build table
        table = Table(title="Connected Workers (aggregated by IP)")
        table.add_column("Worker IP", style="cyan")
        table.add_column("Current p", style="magenta")
        table.add_column("Processed", style="green")
        table.add_column("Avg p calc time", style="yellow")
        table.add_column("Total time online", style="bright_blue")
        table.add_column("Avg CPU (%)", style="bright_magenta")
        table.add_column("Threads (connections)", style="bright_red")

        for ip, stats in ip_stats.items():
            worker_count = stats["thread_count"]  # number of connections for this IP
            avg_p_time = stats["p_time_total"] / max(worker_count, 1)
            avg_cpu = stats["cpu_total"] / max(worker_count, 1)  # average CPU across all threads
            table.add_row(
                ip,
                str(stats["current_p"]),
                str(stats["processed"]),
                f"{avg_p_time:.3f}",
                f"{stats['online_time_total']:.1f}s",
                f"{avg_cpu:.1f}%",
                str(stats["thread_count"])
            )

    console.clear()
    console.print(f"[bold yellow]Time Elapsed:[/bold yellow] {int(total_elapsed)}s")
    console.print(f"[bold cyan]CPU Usage:[/bold cyan] {cpu:.1f}%")
    console.print(f"[bold green]Primes in Queue:[/bold green] {queue_len}")
    console.print(f"[bold green]Total Throughput:[/bold green] {total_throughput:.2f} primes/sec")
    console.print(f"[bold green]ETA until queue empty:[/bold green] {eta:.2f} sec")
    console.print(f"[bold green]Perfect Numbers Found:[/bold green] {len(perfect_numbers)}")
    console.print(f"[green]p values:[/green] {perfect_numbers}")
    console.print(table)

def dashboard_thread():
    while not stop_flag:
        render_dashboard()
        time.sleep(1)

# listening for stop
def stop_listener():
    global stop_flag
    input("\nPress Enter to stop server...\n")
    stop_flag = True
    console.print("[red]Stopping server...[/red]")

#server essentials
HOST = "0.0.0.0"
PORT = 5000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
console.print(f"[bold green]Server listening on {HOST}:{PORT}[/bold green]")

# Start threads
threading.Thread(target=prime_refill_thread, daemon=True).start()
threading.Thread(target=dashboard_thread, daemon=True).start()
threading.Thread(target=stop_listener, daemon=True).start()

# Accept connections
try:
    while not stop_flag:
        server.settimeout(1.0)
        try:
            conn, addr = server.accept()
        except socket.timeout:
            continue

        threading.Thread(target=handle_worker, args=(conn, addr), daemon=True).start()
finally:
    server.close()
    console.print("[bold red]Server closed[/bold red]")
