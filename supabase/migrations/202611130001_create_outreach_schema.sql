create table if not exists public.campaigns (
    id uuid primary key default gen_random_uuid(),
    name text not null check (char_length(name) between 1 and 120),
    segment text not null check (char_length(segment) between 1 and 500),
    status text not null default 'draft'
        check (status in ('draft', 'active', 'paused', 'archived')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.campaign_seeds (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    username text not null check (char_length(username) between 1 and 15),
    username_normalized text generated always as (lower(ltrim(username, '@'))) stored,
    created_at timestamptz not null default now(),
    unique (campaign_id, username_normalized)
);

create table if not exists public.candidates (
    id uuid primary key default gen_random_uuid(),
    username text not null check (char_length(username) between 1 and 15),
    username_normalized text generated always as (lower(ltrim(username, '@'))) stored unique,
    display_name text,
    bio text,
    location text,
    profile_url text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.campaign_candidates (
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    candidate_id uuid not null references public.candidates(id) on delete cascade,
    fit_score smallint check (fit_score between 0 and 100),
    fit_reason text not null check (char_length(fit_reason) between 1 and 1000),
    status text not null default 'identified'
        check (status in ('identified', 'drafted', 'approved', 'rejected')),
    created_at timestamptz not null default now(),
    primary key (campaign_id, candidate_id)
);

create table if not exists public.candidate_evidence (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null,
    candidate_id uuid not null,
    source_url text not null,
    source_type text not null check (source_type in ('profile', 'post', 'website', 'other')),
    excerpt text not null check (char_length(excerpt) between 1 and 3000),
    captured_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    foreign key (campaign_id, candidate_id)
        references public.campaign_candidates(campaign_id, candidate_id) on delete cascade,
    unique (campaign_id, candidate_id, source_url)
);

create table if not exists public.message_drafts (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null,
    candidate_id uuid not null,
    content text not null check (char_length(content) between 1 and 1000),
    status text not null default 'draft'
        check (status in ('draft', 'approved', 'rejected', 'send_pending', 'sent', 'replied', 'failed')),
    approved_at timestamptz,
    sent_at timestamptz,
    external_message_id text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (campaign_id, candidate_id)
        references public.campaign_candidates(campaign_id, candidate_id) on delete cascade
);

create unique index if not exists message_drafts_one_active_per_candidate
    on public.message_drafts (candidate_id)
    where status in ('draft', 'approved', 'send_pending', 'sent', 'replied', 'failed');

create index if not exists campaign_seeds_campaign_id_idx
    on public.campaign_seeds (campaign_id);
create index if not exists campaign_candidates_candidate_id_idx
    on public.campaign_candidates (candidate_id);
create index if not exists candidate_evidence_campaign_candidate_idx
    on public.candidate_evidence (campaign_id, candidate_id);
create index if not exists message_drafts_campaign_created_idx
    on public.message_drafts (campaign_id, created_at desc);

alter table public.campaigns enable row level security;
alter table public.campaign_seeds enable row level security;
alter table public.candidates enable row level security;
alter table public.campaign_candidates enable row level security;
alter table public.candidate_evidence enable row level security;
alter table public.message_drafts enable row level security;

revoke all on public.campaigns, public.campaign_seeds, public.candidates,
    public.campaign_candidates, public.candidate_evidence, public.message_drafts
    from anon, authenticated;
grant all on public.campaigns, public.campaign_seeds, public.candidates,
    public.campaign_candidates, public.candidate_evidence, public.message_drafts
    to service_role;
