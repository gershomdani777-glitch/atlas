from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Datastores (override with real Supabase/Upstash URLs in .env)
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/atlas"
    redis_url: str = "redis://localhost:6379/0"

    # LLM (Google Gemini free tier)
    google_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    llm_timeout_seconds: float = 20.0

    # Market data ingestion
    binance_ws_base: str = "wss://stream.binance.com:9443"
    asset_universe: str = "btcusdt,ethusdt,solusdt,bnbusdt,xrpusdt,dogeusdt"
    depth_stream_levels: int = 20
    staleness_ttl_seconds: int = 10
    # Binance's depth stream alone fires 10x/second/symbol; the agent only
    # reads Redis once per agent_cycle_seconds, so writes are throttled to
    # this interval to avoid burning a free-tier Upstash command budget for
    # updates nothing will read. Must stay comfortably under
    # staleness_ttl_seconds or perceive() would see false-stale data.
    redis_write_interval_seconds: float = 4.0

    # Agent loop
    agent_cycle_seconds: int = 30
    memory_top_k: int = 3

    # Default risk config (seeded into risk_config table on first init)
    default_max_position_pct: float = 0.12
    default_max_exposure_pct: float = 0.45
    default_max_asset_exposure_pct: float = 0.20
    default_drawdown_stop_pct: float = 0.08
    default_kelly_fraction: float = 0.25
    default_min_edge_over_cost_bps: float = 8.0
    starting_capital: float = 100000.0

    # API
    cors_origins: str = "http://localhost:3000"

    @property
    def asset_list(self) -> list[str]:
        return [a.strip().lower() for a in self.asset_universe.split(",") if a.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
