-- ============================================================
-- Big Brother — database schema (Supabase / Postgres)
-- Run once: Supabase -> SQL Editor -> New query -> paste -> Run
-- Safe to re-run (also upgrades the previous version).
-- ============================================================

-- upgrade from the previous version: remove the calculator/warehouse leftovers
drop function if exists bb_save_wallet(bigint, numeric, jsonb);

create or replace function bb_default_stop_words() returns text[]
language sql immutable as $$
  select array['чехол','стекло','пленка','ремешок','коробка','кабель',
               'запчасти','на запчасти','диск','эвакуатор','перевозка',
               'услуги','аренда','доставка','ремонт']::text[]
$$;

create table if not exists user_settings (
  user_id      bigint primary key,
  queries      text[]  not null default '{}',
  stop_words   text[]  not null default bb_default_stop_words(),
  search_limit int     not null default 3 check (search_limit between 1 and 10),
  updated_at   timestamptz not null default now(),
  check (cardinality(queries) <= 20)
);

alter table user_settings drop column if exists balance, drop column if exists items;

-- ads already sent to a user (so nothing is sent twice)
create table if not exists seen_ads (
  user_id    bigint      not null,
  ad_id      varchar(64) not null,
  created_at timestamptz not null default now(),
  primary key (user_id, ad_id)
);
create index if not exists seen_ads_created_idx on seen_ads (created_at);

-- queries whose first scan is done (first scan only "memorises" current ads)
create table if not exists seeded_queries (
  user_id bigint not null,
  query   text   not null,
  primary key (user_id, query)
);

-- Lock the tables completely for the public (anon) key.
alter table user_settings   enable row level security;
alter table seen_ads        enable row level security;
alter table seeded_queries  enable row level security;
revoke all on user_settings, seen_ads, seeded_queries from anon, authenticated;

-- The mini app can ONLY use these two functions (with validation + limits).
create or replace function bb_get(p_user_id bigint) returns json
language plpgsql security definer set search_path = public as $$
declare r user_settings;
begin
  if p_user_id is null or p_user_id <= 0 then raise exception 'bad user'; end if;
  select * into r from user_settings where user_id = p_user_id;
  if not found then
    return json_build_object(
      'exists', false, 'queries', '[]'::json,
      'stop_words', to_json(bb_default_stop_words()),
      'search_limit', 3);
  end if;
  return json_build_object(
    'exists', true, 'queries', to_json(r.queries),
    'stop_words', to_json(r.stop_words), 'search_limit', r.search_limit);
end $$;

create or replace function bb_save_settings(
  p_user_id bigint, p_queries text[], p_stop_words text[], p_limit int
) returns void
language plpgsql security definer set search_path = public as $$
declare q text[]; w text[];
begin
  if p_user_id is null or p_user_id <= 0 then raise exception 'bad user'; end if;
  select coalesce(array_agg(left(trim(t), 80) order by ord), '{}') into q
    from unnest(p_queries) with ordinality as u(t, ord) where trim(t) <> '';
  select coalesce(array_agg(left(trim(t), 40) order by ord), '{}') into w
    from unnest(p_stop_words) with ordinality as u(t, ord) where trim(t) <> '';
  q := q[1:20];
  w := w[1:100];
  insert into user_settings (user_id, queries, stop_words, search_limit)
  values (p_user_id, q, w, greatest(1, least(10, coalesce(p_limit, 3))))
  on conflict (user_id) do update set
    queries = excluded.queries,
    stop_words = excluded.stop_words,
    search_limit = excluded.search_limit,
    updated_at = now();
end $$;

revoke all on function bb_get(bigint)                         from public;
revoke all on function bb_save_settings(bigint,text[],text[],int) from public;
grant execute on function bb_get(bigint)                          to anon;
grant execute on function bb_save_settings(bigint,text[],text[],int) to anon;
-- The bot uses the Postgres connection string (owner role) and is not affected by RLS.
