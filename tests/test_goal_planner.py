"""Reglas de los planes de acción basados en ingreso y presupuesto."""

from datetime import date, datetime
from decimal import Decimal

from app.db.models import Goal, User
from app.goals.planner import build_goal_action_plan

TODAY = date(2026, 10, 28)


def _user(
    frequency: str = "monthly",
    income: str = "3000000",
    budget: str = "2400000",
) -> User:
    amount = Decimal(income)
    monthly = amount * (2 if frequency == "biweekly" else 1)
    return User(
        email="test@fylax.dev",
        income_amount=amount,
        income_frequency=frequency,
        monthly_income=monthly,
        monthly_budget=Decimal(budget),
    )


def _goal(target: str = "1200000", deadline: datetime | None = None) -> Goal:
    return Goal(
        user_id=_user().id,
        name="Viaje",
        target_amount=Decimal(target),
        saved_amount=Decimal("0"),
        deadline=deadline,
    )


def test_plan_quincenal_convierte_capacidad_mensual_en_aporte_por_nomina():
    plan = build_goal_action_plan(_goal(), _user("biweekly", income="1500000"), today=TODAY)

    assert plan.recommended_contribution == Decimal("300000.00")
    assert plan.monthly_contribution == Decimal("600000.00")
    assert plan.months_to_goal == 2
    assert plan.feasible


def test_sin_ingreso_pide_configuracion_financiera():
    plan = build_goal_action_plan(_goal(), _user(income="0", budget="0"), today=TODAY)

    assert plan.requires_income_setup
    assert plan.recommended_contribution == 0
    assert plan.months_to_goal is None


def test_presupuesto_que_consume_todo_el_ingreso_no_es_viable():
    plan = build_goal_action_plan(_goal(), _user(income="3000000", budget="3000000"), today=TODAY)

    assert not plan.feasible
    assert not plan.requires_income_setup
    assert plan.months_to_goal is None


def test_fecha_limite_viable_calcula_aporte_necesario():
    plan = build_goal_action_plan(_goal(deadline=datetime(2026, 12, 28)), _user(), today=TODAY)

    assert plan.recommended_contribution == Decimal("400000.00")
    assert plan.months_to_goal == 3
    assert plan.feasible


def test_fecha_limite_supera_capacidad_y_advierte():
    plan = build_goal_action_plan(
        _goal(target="12000000", deadline=datetime(2027, 1, 28)),
        _user(),
        today=TODAY,
    )

    assert not plan.feasible
    assert plan.monthly_contribution > Decimal("600000")
    assert "supera tu capacidad" in plan.message


def test_proposito_completado_no_recomienda_mas_aportes():
    goal = _goal()
    goal.saved_amount = goal.target_amount

    plan = build_goal_action_plan(goal, _user(), today=TODAY)

    assert plan.months_to_goal == 0
    assert plan.recommended_contribution == 0
    assert plan.feasible


def test_gasto_bajo_mantiene_el_plan_en_camino():
    plan = build_goal_action_plan(
        _goal(), _user(), today=TODAY, monthly_spent=Decimal("1000000")
    )

    assert plan.status == "on_track"
    assert plan.remaining_budget == Decimal("1400000.00")
    assert plan.alert_message is None


def test_gasto_cercano_al_presupuesto_avisa_antes_de_romper_el_plan():
    plan = build_goal_action_plan(
        _goal(), _user("biweekly", income="1500000"), today=TODAY,
        monthly_spent=Decimal("2100000")
    )

    assert plan.status == "at_risk"
    assert plan.recommended_contribution == Decimal("300000.00")
    assert "$300.000" in plan.alert_message


def test_gasto_que_supera_el_presupuesto_marca_plan_desviado():
    plan = build_goal_action_plan(
        _goal(), _user(), today=TODAY, monthly_spent=Decimal("2400001")
    )

    assert plan.status == "off_track"
    assert plan.remaining_budget == Decimal("-1.00")
