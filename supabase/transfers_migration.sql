-- Migración repetible para transferencias de una sola fila.
alter table public.transactions add column if not exists destination_account_id uuid references public.accounts(id) on delete cascade;
create index if not exists idx_transactions_destination_account on public.transactions(destination_account_id);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'transactions_transfer_shape') then
    alter table public.transactions add constraint transactions_transfer_shape check (
      (transaction_type = 'transfer' and destination_account_id is not null and category_id is null and subcategory_id is null and destination_account_id <> account_id)
      or (transaction_type <> 'transfer' and destination_account_id is null)
    );
  end if;
end $$;
