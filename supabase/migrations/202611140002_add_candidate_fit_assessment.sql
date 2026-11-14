alter table public.campaign_candidates
    add column if not exists fit_assessment jsonb;
