import datetime as dt
import math
import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.forecasting import ForecastEvaluation
from app.repositories.forecasting.forecast_repository import ForecastRepository
from app.schemas.forecasting import CategoryEvaluationMetric
from app.services.forecasting.expense_income_forecaster import (
    forecast_categories,
    forecast_expenses,
    forecast_income,
)


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def run_time_aware_backtest(
    db: Session,
    repo: ForecastRepository,
    user_id: uuid.UUID,
    *,
    as_of_date: dt.date,
    horizon_days: int = 30,
) -> ForecastEvaluation:
    """
    Time-aware walk-forward backtest: splits strictly at cutoff_date = as_of_date - horizon_days.
    Generates predictions using ONLY transactions on or before cutoff_date (no future leakage),
    then compares against realized transactions in (cutoff_date, as_of_date].
    Avoids MAPE division-by-zero by using MAE, RMSE, WAPE, and Bias.
    """
    eval_window = min(max(14, horizon_days), 90)
    cutoff_date = as_of_date - dt.timedelta(days=eval_window)
    eval_start = cutoff_date + dt.timedelta(days=1)

    pre_txs = repo.list_eligible_transactions(db, user_id, date_to=cutoff_date)
    pre_expenses = [tx for tx in pre_txs if tx.transaction_type == "expense"]
    pre_incomes = [tx for tx in pre_txs if tx.transaction_type == "income"]

    post_txs = repo.list_eligible_transactions(
        db, user_id, date_from=eval_start, date_to=as_of_date
    )
    post_expenses = [tx for tx in post_txs if tx.transaction_type == "expense"]
    post_incomes = [tx for tx in post_txs if tx.transaction_type == "income"]

    pre_dates = [t.transaction_date for t in pre_expenses]
    pre_cov_days = ((max(pre_dates) - min(pre_dates)).days + 1) if len(pre_dates) >= 2 else 0

    if len(pre_expenses) < 4 or pre_cov_days < 28 or not post_txs:
        ev = ForecastEvaluation(
            user_id=user_id,
            forecast_type="comprehensive",
            horizon_days=eval_window,
            cutoff_date=cutoff_date,
            eval_start_date=eval_start,
            eval_end_date=as_of_date,
            method="insufficient_history",
            status="insufficient_history",
            notes=(
                f"Need >=4 expenses across >=28 days before cutoff ({cutoff_date}) and realized "
                f"transactions in ({eval_start}..{as_of_date}). Found {len(pre_expenses)} pre-cutoff expenses "
                f"({pre_cov_days}d span) and {len(post_txs)} evaluation transactions."
            ),
        )
        db.add(ev)
        db.flush()
        return ev

    # Strictly use pre-cutoff data for prediction; never pass post-cutoff actuals!
    exp_fc, _, _ = forecast_expenses(
        expenses=pre_expenses,
        commitments=[],
        as_of_date=cutoff_date,
        horizon_days=eval_window,
    )
    inc_fc, _ = forecast_income(
        incomes=pre_incomes,
        horizon_days=eval_window,
    )
    cat_map = repo.list_categorizations_map(db, user_id)
    pred_cats = forecast_categories(
        expenses=pre_expenses,
        cat_map=cat_map,
        horizon_days=eval_window,
    )

    pred_exp = exp_fc.predicted_total if exp_fc.predicted_total is not None else Decimal("0.00")
    pred_inc = inc_fc.predicted_total if inc_fc.predicted_total is not None else Decimal("0.00")
    pred_net = _q2(pred_inc - pred_exp)

    act_exp = _q2(sum((Decimal(t.amount) for t in post_expenses), Decimal("0.00")))
    act_inc = _q2(sum((Decimal(t.amount) for t in post_incomes), Decimal("0.00")))
    act_net = _q2(act_inc - act_exp)

    # Category-level predicted vs actual comparison
    act_by_cat: dict[str, Decimal] = {}
    for tx in post_expenses:
        cat_rec = cat_map.get(tx.id)
        c_name = (
            (tx.category.name if tx.category else None)
            or (cat_rec.suggested_category_name if cat_rec else None)
            or "Uncategorized"
        )
        act_by_cat[c_name] = act_by_cat.get(c_name, Decimal("0.00")) + Decimal(tx.amount)

    pred_by_cat = {
        c.category_name: (c.predicted_amount if c.predicted_amount is not None else Decimal("0.00"))
        for c in pred_cats
        if c.data_sufficient
    }
    all_cats = sorted(set(pred_by_cat.keys()) | set(act_by_cat.keys()))

    cat_metrics: list[CategoryEvaluationMetric] = []
    abs_errors: list[Decimal] = []
    sq_errors: list[float] = []
    for c_name in all_cats:
        p_c = _q2(pred_by_cat.get(c_name, Decimal("0.00")))
        a_c = _q2(act_by_cat.get(c_name, Decimal("0.00")))
        err = abs(p_c - a_c)
        abs_errors.append(err)
        sq_errors.append(float(err) ** 2)
        cat_metrics.append(
            CategoryEvaluationMetric(
                category_name=c_name,
                predicted_amount=p_c,
                actual_amount=a_c,
                absolute_error=_q2(err),
            )
        )

    mae = (
        _q2(sum(abs_errors, Decimal("0.00")) / Decimal(len(abs_errors)))
        if abs_errors
        else _q2(abs(pred_exp - act_exp))
    )
    rmse = (
        _q2(Decimal(str(math.sqrt(sum(sq_errors) / len(sq_errors)))))
        if sq_errors
        else _q2(abs(pred_exp - act_exp))
    )
    wape = (
        _q2((abs(pred_exp - act_exp) / act_exp) * Decimal("100"))
        if act_exp > Decimal("0.00")
        else None
    )
    bias = _q2(pred_exp - act_exp)

    ev = ForecastEvaluation(
        user_id=user_id,
        forecast_type="comprehensive",
        horizon_days=eval_window,
        cutoff_date=cutoff_date,
        eval_start_date=eval_start,
        eval_end_date=as_of_date,
        method=exp_fc.method,
        status="evaluated",
        predicted_expense=_q2(pred_exp),
        actual_expense=act_exp,
        predicted_income=_q2(pred_inc),
        actual_income=act_inc,
        predicted_net=pred_net,
        actual_net=act_net,
        mae_expense=mae,
        rmse_expense=rmse,
        wape_expense_pct=wape,
        bias_expense=bias,
        category_metrics=[m.model_dump(mode="json") for m in cat_metrics[:12]],
        notes=(
            f"Time-aware backtest trained strictly through {cutoff_date} ({len(pre_expenses)} expenses) "
            f"and evaluated against actuals in {eval_start}..{as_of_date} ({len(post_expenses)} expenses)."
        ),
    )
    db.add(ev)
    db.flush()
    return ev
