-- Ejecutar en Supabase > SQL Editor si las tablas principales ya existen.
-- Agrega la tabla y permisos necesarios para sincronizar subcategorías.

create table if not exists public.subcategories (
  id uuid primary key,
  category_id uuid not null references public.categories(id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now(),
  unique (category_id, name)
);

alter table public.transactions
  add column if not exists subcategory_id uuid references public.subcategories(id) on delete set null;

create index if not exists idx_subcategories_category on public.subcategories(category_id);
create index if not exists idx_transactions_subcategory on public.transactions(subcategory_id);

alter table public.subcategories enable row level security;
drop policy if exists "personal subcategories" on public.subcategories;
create policy "personal subcategories"
  on public.subcategories for all using (true) with check (true);

grant select, insert, update, delete on table public.subcategories to anon, authenticated;
