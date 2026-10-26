
"""Read-only monitoring of processes visible in the Codespace."""

from datetime import datetime, timezone

import psutil


def get_system_metrics():
    memory = psutil.virtual_memory()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "memory_percent": memory.percent,
        "memory_used_mb": round(memory.used / (1024 ** 2), 2),
        "memory_total_mb": round(memory.total / (1024 ** 2), 2),
        "process_count": len(psutil.pids()),
        "source": "REAL_OS",
    }


def get_real_processes():
    """Read real process measurements and their command lines."""
    results = []

    for process in psutil.process_iter(
        ["pid", "name", "memory_info", "cpu_percent", "cmdline"]
    ):
        try:
            info = process.info
            memory_info = info.get("memory_info")
            command = info.get("cmdline") or []

            command_line = " ".join(command)

            # Friendly identification based on the actual command line.
            if (
                len(command) >= 3
                and command[1] == "-u"
                and command[2] == "workload_demo.py"
            ):
                display_name = "Memory Growth Demo"
            else:
                display_name = info.get("name") or "Unknown"

            results.append({
                "pid": info["pid"],
                "name": display_name,
                "executable": info.get("name") or "Unknown",
                "command_line": command_line,
                "memory_mb": (
                    round(memory_info.rss / (1024 ** 2), 2)
                    if memory_info else None
                ),
                "cpu_percent": info.get("cpu_percent") or 0.0,
                "source": "REAL_OS",
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    return sorted(
        results,
        key=lambda item: item["memory_mb"] or 0,
        reverse=True,
    )
