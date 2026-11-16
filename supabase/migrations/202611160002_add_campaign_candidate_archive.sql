alter table public.campaign_candidates
    add column if not exists removed_at timestamptz;

create index if not exists campaign_candidates_active_idx
    on public.campaign_candidates (campaign_id, created_at desc)
    where removed_at is null;
