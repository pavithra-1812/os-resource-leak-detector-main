
"""Recovery functions for simulated processes only."""

from simulator import recover_process


def recover_simulated_process(processes, process_name):
    """Recover a process in the simulation and return a recovery report."""
    return recover_process(processes, process_name)


def simulated_reset(memory_samples_mb, reset_to_mb=None):
    """Compatibility helper for resetting a list of simulated measurements."""
    samples = list(memory_samples_mb)

    if not samples:
        return samples

    target = reset_to_mb if reset_to_mb is not None else samples[0]
    samples[-1] = min(samples[-1], target)
    return samples

