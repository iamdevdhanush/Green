"""
GreenOps Energy Calculations
Converts idle time to kWh, CO₂, and cost impact.
"""
from app.core.config import settings


def calculate_energy_kwh(idle_minutes: int) -> float:
    """Calculate energy wasted in kWh from idle minutes."""
    idle_hours = idle_minutes / 60
    return round(idle_hours * settings.IDLE_KWH_PER_HOUR, 6)


def calculate_co2_kg(kwh: float) -> float:
    """Calculate CO₂ emissions in kg from kWh."""
    return round(kwh * settings.CO2_KG_PER_KWH, 6)


def calculate_cost_usd(kwh: float) -> float:
    """Calculate electricity cost in USD from kWh."""
    return round(kwh * settings.COST_PER_KWH, 4)


def calculate_all(idle_minutes: int) -> dict:
    """Full energy impact calculation for an idle interval."""
    kwh = calculate_energy_kwh(idle_minutes)
    co2 = calculate_co2_kg(kwh)
    cost = calculate_cost_usd(kwh)
    return {
        "energy_kwh": kwh,
        "co2_kg": co2,
        "cost_usd": cost,
    }


def pct_change(current: float, previous: float) -> float | None:
    """Calculate percentage change, returns None if previous is 0."""
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 2)
