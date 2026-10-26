
"""Live simulated process generator.

All measurements in this module are simulated values.
They are NOT readings from real operating-system processes.
"""

from datetime import datetime, timezone
import random


PROCESS_CONFIG = {
    "Process_A": {"initial_mb": 120.0, "mode": "normal"},
    "Process_B": {"initial_mb": 160.0, "mode": "normal"},
    "Process_C": {"initial_mb": 100.0, "mode": "normal"},
}


def create_processes():
    """Create fresh simulated processes for a new session."""
    processes = {}

    for name, config in PROCESS_CONFIG.items():
        initial = config["initial_mb"]

        processes[name] = {
            "name": name,
            "pid": f"SIM-{name[-1]}",
            "memory_mb": initial,
            "baseline_mb": initial,
            "mode": config["mode"],
            "leak_active": False,
            "recovery_count": 0,
            "history": [
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "memory_mb": initial,
                }
            ],
        }

    return processes


def tick_processes(processes):
    """Advance the simulation by one monitoring interval.

    Normal processes fluctuate slightly.
    Processes with an active simulated leak grow steadily.
    """
    for process in processes.values():
        current = process["memory_mb"]

        if process["leak_active"]:
            # Simulated leak: sustained upward growth.
            change = random.uniform(18.0, 30.0)
            process["memory_mb"] = current + change
            process["mode"] = "simulated_leak"

        else:
            # Normal process: small fluctuations around its baseline.
            change = random.uniform(-4.0, 5.0)
            new_value = current + change

            # Prevent normal activity from drifting indefinitely.
            lower = process["baseline_mb"] * 0.85
            upper = process["baseline_mb"] * 1.20

            process["memory_mb"] = max(
                lower, min(upper, new_value)
            )
            process["mode"] = "normal"

        process["history"].append(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "memory_mb": round(process["memory_mb"], 2),
            }
        )

        # Keep a manageable rolling history.
        process["history"] = process["history"][-120:]


def inject_leak(processes, process_name):
    """Start a simulated leak for the selected process."""
    process = processes[process_name]
    process["leak_active"] = True
    process["mode"] = "simulated_leak"


def stop_leak(processes, process_name):
    """Stop further simulated growth without resetting memory."""
    process = processes[process_name]
    process["leak_active"] = False
    process["mode"] = "normal"


def recover_process(processes, process_name):
    """Reset simulated memory to baseline and stop the simulated leak."""
    process = processes[process_name]
    before_mb = process["memory_mb"]

    process["memory_mb"] = process["baseline_mb"]
    process["leak_active"] = False
    process["mode"] = "recovered"
    process["recovery_count"] += 1

    process["history"].append(
        {
            "time": datetime.now(timezone.utc).isoformat(),
            "memory_mb": round(process["memory_mb"], 2),
        }
    )
    process["history"] = process["history"][-120:]

    return {
        "process": process_name,
        "before_mb": round(before_mb, 2),
        "after_mb": round(process["memory_mb"], 2),
        "reduced_mb": round(
            before_mb - process["memory_mb"], 2
        ),
        "status": (
            "Improved in simulation"
            if before_mb > process["memory_mb"]
            else "No reduction observed"
        ),
    }


def get_process_snapshot(processes):
    """Return a simplified copy of current simulated process data."""
    return [
        {
            "name": process["name"],
            "pid": process["pid"],
            "memory_mb": round(process["memory_mb"], 2),
            "mode": process["mode"],
            "leak_active": process["leak_active"],
            "recovery_count": process["recovery_count"],
        }
        for process in processes.values()
    ]
