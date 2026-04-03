from typing import cast

from geoalchemy2 import WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from shapely.geometry import Point


class CamelCaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class LocationSchema(BaseModel):
    lat: float
    lng: float

    @classmethod
    def from_wkb(cls, wkb: WKBElement | WKTElement) -> LocationSchema:
        point = cast(Point, to_shape(wkb))
        return cls(lat=point.y, lng=point.x)
