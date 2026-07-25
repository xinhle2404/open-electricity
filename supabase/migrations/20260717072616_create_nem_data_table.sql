-- Fuel technology group taxonomy (Open Electricity's coarse fueltech categories).
-- Confirmed against live NEM data via secondary_grouping=fueltech_group.
create table fueltech_group (
  fueltech_group  text primary key
);

insert into fueltech_group (fueltech_group) values
    ('battery'),
    ('battery_charging'),
    ('battery_discharging'),
    ('bioenergy'),
    ('coal'),
    ('distillate'),
    ('gas'),
    ('hydro'),
    ('pumps'),
    ('solar'),
    ('wind');

-- Granular fuel technology codes, per Open Electricity's own documentation.
-- fueltech_group is nullable: aggregators (VPP/DR) genuinely have no single
-- fuel type, since they represent a fleet of underlying generators.
create table fueltech (
    fueltech    text primary key,
    fueltech_group  text references fueltech_group(fueltech_group),
    renewable   boolean not null
);

insert into fueltech (fueltech, fueltech_group, renewable) values
    ('aggregator_dr', null, true),
    ('aggregator_vpp', null, true),
    ('battery', 'battery', false),
    ('battery_charging', 'battery_charging', false),
    ('battery_discharging', 'battery_discharging', false),
    ('bioenergy_biogas', 'bioenergy', true),
    ('bioenergy_biomass', 'bioenergy', true),
    ('coal_black', 'coal', false),
    ('coal_brown', 'coal', false),
    ('distillate', 'distillate', false),
    ('exports', null, false),
    ('gas_ccgt', 'gas', false),
    ('gas_ocgt', 'gas', false),
    ('gas_recip', 'gas', false),
    ('gas_steam', 'gas', false),
    ('gas_wcmg', 'gas', false),
    ('hydro', 'hydro', true),
    ('imports', null, false),
    ('interconnector', null, false),
    ('nuclear', null, false),
    ('pumps', 'pumps', false),
    ('solar_rooftop', 'solar', true),
    ('solar_thermal', 'solar', true),
    ('solar_utility', 'solar', true),
    ('wind', 'wind', true),
    ('wind_offshore', 'wind', true);

-- Fact table: one row per (region, fueltech, interval)
create table nem_data (
    network_region  text not null,
    fueltech        text not null references fueltech(fueltech),
    interval_start  timestamptz not null,
    power_mw        numeric,
    energy_mwh      numeric,
    emissions_t     numeric,
    market_value_dollars    numeric,
    storage_battery_mwh     numeric,
    fetched_at      timestamptz not null default now(),
    unique (network_region, fueltech, interval_start)
);

create policy "Allow public read access" on fueltech for select to anon using (true);
create policy "Allow public read access" on nem_data for select to anon using (true);
create policy "Allow public read access" on fueltech_group for select to anon using (true);
