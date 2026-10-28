-- Políticas Row Level Security de Fylax.
-- Ejecutar después de las migraciones Alembic o incluirlas en schema.sql.
-- Cada usuario autenticado solo puede acceder a sus propios datos.
-- El backend se conecta con credenciales de servicio y aplica además sus
-- propios filtros por user_id en todas las consultas.

alter table public.users enable row level security;
alter table public.transactions enable row level security;
alter table public.categories enable row level security;
alter table public.email_sync_state enable row level security;
alter table public.goals enable row level security;
alter table public.plan_alerts enable row level security;

-- Usuarios: lectura y actualización del propio perfil.
drop policy if exists "users_select_own" on public.users;
create policy "users_select_own" on public.users
  for select using (auth.uid() = id);

drop policy if exists "users_update_own" on public.users;
create policy "users_update_own" on public.users
  for update using (auth.uid() = id) with check (auth.uid() = id);

-- Movimientos: acceso completo únicamente a los del propietario.
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

-- Sincronización: el usuario solo consulta su propio estado.
drop policy if exists "sync_select_own" on public.email_sync_state;
create policy "sync_select_own" on public.email_sync_state
  for select using (auth.uid() = user_id);

-- Categorías: las globales son visibles; las personalizadas son privadas.
drop policy if exists "categories_select" on public.categories;
create policy "categories_select" on public.categories
  for select using (user_id is null or auth.uid() = user_id);

-- Propósitos: lectura y gestión únicamente por su propietario.
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

-- Alertas: se crean desde el backend; el usuario las lee y marca como leídas.
drop policy if exists "plan_alerts_select_own" on public.plan_alerts;
create policy "plan_alerts_select_own" on public.plan_alerts
  for select using (auth.uid() = user_id);

drop policy if exists "plan_alerts_update_own" on public.plan_alerts;
create policy "plan_alerts_update_own" on public.plan_alerts
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
