-- Fylax: esquema completo para un proyecto Supabase NUEVO Y VACÍO.
-- Incluye migraciones 0001 a 0003, categorías iniciales y políticas RLS.
-- Ejecutar completo en Supabase SQL Editor. No ejecutar sobre una base que
-- ya use Alembic: en ese caso usar `alembic upgrade head` y rls_policies.sql.

BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_initial

CREATE TABLE users (
    id UUID NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    name VARCHAR(255) DEFAULT '' NOT NULL, 
    google_refresh_token TEXT, 
    subscription_tier VARCHAR(16) DEFAULT 'free' NOT NULL, 
    wompi_customer_id VARCHAR(128), 
    monthly_income NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
    monthly_budget NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    UNIQUE (email)
);

CREATE TABLE categories (
    id UUID NOT NULL, 
    user_id UUID, 
    name VARCHAR(120) NOT NULL, 
    icon VARCHAR(64) DEFAULT 'category' NOT NULL, 
    color VARCHAR(9) DEFAULT '#888888' NOT NULL, 
    type VARCHAR(16) DEFAULT 'expense' NOT NULL, 
    is_system_default BOOLEAN DEFAULT true NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_categories_user_id ON categories (user_id);

CREATE TABLE transactions (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    category_id UUID NOT NULL, 
    amount NUMERIC(10, 2) NOT NULL, 
    currency VARCHAR(3) DEFAULT 'COP' NOT NULL, 
    date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    merchant_clean VARCHAR(255) NOT NULL, 
    source VARCHAR(16) DEFAULT 'manual' NOT NULL, 
    source_ref_id VARCHAR(128), 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_tx_user_source_ref UNIQUE (user_id, source_ref_id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    FOREIGN KEY(category_id) REFERENCES categories (id)
);

CREATE INDEX ix_transactions_user_id ON transactions (user_id);

CREATE INDEX ix_transactions_user_date ON transactions (user_id, date);

CREATE TABLE email_sync_state (
    user_id UUID NOT NULL, 
    gmail_history_id VARCHAR(32), 
    last_sync_at TIMESTAMP WITHOUT TIME ZONE, 
    status VARCHAR(16) DEFAULT 'active' NOT NULL, 
    last_error TEXT, 
    PRIMARY KEY (user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE goals (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    target_amount NUMERIC(12, 2) NOT NULL, 
    saved_amount NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
    icon VARCHAR(64) DEFAULT 'savings' NOT NULL, 
    color VARCHAR(9) DEFAULT '#2E8FFF' NOT NULL, 
    deadline TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_goals_user_id ON goals (user_id);

INSERT INTO categories (id, user_id, name, icon, color, type, is_system_default) VALUES ('00000000-0000-4000-8000-000000000001', NULL, 'Domicilios', 'delivery', '#2E8FFF', 'expense', true);

INSERT INTO categories (id, user_id, name, icon, color, type, is_system_default) VALUES ('00000000-0000-4000-8000-000000000002', NULL, 'Restaurantes', 'restaurant', '#34E0A1', 'expense', true);

INSERT INTO categories (id, user_id, name, icon, color, type, is_system_default) VALUES ('00000000-0000-4000-8000-000000000003', NULL, 'Mercado', 'groceries', '#00D68F', 'expense', true);

INSERT INTO categories (id, user_id, name, icon, color, type, is_system_default) VALUES ('00000000-0000-4000-8000-000000000004', NULL, 'Transporte', 'transport', '#1E5EFF', 'expense', true);

INSERT INTO categories (id, user_id, name, icon, color, type, is_system_default) VALUES ('00000000-0000-4000-8000-000000000005', NULL, 'Suscripciones', 'subscriptions', '#5EB2FF', 'expense', true);

INSERT INTO categories (id, user_id, name, icon, color, type, is_system_default) VALUES ('00000000-0000-4000-8000-000000000006', NULL, 'Salud', 'health', '#7BE8C3', 'expense', true);

INSERT INTO categories (id, user_id, name, icon, color, type, is_system_default) VALUES ('00000000-0000-4000-8000-000000000007', NULL, 'Entretenimiento', 'entertainment', '#8FB8DE', 'expense', true);

INSERT INTO categories (id, user_id, name, icon, color, type, is_system_default) VALUES ('00000000-0000-4000-8000-000000000008', NULL, 'Servicios', 'services', '#3ECF8E', 'expense', true);

INSERT INTO categories (id, user_id, name, icon, color, type, is_system_default) VALUES ('00000000-0000-4000-8000-000000000009', NULL, 'Ingresos', 'income', '#00D68F', 'income', true);

INSERT INTO categories (id, user_id, name, icon, color, type, is_system_default) VALUES ('00000000-0000-4000-8000-000000000010', NULL, 'Otros', 'category', '#5C6B7A', 'expense', true);

INSERT INTO alembic_version (version_num) VALUES ('0001_initial') RETURNING alembic_version.version_num;

-- Running upgrade 0001_initial -> 0002_income_planning

ALTER TABLE users ADD COLUMN income_amount NUMERIC(12, 2) DEFAULT '0' NOT NULL;

ALTER TABLE users ADD COLUMN income_frequency VARCHAR(16) DEFAULT 'monthly' NOT NULL;

UPDATE users SET income_amount = monthly_income;

UPDATE alembic_version SET version_num='0002_income_planning' WHERE alembic_version.version_num = '0001_initial';

-- Running upgrade 0002_income_planning -> 0003_plan_alerts

CREATE TABLE plan_alerts (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    goal_id UUID NOT NULL, 
    kind VARCHAR(24) NOT NULL, 
    title VARCHAR(180) NOT NULL, 
    message TEXT NOT NULL, 
    period VARCHAR(7) NOT NULL, 
    read_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    FOREIGN KEY(goal_id) REFERENCES goals (id) ON DELETE CASCADE, 
    CONSTRAINT uq_plan_alert_period UNIQUE (user_id, goal_id, kind, period)
);

CREATE INDEX ix_plan_alerts_user_id ON plan_alerts (user_id);

CREATE INDEX ix_plan_alerts_user_created ON plan_alerts (user_id, created_at);

UPDATE alembic_version SET version_num='0003_plan_alerts' WHERE alembic_version.version_num = '0002_income_planning';

-- Row Level Security: cada usuario autenticado solo accede a sus datos.
alter table public.users enable row level security;
alter table public.transactions enable row level security;
alter table public.categories enable row level security;
alter table public.email_sync_state enable row level security;
alter table public.goals enable row level security;
alter table public.plan_alerts enable row level security;

drop policy if exists "users_select_own" on public.users;
create policy "users_select_own" on public.users
  for select using (auth.uid() = id);

drop policy if exists "users_update_own" on public.users;
create policy "users_update_own" on public.users
  for update using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "tx_select_own" on public.transactions;
create policy "tx_select_own" on public.transactions
  for select using (auth.uid() = user_id);

drop policy if exists "tx_insert_own" on public.transactions;
create policy "tx_insert_own" on public.transactions
  for insert with check (auth.uid() = user_id);

drop policy if exists "tx_update_own" on public.transactions;
create policy "tx_update_own" on public.transactions
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "tx_delete_own" on public.transactions;
create policy "tx_delete_own" on public.transactions
  for delete using (auth.uid() = user_id);

drop policy if exists "sync_select_own" on public.email_sync_state;
create policy "sync_select_own" on public.email_sync_state
  for select using (auth.uid() = user_id);

drop policy if exists "categories_select" on public.categories;
create policy "categories_select" on public.categories
  for select using (user_id is null or auth.uid() = user_id);

drop policy if exists "goals_select_own" on public.goals;
create policy "goals_select_own" on public.goals
  for select using (auth.uid() = user_id);

drop policy if exists "goals_insert_own" on public.goals;
create policy "goals_insert_own" on public.goals
  for insert with check (auth.uid() = user_id);

drop policy if exists "goals_update_own" on public.goals;
create policy "goals_update_own" on public.goals
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "goals_delete_own" on public.goals;
create policy "goals_delete_own" on public.goals
  for delete using (auth.uid() = user_id);

drop policy if exists "plan_alerts_select_own" on public.plan_alerts;
create policy "plan_alerts_select_own" on public.plan_alerts
  for select using (auth.uid() = user_id);

drop policy if exists "plan_alerts_update_own" on public.plan_alerts;
create policy "plan_alerts_update_own" on public.plan_alerts
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

COMMIT;

