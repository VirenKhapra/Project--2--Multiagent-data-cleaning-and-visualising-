from datetime import date
from types import SimpleNamespace

from app.api.analytics import _kpi_trend_base, _kpi_trend_rows_query, _rollup_kpi_trend_rows


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.replace('"', "").split())


def test_analytics_kpis_does_not_crash_with_status_grouping():
    sql = _normalize_sql(str(_kpi_trend_rows_query(_kpi_trend_base([], [])).compile(compile_kwargs={"literal_binds": True})))

    assert "FROM (SELECT" in sql
    assert "GROUP BY kpi_trend_base.day, kpi_trend_base.status" in sql
    assert sql.count("CASE") == 1


def test_analytics_kpis_groups_by_derived_status():
    sql = _normalize_sql(str(_kpi_trend_rows_query(_kpi_trend_base([], [])).compile(compile_kwargs={"literal_binds": True})))
    group_by_clause = sql.split("GROUP BY", 1)[1].split("ORDER BY", 1)[0]

    assert "kpi_trend_base.status" in group_by_clause
    assert "submissions.status" not in group_by_clause.lower()


def test_analytics_kpis_handles_pending_running_succeeded_failed_statuses():
    rolled = _rollup_kpi_trend_rows(
        [
            SimpleNamespace(day=date(2026, 6, 18), status="queued", uploads=2, records=5),
            SimpleNamespace(day=date(2026, 6, 18), status="planning", uploads=1, records=0),
            SimpleNamespace(day=date(2026, 6, 18), status="running", uploads=3, records=7),
            SimpleNamespace(day=date(2026, 6, 18), status="succeeded", uploads=4, records=9),
            SimpleNamespace(day=date(2026, 6, 18), status="failed", uploads=5, records=11),
        ]
    )

    assert rolled == [
        {
            "day": "2026-06-18",
            "uploads": 15,
            "queued": 2,
            "planning": 1,
            "running": 3,
            "succeeded": 4,
            "failed": 5,
            "quarantined": 0,
            "callback_failed": 0,
            "awaiting_schema_approval": 0,
            "awaiting_confirmation": 0,
            "declined": 0,
            "complete": 4,
            "awaiting_agent": 0,
            "pending": 3,
            "processing": 3,
            "records": 32,
        }
    ]
