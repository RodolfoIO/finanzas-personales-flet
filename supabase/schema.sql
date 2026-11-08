-- Ejecutar en Supabase > SQL Editor.
-- La app utiliza la API REST con SUPABASE_URL y SUPABASE_KEY.
create table if not exists public.categories (
  id uuid primary key,
  name text not null unique,
  color text not null default '#64748B',
  monthly_budget numeric not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.subcategories (
  id uuid primary key,
  category_id uuid not null references public.categories(id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now(),
  unique (category_id, name)
);

create table if not exists public.accounts (
  id uuid primary key,
  name text not null,
  institution text not null default '',
  account_type text not null default 'cuenta',
  currency text not null default 'GTQ',
  current_balance numeric not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.transactions (
  id uuid primary key,
  account_id uuid not null references public.accounts(id) on delete cascade,
  category_id uuid references public.categories(id) on delete set null,
  subcategory_id uuid references public.subcategories(id) on delete set null,
  transaction_date date not null,
  description text not null,
  amount numeric not null,
  transaction_type text not null default 'expense',
  source text not null default 'manual',
  source_hash text unique,
  notes text not null default '',
  created_at timestamptz not null default now()
);

alter table public.transactions add column if not exists subcategory_id uuid references public.subcategories(id) on delete set null;
create index if not exists idx_subcategories_category on public.subcategories(category_id);
create index if not exists idx_transactions_subcategory on public.transactions(subcategory_id);

alter table public.categories enable row level security;
alter table public.subcategories enable row level security;
alter table public.accounts enable row level security;
alter table public.transactions enable row level security;

-- MVP personal. Si se publica en internet, sustituir por políticas con Supabase Auth.
drop policy if exists "personal categories" on public.categories;
drop policy if exists "personal subcategories" on public.subcategories;
drop policy if exists "personal accounts" on public.accounts;
drop policy if exists "personal transactions" on public.transactions;
create policy "personal categories" on public.categories for all using (true) with check (true);
create policy "personal subcategories" on public.subcategories for all using (true) with check (true);
create policy "personal accounts" on public.accounts for all using (true) with check (true);
create policy "personal transactions" on public.transactions for all using (true) with check (true);

-- Necesario si el proyecto restringe la exposición automática de tablas al Data API.
grant select, insert, update, delete on table public.subcategories to anon, authenticated;
