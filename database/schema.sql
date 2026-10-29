-- CreditGuard: exact existing columns, foreign keys and added indexes.

-- Empty PostgreSQL/Supabase database setup. All timestamps are naive UTC.

-- Run in Supabase SQL Editor OR use python database/init_database.py.

-- Existing tables are preserved. This is initialization, not a migration engine.

BEGIN;

SET LOCAL search_path TO public;

CREATE TABLE IF NOT EXISTS customers (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(180) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (email)
);

ALTER TABLE public.customers ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS transactions (
	id SERIAL NOT NULL, 
	customer_id INTEGER NOT NULL, 
	amount FLOAT NOT NULL, 
	merchant VARCHAR(120) NOT NULL, 
	category VARCHAR(80) NOT NULL, 
	location VARCHAR(120) NOT NULL, 
	hour INTEGER NOT NULL, 
	distance_from_home FLOAT NOT NULL, 
	distance_from_last_transaction FLOAT NOT NULL, 
	ratio_to_median_purchase_price FLOAT NOT NULL, 
	repeat_retailer BOOLEAN NOT NULL, 
	used_chip BOOLEAN NOT NULL, 
	used_pin_number BOOLEAN NOT NULL, 
	online_order BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);

CREATE INDEX IF NOT EXISTS ix_transactions_created_id ON transactions (created_at, id);

CREATE INDEX IF NOT EXISTS ix_transactions_customer_created ON transactions (customer_id, created_at);

CREATE INDEX IF NOT EXISTS ix_transactions_customer_id ON transactions (customer_id);

ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS fraud_alerts (
	id SERIAL NOT NULL, 
	transaction_id INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (transaction_id), 
	FOREIGN KEY(transaction_id) REFERENCES transactions (id)
);

CREATE INDEX IF NOT EXISTS ix_alerts_status_id ON fraud_alerts (status, id);

ALTER TABLE public.fraud_alerts ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS predictions (
	id SERIAL NOT NULL, 
	transaction_id INTEGER NOT NULL, 
	fraud_probability FLOAT NOT NULL, 
	predicted_fraud BOOLEAN NOT NULL, 
	risk_level VARCHAR(20) NOT NULL, 
	model_version VARCHAR(50) NOT NULL, 
	explanation JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (transaction_id), 
	FOREIGN KEY(transaction_id) REFERENCES transactions (id)
);

CREATE INDEX IF NOT EXISTS ix_predictions_fraud_transaction ON predictions (predicted_fraud, transaction_id);

ALTER TABLE public.predictions ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE format('REVOKE ALL ON TABLE public.customers, public.transactions, public.predictions, public.fraud_alerts FROM %I', role_name);
    END IF;
  END LOOP;
END $$;

COMMIT;
