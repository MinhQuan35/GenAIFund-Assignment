alter table public.candidates
    add column if not exists x_account_created_at timestamptz;
