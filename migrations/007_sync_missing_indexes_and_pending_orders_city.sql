-- Migration 007: Sync missing indexes and pending_orders city column from legacy init_database
-- Ensures complete parity between migration-driven schema and runtime database requirements

-- 1. Add missing city column to pending_orders if not present
ALTER TABLE pending_orders ADD COLUMN IF NOT EXISTS city VARCHAR(100) DEFAULT 'Bangalore';

-- 2. Add missing performance indexes identified during schema audit
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_wishlist_user_id ON wishlist(user_id);
CREATE INDEX IF NOT EXISTS idx_wishlist_product_id ON wishlist(product_id);
CREATE INDEX IF NOT EXISTS idx_outbox_status_created ON outbox_events(status, created_at);
CREATE INDEX IF NOT EXISTS idx_outbox_event_id ON outbox_events(event_id);
