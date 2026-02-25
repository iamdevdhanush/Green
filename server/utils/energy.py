"""
GreenOps Energy Calculation Utilities
Explainable, documented energy estimation model.
"""
from config import get_settings

settings = get_settings()


def calculate_energy_wasted(idle_seconds: float) -> float:
    """
    Calculate energy wasted during idle time.
    
    Formula:
        idle_hours = idle_seconds / 3600
        energy_kwh = idle_hours * (IDLE_POWER_WATTS / 1000)
    """
    idle_hours = idle_seconds / 3600.0
    energy_kwh = idle_hours * (settings.IDLE_POWER_WATTS / 1000.0)
    return round(energy_kwh, 6)


def calculate_cost(energy_kwh: float) -> float:
    """Calculate electricity cost for given energy consumption."""
    return round(energy_kwh * settings.ELECTRICITY_COST_PER_KWH, 4)


def is_idle(idle_seconds: float) -> bool:
    """Determine if a machine is in idle state."""
    return idle_seconds >= settings.IDLE_THRESHOLD_SECONDS
