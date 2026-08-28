"""One-shot schema bootstrap: run `python -m db.init_db` from backend/.

Creates the pgvector extension, all tables, seeds `assets` from the
configured universe, seeds default `risk_config` rows, and ensures the
`agent_runtime` singleton row exists. Safe to re-run (idempotent).
"""

from sqlalchemy import text

from config import settings
from db.models import AgentRuntime, Asset, Base, RiskConfig
from db.session import engine, get_session


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)

    with get_session() as session:
        existing_symbols = {a.symbol for a in session.query(Asset).all()}
        for symbol in settings.asset_list:
            if symbol in existing_symbols:
                continue
            quote = "usdt"
            base = symbol[: -len(quote)] if symbol.endswith(quote) else symbol
            session.add(Asset(symbol=symbol, base_asset=base, quote_asset=quote, exchange="binance"))

        defaults = {
            "max_position_pct": settings.default_max_position_pct,
            "max_exposure_pct": settings.default_max_exposure_pct,
            "max_asset_exposure_pct": settings.default_max_asset_exposure_pct,
            "drawdown_stop_pct": settings.default_drawdown_stop_pct,
            "kelly_fraction": settings.default_kelly_fraction,
            "min_edge_over_cost_bps": settings.default_min_edge_over_cost_bps,
        }
        existing_keys = {r.config_key for r in session.query(RiskConfig).all()}
        for key, value in defaults.items():
            if key not in existing_keys:
                session.add(RiskConfig(config_key=key, config_value=value, updated_by="init"))

        if session.get(AgentRuntime, 1) is None:
            session.add(
                AgentRuntime(
                    id=1,
                    is_running=True,
                    cycle=0,
                    capital=settings.starting_capital,
                    peak_equity=settings.starting_capital,
                )
            )

    print("ATLAS DB initialized: extension, tables, seeded assets/risk_config/agent_runtime.")


if __name__ == "__main__":
    init_db()
