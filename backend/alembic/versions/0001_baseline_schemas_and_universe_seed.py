"""baseline schemas and trading universe seed

Revision ID: 0001_baseline
Revises: -
Create Date: 2026-06-30

Creates:
  - reference schema: instrument, universe, universe_membership
  - market_data schema: ohlcv_bar (TimescaleDB hypertable)
  - Seeds the chartered trading universe and market-analysis universe.
"""

from datetime import date

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

TRADING_UNIVERSE = "default"
ANALYSIS_UNIVERSE = "analysis_indices"


def upgrade() -> None:
    # ---- schemas ----
    op.execute("CREATE SCHEMA IF NOT EXISTS reference")
    op.execute("CREATE SCHEMA IF NOT EXISTS market_data")

    # ---- reference.instrument ----
    op.create_table(
        "instrument",
        sa.Column("symbol", sa.String(16), primary_key=True),
        sa.Column("name", sa.String(255), server_default=""),
        sa.Column("asset_class", sa.String(32), server_default="equity"),
        sa.Column("sector", sa.String(64), nullable=True),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("is_index", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("tick_size", sa.Float, server_default="0.01"),
        sa.Column("created_at", sa.Date, server_default=sa.text("CURRENT_DATE")),
        schema="reference",
    )
    op.create_index("ix_instrument_asset_class", "instrument", ["asset_class"], schema="reference")
    op.create_index("ix_instrument_sector", "instrument", ["sector"], schema="reference")

    # ---- reference.universe ----
    op.create_table(
        "universe",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False),
        sa.Column("description", sa.String(512), server_default=""),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        schema="reference",
    )

    # ---- reference.universe_membership ----
    op.create_table(
        "universe_membership",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("universe_id", sa.Integer, nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("effective_from", sa.Date, server_default=sa.text("CURRENT_DATE")),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.UniqueConstraint("universe_id", "symbol", "effective_from"),
        schema="reference",
    )
    op.create_index("ix_um_universe_id", "universe_membership", ["universe_id"], schema="reference")
    op.create_index("ix_um_symbol", "universe_membership", ["symbol"], schema="reference")

    # ---- market_data.ohlcv_bar ----
    op.create_table(
        "ohlcv_bar",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("open", sa.Float, nullable=False),
        sa.Column("high", sa.Float, nullable=False),
        sa.Column("low", sa.Float, nullable=False),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("volume", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.UniqueConstraint("symbol", "timestamp"),
        schema="market_data",
    )
    op.create_index("ix_ohlcv_symbol_ts", "ohlcv_bar", ["symbol", "timestamp"], schema="market_data")
    op.create_index("ix_ohlcv_symbol", "ohlcv_bar", ["symbol"], schema="market_data")
    op.create_index("ix_ohlcv_timestamp", "ohlcv_bar", ["timestamp"], schema="market_data")

    # ---- TimescaleDB hypertable (safe: no-op if not TimescaleDB) ----
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                CREATE MATERIALIZED VIEW IF NOT EXISTS market_data.ohlcv_hypertable
                AS SELECT * FROM market_data.ohlcv_bar WITH NO DATA;
                PERFORM create_hypertable(
                    'market_data.ohlcv_bar', 'timestamp',
                    migrate_data => true, if_not_exists => true
                );
            END IF;
        END
        $$
    """)

    # ---- Seed universes ----
    today = date.today().isoformat()

    op.execute(f"""
        INSERT INTO reference.universe (name, description) VALUES
        ('{TRADING_UNIVERSE}', 'Default tradable universe'),
        ('{ANALYSIS_UNIVERSE}', 'Market analysis indices (no direct trading)')
        ON CONFLICT (name) DO NOTHING
    """)

    # ---- Seed trading universe (ADR-0004: data-driven, not hard-coded in source) ----
    trading_symbols = [
        # Technology
        ("AAPL", "Apple Inc.", "Technology"),
        ("MSFT", "Microsoft Corp.", "Technology"),
        ("NVDA", "NVIDIA Corp.", "Technology"),
        ("AMD", "Advanced Micro Devices", "Technology"),
        ("AVGO", "Broadcom Inc.", "Technology"),
        ("META", "Meta Platforms Inc.", "Technology"),
        ("AMZN", "Amazon.com Inc.", "Technology"),
        ("GOOGL", "Alphabet Inc.", "Technology"),
        # Semiconductors
        ("TSM", "Taiwan Semiconductor", "Semiconductors"),
        ("QCOM", "Qualcomm Inc.", "Semiconductors"),
        ("MU", "Micron Technology", "Semiconductors"),
        # Financial
        ("JPM", "JPMorgan Chase", "Financial"),
        ("GS", "Goldman Sachs", "Financial"),
        # Healthcare
        ("LLY", "Eli Lilly", "Healthcare"),
        ("UNH", "UnitedHealth Group", "Healthcare"),
        # Consumer
        ("COST", "Costco Wholesale", "Consumer"),
        ("WMT", "Walmart Inc.", "Consumer"),
        ("MCD", "McDonald's Corp.", "Consumer"),
        ("KO", "Coca-Cola Co.", "Consumer"),
        ("PEP", "PepsiCo Inc.", "Consumer"),
        # Industrials
        ("CAT", "Caterpillar Inc.", "Industrials"),
        ("GE", "GE Aerospace", "Industrials"),
    ]

    for symbol, name, sector in trading_symbols:
        op.execute(f"""
            INSERT INTO reference.instrument (symbol, name, sector)
            VALUES ('{symbol}', '{name}', '{sector}')
            ON CONFLICT (symbol) DO NOTHING
        """)

    # Add trading symbols to the default universe.
    for symbol, _, _ in trading_symbols:
        op.execute(f"""
            INSERT INTO reference.universe_membership (universe_id, symbol, effective_from)
            SELECT u.id, '{symbol}', '{today}'
            FROM reference.universe u WHERE u.name = '{TRADING_UNIVERSE}'
            ON CONFLICT DO NOTHING
        """)

    # ---- Seed analysis indices (is_index=true, never tradeable) ----
    analysis_symbols = [
        ("SPY", "S&P 500 ETF", "Index"),
        ("QQQ", "Nasdaq-100 ETF", "Index"),
        ("DIA", "Dow Jones ETF", "Index"),
        ("IWM", "Russell 2000 ETF", "Index"),
        ("VIX", "CBOE Volatility Index", "Index"),
    ]

    for symbol, name, sector in analysis_symbols:
        op.execute(f"""
            INSERT INTO reference.instrument (symbol, name, sector, is_index)
            VALUES ('{symbol}', '{name}', '{sector}', true)
            ON CONFLICT (symbol) DO NOTHING
        """)
        op.execute(f"""
            INSERT INTO reference.universe_membership (universe_id, symbol, effective_from)
            SELECT u.id, '{symbol}', '{today}'
            FROM reference.universe u WHERE u.name = '{ANALYSIS_UNIVERSE}'
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS market_data CASCADE")
    op.execute("DROP SCHEMA IF EXISTS reference CASCADE")
