-- Kill the Quote Spreadsheet: execute once in the Supabase SQL Editor.
create extension if not exists pgcrypto;

create table if not exists public.rfx_catalog (
  item_id text primary key,
  description text not null,
  uom text not null check (uom in ('piece', 'roll')),
  base_price numeric(12,2) not null check (base_price >= 0)
);

create table if not exists public.vendor_quotes (
  id uuid primary key default gen_random_uuid(),
  vendor_name text not null,
  currency char(3) not null default 'INR',
  payment_terms text,
  created_at timestamptz not null default now(),
  unique (vendor_name, created_at)
);

create table if not exists public.normalized_line_items (
  id uuid primary key default gen_random_uuid(),
  quote_id uuid not null references public.vendor_quotes(id) on delete cascade,
  rfx_item_id text references public.rfx_catalog(item_id),
  raw_description text not null,
  raw_price numeric(14,4),
  raw_unit text,
  raw_currency char(3),
  normalized_price_inr numeric(14,4),
  confidence_score numeric(4,3) not null check (confidence_score between 0 and 1),
  audit_trail jsonb not null default '[]'::jsonb,
  source_location text,
  created_at timestamptz not null default now(),
  unique (quote_id, rfx_item_id, raw_description)
);

create table if not exists public.vendor_clauses (
  id uuid primary key default gen_random_uuid(),
  quote_id uuid not null references public.vendor_quotes(id) on delete cascade,
  clause_type text not null,
  raw_text text not null,
  commercial_impact text,
  created_at timestamptz not null default now()
);

create index if not exists normalized_line_items_quote_item_idx
  on public.normalized_line_items (quote_id, rfx_item_id);
create index if not exists vendor_clauses_quote_idx on public.vendor_clauses (quote_id);

-- The demo uses a server-side service key. If you expose this schema to a browser,
-- enable RLS and write tenant-specific policies before granting client access.
alter table public.rfx_catalog enable row level security;
alter table public.vendor_quotes enable row level security;
alter table public.normalized_line_items enable row level security;
alter table public.vendor_clauses enable row level security;

-- Controlled, read-only endpoint for the AI co-pilot. It intentionally permits only
-- a single SELECT over the four public demo tables. Do not broaden this without auth.
create or replace function public.run_readonly_procurement_sql(query_text text)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare result jsonb;
begin
  if query_text !~* '^\s*select\s' or query_text ~ ';' or
     query_text ~* '(insert|update|delete|drop|alter|grant|revoke|copy|pg_)' or
     query_text !~* '(rfx_catalog|vendor_quotes|normalized_line_items|vendor_clauses)' then
    raise exception 'Only a single SELECT against procurement demo tables is allowed';
  end if;
  execute format('select coalesce(jsonb_agg(row_to_json(x)::jsonb), ''[]''::jsonb) from (%s) x', query_text)
    into result;
  return result;
end;
$$;
revoke all on function public.run_readonly_procurement_sql(text) from public;
grant execute on function public.run_readonly_procurement_sql(text) to service_role;

insert into public.rfx_catalog (item_id, description, uom, base_price) values
('PKG-001','3-ply corrugated carton 12 x 9 x 6 in','piece',28.00),
('PKG-002','5-ply corrugated carton 18 x 12 x 12 in','piece',58.00),
('PKG-003','7-ply corrugated carton 24 x 18 x 18 in','piece',115.00),
('PKG-004','Die-cut mailer 10 x 8 x 4 in','piece',22.00),
('PKG-005','Kraft paper roll 24 in x 50 m','roll',420.00),
('PKG-006','Bubble wrap roll 1 m x 50 m','roll',980.00),
('PKG-007','Stretch film roll 18 in x 300 m','roll',690.00),
('PKG-008','BOPP packing tape 2 in x 65 m','roll',42.00),
('PKG-009','Fragile label 100 x 50 mm','piece',1.20),
('PKG-010','Shipping label 100 x 150 mm','piece',0.85),
('PKG-011','Void fill paper roll 15 in x 250 m','roll',1250.00),
('PKG-012','Air pillow film roll 400 mm x 300 m','roll',1450.00),
('PKG-013','Poly mailer 10 x 12 in','piece',4.50),
('PKG-014','Poly mailer 14 x 16 in','piece',6.80),
('PKG-015','Zip lock pouch 6 x 8 in','piece',3.20),
('PKG-016','Zip lock pouch 10 x 12 in','piece',6.10),
('PKG-017','Corner protector 50 mm','piece',8.50),
('PKG-018','Edge board 50 x 50 x 1000 mm','piece',19.00),
('PKG-019','Wooden pallet 1200 x 1000 mm','piece',1250.00),
('PKG-020','Plastic pallet 1200 x 1000 mm','piece',1650.00),
('PKG-021','Carton sealing dispenser 2 in','piece',185.00),
('PKG-022','PP strapping roll 12 mm x 1000 m','roll',1120.00),
('PKG-023','Metal buckle 12 mm','piece',2.80),
('PKG-024','Silica gel sachet 5 g','piece',1.60),
('PKG-025','Thermal liner 1 m x 25 m','roll',1620.00),
('PKG-026','Foam sheet 2 mm 1 m x 50 m','roll',880.00),
('PKG-027','Carton cutter safety knife','piece',135.00),
('PKG-028','Document enclosed pouch A5','piece',3.50),
('PKG-029','Return label 100 x 150 mm','piece',1.10),
('PKG-030','Tamper-evident tape 2 in x 50 m','roll',78.00)
on conflict (item_id) do update set description = excluded.description, uom = excluded.uom, base_price = excluded.base_price;
