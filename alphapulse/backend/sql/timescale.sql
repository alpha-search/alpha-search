-- AlphaPulse TimescaleDB time-series schema.
--
-- Run AFTER the relational tables (Prisma migrate / create_all) exist. This
-- file owns the high-ingestion financial metrics that would overwhelm a normal
-- B-tree table at scale. Apply with:
--   psql "$DATABASE_URL" -f sql/timescale.sql

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- --------------------------------------------------------------------------
-- Raw OHLCV / intraday price ticks. One row per (symbol, interval, ts).
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticker_metrics (
    symbol      VARCHAR(16)      NOT NULL,
    ts          TIMESTAMPTZ      NOT NULL,
    interval    VARCHAR(8)       NOT NULL DEFAULT '1d',  -- 1m, 5m, 1h, 1d
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    volume      BIGINT           NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, interval, ts)
);

-- Convert to a hypertable partitioned weekly on time, sharded by symbol.
SELECT create_hypertable(
    'ticker_metrics',
    'ts',
    partitioning_column => 'symbol',
    number_partitions   => 8,
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS ix_ticker_metrics_symbol_ts
    ON ticker_metrics (symbol, ts DESC);

-- --------------------------------------------------------------------------
-- Compression: compress chunks older than 14 days to slash storage on the
-- long tail of historical bars while keeping recent data hot.
-- --------------------------------------------------------------------------
ALTER TABLE ticker_metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, interval',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('ticker_metrics', INTERVAL '14 days', if_not_exists => TRUE);

-- --------------------------------------------------------------------------
-- Continuous aggregate: daily OHLCV rolled up from intraday ticks, refreshed
-- automatically. Powers the chart endpoint without scanning raw ticks.
-- --------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS ticker_metrics_daily
WITH (timescaledb.continuous) AS
SELECT
    symbol,
    time_bucket('1 day', ts)            AS bucket,
    first(open, ts)                     AS open,
    max(high)                           AS high,
    min(low)                            AS low,
    last(close, ts)                     AS close,
    sum(volume)                         AS volume
FROM ticker_metrics
GROUP BY symbol, time_bucket('1 day', ts)
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'ticker_metrics_daily',
    start_offset      => INTERVAL '30 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists     => TRUE
);

-- --------------------------------------------------------------------------
-- Retention: drop raw 1-minute ticks after 90 days (the daily continuous
-- aggregate retains the long history).
-- --------------------------------------------------------------------------
SELECT add_retention_policy('ticker_metrics', INTERVAL '90 days', if_not_exists => TRUE);
