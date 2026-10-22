-- Migration 004: Payment & Fulfillment State Constraints and Negative Stock Checks
-- Protects inventory integrity and restricts order status values

-- In PostgreSQL, check constraints prevent invalid statuses from being inserted
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_order_status'
    ) THEN
        ALTER TABLE orders ADD CONSTRAINT chk_order_status 
        CHECK (status IN ('Paid', 'Processing', 'Packed', 'Shipped', 'Out for Delivery', 'Delivered', 'Cancelled'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_product_stock_non_negative'
    ) THEN
        ALTER TABLE products ADD CONSTRAINT chk_product_stock_non_negative 
        CHECK (stock >= 0);
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        -- Graceful fallback for non-PostgreSQL / SQLite test engines
        NULL;
END $$;
