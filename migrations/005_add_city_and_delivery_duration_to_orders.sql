-- Migration 005: Add city and delivery duration columns to orders
-- Ensures orders schema is up-to-date across migrations

ALTER TABLE orders ADD COLUMN IF NOT EXISTS city VARCHAR(100) DEFAULT 'Bangalore';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_duration_minutes NUMERIC(4, 1) DEFAULT 7.5;
