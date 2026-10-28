"""Planes de acción de propósitos, calculados desde la capacidad de ahorro.

No se persisten: cambian automáticamente cuando el usuario actualiza su
ingreso, presupuesto, aportes o fecha límite. Las reglas son deterministas
y transparentes (no IA), apropiadas para el MVP financiero.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel

from app.db.models import Goal, User

_ZERO = Decimal("0")
_CENT = Decimal("0.01")


class GoalActionPlan(BaseModel):
    """Recomendación accionable y seguimiento con el gasto real del mes."""

    income_frequency: Literal["monthly", "biweekly"]
    recommended_contribution: Decimal
    monthly_contribution: Decimal
    months_to_goal: int | None
    estimated_completion: date | None
    feasible: bool
    requires_income_setup: bool
    message: str
    status: Literal["on_track", "at_risk", "off_track"] = "on_track"
    monthly_spent: Decimal = _ZERO
    remaining_budget: Decimal = _ZERO
    alert_message: str | None = None


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _display_money(value: Decimal) -> str:
    return f"${value:,.0f}".replace(",", ".")


def _months(amount: Decimal, monthly: Decimal) -> int:
    return max(1, int((amount / monthly).to_integral_value(rounding=ROUND_CEILING)))


def build_goal_action_plan(
    goal: Goal,
    user: User | None,
    active_goals: int = 1,
    today: date | None = None,
    monthly_spent: Decimal = _ZERO,
) -> GoalActionPlan:
    """Calcula aporte por nómina, duración, viabilidad y riesgo con gastos reales.

    La capacidad mensual es ingreso mensual - presupuesto de gastos. Si hay
    varios propósitos activos, se reparte por igual. Al llegar al 85 % del
    presupuesto se avisa antes de comprometer el aporte de la próxima nómina.
    """
    now = today or datetime.now(UTC).date()
    frequency = user.income_frequency if user is not None else "monthly"
    frequency = "biweekly" if frequency == "biweekly" else "monthly"
    periods = Decimal("2") if frequency == "biweekly" else Decimal("1")
    remaining = max(goal.target_amount - goal.saved_amount, _ZERO)

    if remaining == 0:
        return GoalActionPlan(
            income_frequency=frequency,
            recommended_contribution=_ZERO,
            monthly_contribution=_ZERO,
            months_to_goal=0,
            estimated_completion=now,
            feasible=True,
            requires_income_setup=False,
            message="Propósito cumplido. Puedes crear uno nuevo o mantener el hábito.",
        )

    monthly_income = user.monthly_income if user is not None else _ZERO
    monthly_budget = user.monthly_budget if user is not None else _ZERO
    if monthly_income <= 0:
        return GoalActionPlan(
            income_frequency=frequency,
            recommended_contribution=_ZERO,
            monthly_contribution=_ZERO,
            months_to_goal=None,
            estimated_completion=None,
            feasible=False,
            requires_income_setup=True,
            message="Configura tu ingreso mensual o quincenal para calcular tu plan.",
        )

    capacity = max(monthly_income - monthly_budget, _ZERO)
    share = capacity / max(active_goals, 1)
    if share <= 0:
        return GoalActionPlan(
            income_frequency=frequency,
            recommended_contribution=_ZERO,
            monthly_contribution=_ZERO,
            months_to_goal=None,
            estimated_completion=None,
            feasible=False,
            requires_income_setup=False,
            message=(
                "Tu presupuesto de gastos usa todo tu ingreso. Reduce gastos o "
                "ajusta el presupuesto para liberar dinero para este propósito."
            ),
        )

    if goal.deadline is not None:
        deadline_date = goal.deadline.date()
        days_left = (deadline_date - now).days
        months_left = max(
            1,
            int(
                (Decimal(days_left) / Decimal("30.4375")).to_integral_value(rounding=ROUND_CEILING)
            ),
        )
        monthly = min(remaining / months_left, remaining)
        months_to_goal = months_left
        feasible = monthly <= share
        if feasible:
            message = "Con este aporte en cada nómina llegas a tu fecha límite."
        elif days_left < 0:
            message = (
                "La fecha límite ya pasó. Actualízala o ajusta el objetivo para "
                "recuperar un plan viable."
            )
        else:
            message = (
                "El aporte necesario supera tu capacidad asignada. Amplía la "
                "fecha, reduce gastos o disminuye el monto objetivo."
            )
    else:
        monthly = min(share, remaining)
        months_to_goal = _months(remaining, monthly)
        feasible = True
        message = (
            "Apartaremos una parte de lo que queda después de tus gastos en "
            "cada nómina hasta completar el propósito."
        )

    monthly = _money(monthly)
    status = "on_track"
    alert_message = None
    if monthly_spent > monthly_budget or monthly_spent + monthly > monthly_income:
        status = "off_track"
        alert_message = (
            "Tus gastos ya comprometen el aporte de "
            f"{_display_money(monthly / periods)} por nómina. Reduce gastos o "
            "ajusta el plan para recuperar el rumbo."
        )
    elif monthly_budget > 0 and monthly_spent >= monthly_budget * Decimal("0.85"):
        status = "at_risk"
        alert_message = (
            "Estás cerca de agotar tu presupuesto. Modera los próximos gastos "
            "para proteger el aporte de "
            f"{_display_money(monthly / periods)} por nómina."
        )

    return GoalActionPlan(
        income_frequency=frequency,
        recommended_contribution=_money(monthly / periods),
        monthly_contribution=monthly,
        months_to_goal=months_to_goal,
        estimated_completion=now + timedelta(days=months_to_goal * 30),
        feasible=feasible,
        requires_income_setup=False,
        message=message,
        status=status,
        monthly_spent=_money(monthly_spent),
        remaining_budget=_money(monthly_budget - monthly_spent),
        alert_message=alert_message,
    )
