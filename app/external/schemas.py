from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.core.schemas import CamelCaseModel, LocationSchema
from app.stations.enums import FuelType, ProviderType
from app.stations.models import PriceRegistration, Station


class ExternalPriceSchema(CamelCaseModel):
    fuel_type: FuelType
    price: Decimal
    registered_at: datetime


class ExternalStationSchema(CamelCaseModel):
    id: UUID
    external_id: str
    name: str
    provider: ProviderType
    address: str
    city: str
    location: LocationSchema
    prices: list[ExternalPriceSchema] = []


class ExternalGetStationsResponseBody(CamelCaseModel):
    stations: list[ExternalStationSchema]

    @classmethod
    def from_models(
        cls,
        stations: list[Station],
        prices_by_station: dict[UUID, list[PriceRegistration]],
    ) -> ExternalGetStationsResponseBody:
        return cls(
            stations=[
                ExternalStationSchema(
                    id=station.id,
                    external_id=station.external_id,
                    name=station.name,
                    provider=station.provider,
                    address=station.address,
                    city=station.city,
                    location=LocationSchema.from_wkb(station.location),
                    prices=[
                        ExternalPriceSchema(
                            fuel_type=p.fuel_type,
                            price=p.price,
                            registered_at=p.registered_at,
                        )
                        for p in prices_by_station.get(station.id, [])
                    ],
                )
                for station in stations
            ]
        )
