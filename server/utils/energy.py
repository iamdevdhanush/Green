"""GreenOps Energy Calculation Utilities"""
from config import get_settings
settings = get_settings()


def calculate_energy_wasted(idle_seconds: float) -> float:
    idle_hours = idle_seconds / 3600.0
    return round(idle_hours * (settings.IDLE_POWER_WATTS / 1000.0), 6)


def calculate_cost(energy_kwh: float) -> float:
    return round(energy_kwh * settings.ELECTRICITY_COST_PER_KWH, 4)


def is_idle(idle_seconds: float) -> bool:
    return idle_seconds >= settings.IDLE_THRESHOLD_SECONDS
