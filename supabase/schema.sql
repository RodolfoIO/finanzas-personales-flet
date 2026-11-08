-- Ejecutar en Supabase > SQL Editor.
-- La app utiliza la API REST con SUPABASE_URL y SUPABASE_KEY.
create table if not exists public.categories (
  id uuid primary key,
  name text not null unique,
  color text not null default '#64748B',
  monthly_budget numeric not null default 0,
  created_at timestamptz not null default now()
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
  transaction_date date not null,
  description text not null,
  amount numeric not null,
  transaction_type text not null default 'expense',
  source text not null default 'manual',
  source_hash text unique,
  notes text not null default '',
  created_at timestamptz not null default now()
);

alter table public.categories enable row level security;
alter table public.accounts enable row level security;
alter table public.transactions enable row level security;

-- MVP personal. Si se publica en internet, sustituir por políticas con Supabase Auth.
create policy "personal categories" on public.categories for all using (true) with check (true);
create policy "personal accounts" on public.accounts for all using (true) with check (true);
create policy "personal transactions" on public.transactions for all using (true) with check (true);
