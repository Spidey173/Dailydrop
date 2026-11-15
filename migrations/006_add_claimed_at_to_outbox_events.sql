-- Migration 006: Add claimed_at column to outbox_events
-- Enables recovery of stale IN_PROGRESS events when background workers crash or disconnect

ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_outbox_claimed_at ON outbox_events(status, claimed_at);
