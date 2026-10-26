
"""Detection rules for simulated resource usage."""

def detect_suspicious_growth(
    memory_samples_mb,
    minimum_growth_mb=60.0,
    minimum_consecutive_increases=3,
):
    """Flag sustained upward memory trends in sample history.

    This is an educational heuristic, not proof of a real memory leak.
    """
    samples = list(memory_samples_mb)

    if len(samples) < minimum_consecutive_increases + 1:
        return {
            "suspicious": False,
            "total_growth_mb": 0.0,
            "consecutive_increases": 0,
            "reason": "Not enough samples",
        }

    recent = samples[-(minimum_consecutive_increases + 1):]
    total_growth = recent[-1] - recent[0]

    consecutive_increases = 0
    for previous, current in zip(recent, recent[1:]):
        if current > previous:
            consecutive_increases += 1
        else:
            consecutive_increases = 0

    suspicious = (
        consecutive_increases >= minimum_consecutive_increases
        and total_growth >= minimum_growth_mb
    )

    return {
        "suspicious": suspicious,
        "total_growth_mb": round(total_growth, 2),
        "consecutive_increases": consecutive_increases,
        "reason": (
            "Sustained growth detected"
            if suspicious
            else "Selected detection conditions not met"
        ),
    }
