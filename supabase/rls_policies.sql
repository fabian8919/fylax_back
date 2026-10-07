-- Políticas Row Level Security (PRD §8 y §10).
-- Segunda línea de defensa: aunque una query llegue sin filtro por
-- usuario desde el backend, Supabase impide leer datos ajenos.
-- Requisito: en users, id = auth.uid() (id enlazado a Supabase Auth).
-- Ejecutar en el SQL Editor de Supabase tras la migración inicial.

alter table public.users enable row level security;
alter table public.transactions enable row level security;
alter table public.categories enable row level security;
alter table public.email_sync_state enable row level security;

create policy "users_select_own" on public.users
  for select using (auth.uid() = id);
create policy "users_update_own" on public.users
  for update using (auth.uid() = id);

create policy "tx_select_own" on public.transactions
  for select using (auth.uid() = user_id);
create policy "tx_insert_own" on public.transactions
  for insert with check (auth.uid() = user_id);
create policy "tx_update_own" on public.transactions
  for update using (auth.uid() = user_id);
create policy "tx_delete_own" on public.transactions
  for delete using (auth.uid() = user_id);

create policy "sync_select_own" on public.email_sync_state
  for select using (auth.uid() = user_id);

-- categories: las del sistema (user_id IS NULL) las lee cualquier
-- usuario autenticado; las personalizadas solo su dueño.
alter table public.categories add column if not exists user_id uuid
  references public.users(id);
create policy "categories_select" on public.categories
  for select using (user_id is null or auth.uid() = user_id);
