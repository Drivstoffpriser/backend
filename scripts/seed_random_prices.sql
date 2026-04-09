-- Insert 2 price registrations per fuel type for each station,
-- randomly distributed within the last 3 days
INSERT INTO
  price_registration (
    station_id,
    fuel_type,
    price,
    registered_at,
    registered_by,
    is_latest
  )
SELECT
  s.id,
  fuel_type,
  round((18 + random() * 6) :: numeric, 2),
  NOW() - (random() * 3 || ' days') :: INTERVAL,
  NULL,
  false
FROM
  station s
  CROSS JOIN unnest(
    ARRAY ['DIESEL', 'GASOLINE_95', 'GASOLINE_98'] :: text []
  ) AS fuel_type
  CROSS JOIN generate_series(1, 2) AS entry;

-- Mark the most recent registration per fuel type per station as is_latest
UPDATE
  price_registration pr
SET
  is_latest = TRUE
WHERE
  pr.registered_at = (
    SELECT
      max(registered_at)
    FROM
      price_registration
    WHERE
      station_id = pr.station_id
      AND fuel_type = pr.fuel_type
  );
