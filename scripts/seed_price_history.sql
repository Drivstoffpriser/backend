-- Insert 2 price registrations per day over the last 60 days, for each fuel type
-- for station bfde3b3f-2a93-4c6a-a621-dcb3fb93b805
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
  'e08f7b61-4d0a-4cc3-af8a-ab4769ba5d3b',
  fuel_type,
  round((18 + random() * 6) :: numeric, 2),
  NOW() - (DAY || ' days') :: INTERVAL - (entry * 8 || ' hours') :: INTERVAL,
  NULL,
  false
FROM
  generate_series(0, 59) AS gs(DAY)
  CROSS JOIN unnest(
    ARRAY ['DIESEL', 'GASOLINE_95', 'GASOLINE_98'] :: text []
  ) AS fuel_type
  CROSS JOIN generate_series(1, 2) AS entry;

-- Mark the most recent registration per fuel type as is_latest, only if none is already marked
UPDATE
  price_registration pr
SET
  is_latest = TRUE
WHERE
  pr.station_id = 'e08f7b61-4d0a-4cc3-af8a-ab4769ba5d3b'
  AND pr.registered_at = (
    SELECT
      max(registered_at)
    FROM
      price_registration
    WHERE
      station_id = pr.station_id
      AND fuel_type = pr.fuel_type
  )
  AND NOT EXISTS (
    SELECT
      1
    FROM
      price_registration
    WHERE
      station_id = pr.station_id
      AND fuel_type = pr.fuel_type
      AND is_latest = TRUE
  );
