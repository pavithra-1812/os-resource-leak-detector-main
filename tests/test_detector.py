from detector import detect_suspicious_growth
from recovery import simulated_reset


def test_stable_usage_is_not_flagged():
    result = detect_suspicious_growth([100, 104, 102, 105, 103, 106])
    assert result["suspicious"] is False


def test_sustained_growth_is_flagged():
    result = detect_suspicious_growth(
        [100, 145, 205, 270, 335, 410],
        minimum_growth_mb=150,
        minimum_consecutive_increases=3,
    )
    assert result["suspicious"] is True


def test_temporary_spike_is_not_flagged_by_default_rule():
    result = detect_suspicious_growth([100, 180, 125, 115, 120, 118])
    assert result["suspicious"] is False


def test_simulated_reset_reduces_final_value():
    result = simulated_reset([100, 145, 205, 270, 335, 410])
    assert result[-1] == 100
    assert result[:-1] == [100, 145, 205, 270, 335]
