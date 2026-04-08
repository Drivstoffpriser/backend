-- Insert 2 price registrations per day over the last 60 days, for each fuel type
-- for station 8188dcf8-fe49-44f8-bd72-9b9b0db5bc8f
INSERT INTO price_registration (station_id, fuel_type, price, registered_at, registered_by, is_latest)
SELECT
    '8188dcf8-fe49-44f8-bd72-9b9b0db5bc8f',
    fuel_type,
    round((18 + random() * 6)::numeric, 2),
    now() - (day || ' days')::interval - (entry * 8 || ' hours')::interval,
    NULL,
    false
FROM generate_series(0, 59) AS gs(day)
CROSS JOIN unnest(ARRAY['DIESEL', 'GASOLINE_95', 'GASOLINE_98']::text[]) AS fuel_type
CROSS JOIN generate_series(1, 2) AS entry;

-- Mark the most recent registration per fuel type as is_latest
UPDATE price_registration pr
SET is_latest = true
WHERE pr.station_id = '8188dcf8-fe49-44f8-bd72-9b9b0db5bc8f'
  AND pr.registered_at = (
      SELECT max(registered_at)
      FROM price_registration
      WHERE station_id = pr.station_id
        AND fuel_type = pr.fuel_type
  );
