alter table public.candidates
    add column if not exists x_user_id text;

create unique index if not exists candidates_x_user_id_unique
    on public.candidates (x_user_id)
    where x_user_id is not null;

alter table public.message_drafts
    add column if not exists send_error text;

create table if not exists public.x_connections (
    id boolean primary key default true check (id),
    x_user_id text not null,
    username text not null,
    access_token_encrypted text not null,
    refresh_token_encrypted text,
    expires_at timestamptz,
    scopes text[] not null default '{}',
    connected_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.x_oauth_states (
    state_hash text primary key,
    code_verifier text not null,
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);

create table if not exists public.message_interactions (
    id uuid primary key default gen_random_uuid(),
    message_id uuid not null references public.message_drafts(id) on delete cascade,
    external_event_id text not null unique,
    event_type text not null,
    sender_x_user_id text,
    text text,
    occurred_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index if not exists message_interactions_message_occurred_idx
    on public.message_interactions (message_id, occurred_at desc);

alter table public.x_connections enable row level security;
alter table public.x_oauth_states enable row level security;
alter table public.message_interactions enable row level security;

revoke all on public.x_connections, public.x_oauth_states, public.message_interactions from anon, authenticated;
grant all on public.x_connections, public.x_oauth_states, public.message_interactions to service_role;
