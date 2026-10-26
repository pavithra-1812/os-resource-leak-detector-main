
"""Bounded workload for OS Resource Leak Detector.

This is a controlled test workload, not a real memory leak.
Maximum retained test memory: 64 MB.
Maximum runtime: 220 seconds (3 minutes 40 seconds).
"""

import os
import time

CHUNK_MB = 2
MAX_MEMORY_MB = 64
INTERVAL_SECONDS = 2
MAX_RUNTIME_SECONDS = 220


def main():
    allocations = []
    started = time.monotonic()
    next_status_time = started

    print(f"Workload PID: {os.getpid()}", flush=True)
    print("Mode: controlled memory growth", flush=True)
    print(f"Maximum memory: {MAX_MEMORY_MB} MB", flush=True)
    print(f"Maximum runtime: {MAX_RUNTIME_SECONDS} seconds", flush=True)

    try:
        while time.monotonic() - started < MAX_RUNTIME_SECONDS:
            elapsed = time.monotonic() - started
            current_mb = len(allocations) * CHUNK_MB

            # Allocate memory only while below the safe limit.
            if current_mb < MAX_MEMORY_MB:
                allocations.append(bytearray(CHUNK_MB * 1024 * 1024))
                current_mb = len(allocations) * CHUNK_MB

                print(
                    f"Allocated test memory: {current_mb} MB "
                    f"| Elapsed: {int(elapsed)} seconds",
                    flush=True,
                )

            # Once the cap is reached, retain the allocated memory
            # and keep the workload alive for monitoring.
            elif time.monotonic() >= next_status_time:
                print(
                    f"Memory cap reached: {current_mb} MB "
                    f"| Workload still running "
                    f"| Elapsed: {int(elapsed)} seconds",
                    flush=True,
                )
                next_status_time = time.monotonic() + 10

            time.sleep(INTERVAL_SECONDS)

        print("Maximum runtime of 220 seconds reached.", flush=True)

    except KeyboardInterrupt:
        print("Workload stopped by user.", flush=True)

    finally:
        allocations.clear()
        print("Test allocations released.", flush=True)


if __name__ == "__main__":
    main()
