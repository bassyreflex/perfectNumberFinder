# all code written by Nathan Shaw
import time
import multiprocessing as mp
import math
import os
import sys


def lucas_lehmer(p):
    if p == 2:
        return True
    M = 2**p - 1
    s = 4
    for _ in range(p - 2):
        s = (s * s - 2) % M
    return s == 0


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


def prime_producer(queue, stop_event, p_counter):
    p = 2
    while not stop_event.is_set():
        if queue.qsize() > 500:
            time.sleep(0.1)
            continue
        if is_prime(p):
            queue.put(p)
        with p_counter.get_lock():
            p_counter.value = p
        p += 1



def perfect_worker(queue, result_queue, stop_event, p_processed):
    while not stop_event.is_set():
        try:
            p = queue.get(timeout=0.5)
        except:
            continue
        if lucas_lehmer(p):
            M = 2**p - 1
            perfect = 2**(p-1) * M
            result_queue.put((p, M, perfect))
        
        with p_processed.get_lock():
            if p > p_processed.value:
                p_processed.value = p


def main():
    start_time = time.time()
    sys.set_int_max_str_digits(0) #remove str int limit

    NUM_WORKERS = 1   # change to the number of worker cores you want
    print(f"Using {NUM_WORKERS + 1} processes total ({NUM_WORKERS} workers + 1 producer).")


    p_processed = mp.Value('i', 2)  # p values of primes actually processed
    prime_queue = mp.Queue() # queue of prime p value created by producer
    result_queue = mp.Queue() # queue of found perfect numbers
    stop_event = mp.Event() # event to signal stopping
    p_counter = mp.Value('i', 2)  # track the current p being processed

    # Start producer
    producer = mp.Process(target=prime_producer, args=(prime_queue, stop_event, p_counter))
    producer.start()

    # Start workers
    workers = []
    for _ in range(NUM_WORKERS):
        w = mp.Process(target=perfect_worker, args=(prime_queue, result_queue, stop_event, p_processed))
        w.start()
        workers.append(w)

    total_found = 0
    max_digits = 0
    biggest_p = 0
    try:
        while True:
            # Check for new perfect numbers without printing each one
            while not result_queue.empty():
                p, M, perfect = result_queue.get()
                total_found += 1
                biggest_p = max(biggest_p, p)
                max_digits = max(max_digits, len(str(perfect)))

            # dashboard
            elapsed = time.time() - start_time
            sys.stdout.write(
                f"\rTotal perfect numbers found: {total_found} | "
                f"Elapsed time: {elapsed:.1f}s | "
                f"Primes generated: {p_counter.value} | "
                f"Current p: {p_processed.value} | "
                f"Cores used: {NUM_WORKERS + 1} | "
                f"Largest p found: {biggest_p} "
            )
            sys.stdout.flush()
            time.sleep(0.2)

    except KeyboardInterrupt:
        stop_event.set()
        producer.join()
        for w in workers:
            w.join()
        print("\n\n[Main] Execution stopped by user.")
        print(f"Total perfect numbers found: {total_found}")
        print(f"Length of largest perfect number: {max_digits} digits")
        print(f"Total elapsed time: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    main()
