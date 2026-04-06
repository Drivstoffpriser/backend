"""Tests for sync_stations_from_firestore."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import app.stations.sync
from app.core.config import get_settings
from app.core.db import DBSession
from app.core.db import db as app_db
from app.stations.enums import ProviderType
from app.stations.models import Station
from app.stations.sync import sync_stations_from_firestore


@pytest.fixture(autouse=True)
async def null_pool_sync_engine() -> AsyncGenerator[None]:
    # Replace db._engine with NullPool so sync works across per-function event loops.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    with patch.object(app_db, "_engine", engine):
        yield
    async with engine.begin() as conn:
        await conn.execute(sa.delete(Station))
    await engine.dispose()


def _patch_firestore(docs: list[dict[str, Any]]) -> Any:
    return patch.object(
        app.stations.sync,
        "fetch_all_stations_sync",
        return_value=docs,
    )


async def test_valid_station_is_synced(db: DBSession) -> None:
    docs = [
        {
            "id": "node/1",
            "name": "Circle K Majorstuen",
            "brand": "Circle K",
            "longitude": 10.752,
            "latitude": 59.911,
            "address": "Bogstadveien 1",
            "city": "Oslo",
        }
    ]

    with _patch_firestore(docs):
        await sync_stations_from_firestore()

    station = await db.fetch_one(
        sa.select(Station).where(Station.external_id == "node/1")
    )
    assert station.name == "Circle K Majorstuen"
    assert station.provider == ProviderType.CIRCLE_K
    assert station.address == "Bogstadveien 1"
    assert station.city == "Oslo"


async def test_station_missing_required_field_is_skipped(db: DBSession) -> None:
    docs = [{"id": "node/2", "name": "No Coords", "brand": "Circle K"}]

    with _patch_firestore(docs):
        await sync_stations_from_firestore()

    result = await db.fetch_one_or_none(
        sa.select(Station).where(Station.external_id == "node/2")
    )
    assert result is None


async def test_station_with_unknown_brand_is_skipped(db: DBSession) -> None:
    docs = [
        {
            "id": "node/3",
            "name": "Mystery Station",
            "brand": "NoSuchBrand",
            "longitude": 10.0,
            "latitude": 60.0,
        }
    ]

    with _patch_firestore(docs):
        await sync_stations_from_firestore()

    result = await db.fetch_one_or_none(
        sa.select(Station).where(Station.external_id == "node/3")
    )
    assert result is None


async def test_station_with_no_brand_is_skipped(db: DBSession) -> None:
    docs = [
        {
            "id": "node/4",
            "name": "No Brand Station",
            "longitude": 10.0,
            "latitude": 60.0,
        }
    ]

    with _patch_firestore(docs):
        await sync_stations_from_firestore()

    result = await db.fetch_one_or_none(
        sa.select(Station).where(Station.external_id == "node/4")
    )
    assert result is None


async def test_existing_station_is_updated(db: DBSession) -> None:
    docs = [
        {
            "id": "node/5",
            "name": "Old Name",
            "brand": "YX",
            "longitude": 10.0,
            "latitude": 60.0,
            "city": "Bergen",
        }
    ]
    with _patch_firestore(docs):
        await sync_stations_from_firestore()

    docs[0]["name"] = "New Name"
    docs[0]["city"] = "Stavanger"
    with _patch_firestore(docs):
        await sync_stations_from_firestore()

    station = await db.fetch_one(
        sa.select(Station).where(Station.external_id == "node/5")
    )
    assert station.name == "New Name"
    assert station.city == "Stavanger"


async def test_optional_fields_default_to_empty_string(db: DBSession) -> None:
    docs = [
        {
            "id": "node/6",
            "name": "Minimal Station",
            "brand": "Esso",
            "longitude": 10.0,
            "latitude": 60.0,
        }
    ]

    with _patch_firestore(docs):
        await sync_stations_from_firestore()

    station = await db.fetch_one(
        sa.select(Station).where(Station.external_id == "node/6")
    )
    assert station.address == ""
    assert station.city == ""


async def test_valid_and_invalid_stations_mixed(db: DBSession) -> None:
    docs: list[dict[str, Any]] = [
        {
            "id": "node/7",
            "name": "Valid Station",
            "brand": "St1",
            "longitude": 10.0,
            "latitude": 60.0,
        },
        {"id": "node/8", "name": "Missing Coords", "brand": "St1"},
        {
            "id": "node/9",
            "name": "Unknown Brand",
            "brand": "Fake",
            "longitude": 10.0,
            "latitude": 60.0,
        },
    ]

    with _patch_firestore(docs):
        await sync_stations_from_firestore()

    valid = await db.fetch_one_or_none(
        sa.select(Station).where(Station.external_id == "node/7")
    )
    assert valid is not None

    skipped_missing = await db.fetch_one_or_none(
        sa.select(Station).where(Station.external_id == "node/8")
    )
    assert skipped_missing is None

    skipped_brand = await db.fetch_one_or_none(
        sa.select(Station).where(Station.external_id == "node/9")
    )
    assert skipped_brand is None
