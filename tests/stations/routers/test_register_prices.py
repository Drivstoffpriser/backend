from decimal import Decimal

import sqlalchemy as sa

from app.core.db import DBSession
from app.stations.enums import FuelType
from app.stations.models import PriceRegistration
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory
from tests.users.factories import user_factory


async def test_register_prices_creates_records(
    client: AuthenticatedClient, db: DBSession, logged_in_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={
            "registrations": [
                {"fuelType": FuelType.DIESEL, "price": "20.00"},
                {"fuelType": FuelType.GASOLINE_95, "price": "22.90"},
            ]
        },
        authenticate_with=logged_in_user,
    )

    assert response.status_code == 201

    rows = await db.fetch_all(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
            PriceRegistration.is_latest.is_(True),
        )
    )
    by_fuel = {r.fuel_type: r for r in rows}
    assert by_fuel[FuelType.DIESEL].price == Decimal("20.00")
    assert by_fuel[FuelType.GASOLINE_95].price == Decimal("22.90")


async def test_register_prices_only_unsets_same_fuel_type(
    client: AuthenticatedClient, db: DBSession, logged_in_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")
    old_diesel = await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    old_gasoline = await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("22.00"),
    )

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={"registrations": [{"fuelType": FuelType.DIESEL, "price": "21.50"}]},
        authenticate_with=logged_in_user,
    )

    assert response.status_code == 201

    old_diesel_row = await db.fetch_one(
        sa.select(PriceRegistration).where(PriceRegistration.id == old_diesel.id)
    )
    assert old_diesel_row.is_latest is False

    old_gasoline_row = await db.fetch_one(
        sa.select(PriceRegistration).where(PriceRegistration.id == old_gasoline.id)
    )
    assert old_gasoline_row.is_latest is True

    new_diesel_row = await db.fetch_one(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
            PriceRegistration.fuel_type == FuelType.DIESEL,
            PriceRegistration.is_latest.is_(True),
        )
    )
    assert new_diesel_row.price == Decimal("21.50")


async def test_register_prices_rejects_price_below_min(
    client: AuthenticatedClient, db: DBSession, logged_in_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={"registrations": [{"fuelType": FuelType.DIESEL, "price": "9.99"}]},
        authenticate_with=logged_in_user,
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["type"] == "greater_than_equal"
    assert error["msg"] == "Input should be greater than or equal to 10"


async def test_register_prices_rejects_price_above_max(
    client: AuthenticatedClient, db: DBSession, logged_in_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={"registrations": [{"fuelType": FuelType.DIESEL, "price": "40.01"}]},
        authenticate_with=logged_in_user,
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["type"] == "less_than_equal"
    assert error["msg"] == "Input should be less than or equal to 40"


async def test_register_prices_rejects_duplicate_fuel_types(
    client: AuthenticatedClient, db: DBSession, logged_in_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={
            "registrations": [
                {"fuelType": FuelType.DIESEL, "price": "20.00"},
                {"fuelType": FuelType.DIESEL, "price": "21.00"},
            ]
        },
        authenticate_with=logged_in_user,
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["type"] == "value_error"
    assert error["msg"] == "Value error, Duplicate fuel types are not allowed"


async def test_register_prices_does_not_affect_other_stations(
    client: AuthenticatedClient, db: DBSession, logged_in_user: User
) -> None:
    s1 = await station_factory(db, external_id="node/1")
    s2 = await station_factory(db, external_id="node/2", lat=59.920, lng=10.760)
    other = await price_update_factory(
        db, station_id=s2.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )

    await client.post(
        f"/stations/{s1.id}/prices",
        json={"registrations": [{"fuelType": FuelType.DIESEL, "price": "21.50"}]},
        authenticate_with=logged_in_user,
    )

    row = await db.fetch_one(
        sa.select(PriceRegistration).where(PriceRegistration.id == other.id)
    )
    assert row.is_latest is True


async def test_register_prices_rejects_anonymous_user(
    client: AuthenticatedClient, db: DBSession
) -> None:
    station = await station_factory(db, external_id="node/1")
    anonymous_user = await user_factory(db=db, firebase_uid="anon-uid", email=None)

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={"registrations": [{"fuelType": FuelType.DIESEL, "price": "20.00"}]},
        authenticate_with=anonymous_user,
    )

    assert response.status_code == 403


async def test_register_prices_sets_registered_by_to_authenticated_user(
    client: AuthenticatedClient, db: DBSession, logged_in_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={"registrations": [{"fuelType": FuelType.DIESEL, "price": "20.00"}]},
        authenticate_with=logged_in_user,
    )

    assert response.status_code == 201

    row = await db.fetch_one(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
            PriceRegistration.is_latest.is_(True),
        )
    )
    assert row.registered_by == logged_in_user.id
