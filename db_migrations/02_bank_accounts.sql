-- Migration: Encrypted bank accounts for statement integrations
create extension if not exists "pgcrypto";

create table if not exists crm_bank_accounts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    provider text not null check (provider in ('privatbank','monobank','custom')),
    provider_api text not null,
    account_mask text,
    account_number_encrypted text not null,
    api_key_encrypted text not null,
    encryption_method text not null default 'fernet',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create unique index if not exists idx_bank_accounts_unique
    on crm_bank_accounts(user_id, provider, provider_api, account_mask);

alter table crm_bank_accounts enable row level security;

-- Allow user to manage only their own bank accounts
create policy if not exists bank_accounts_self_select
    on crm_bank_accounts for select
    using (auth.uid() = user_id);

create policy if not exists bank_accounts_self_modify
    on crm_bank_accounts for insert with check (auth.uid() = user_id);

create policy if not exists bank_accounts_self_update
    on crm_bank_accounts for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy if not exists bank_accounts_self_delete
    on crm_bank_accounts for delete using (auth.uid() = user_id);

-- Service role (e.g. from backend) gets full access
create policy if not exists bank_accounts_service_all
    on crm_bank_accounts for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
