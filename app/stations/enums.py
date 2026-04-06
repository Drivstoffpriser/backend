from enum import StrEnum


class ProviderType(StrEnum):
    AUTOMAT_1 = "AUTOMAT_1"
    BEST = "BEST"
    BUNKER_OIL = "BUNKER_OIL"
    CIRCLE_K = "CIRCLE_K"
    DRIV = "DRIV"
    ESSO = "ESSO"
    HALTBAKK_EXPRESS = "HALTBAKK_EXPRESS"
    OLJELEVERANDØREN = "OLJELEVERANDØREN"
    ST1 = "ST1"
    TANKEN = "TANKEN"
    TRONDER_OIL = "TRONDER_OIL"
    UNO_X = "UNO_X"
    YX = "YX"
    YX_TRUCK = "YX_TRUCK"


class FuelType(StrEnum):
    DIESEL = "DIESEL"
    GASOLINE_95 = "GASOLINE_95"
    GASOLINE_98 = "GASOLINE_98"


class PriceRegistrationSourceType(StrEnum):
    USER = "USER"
    FIRESTORE = "FIRESTORE"


FIRESTORE_FUEL_TYPE_MAP: dict[str, FuelType] = {
    "diesel": FuelType.DIESEL,
    "petrol95": FuelType.GASOLINE_95,
    "petrol98": FuelType.GASOLINE_98,
}

BRAND_TO_PROVIDER: dict[str, ProviderType] = {
    "Automat1": ProviderType.AUTOMAT_1,
    "Automat 1": ProviderType.AUTOMAT_1,
    "Best": ProviderType.BEST,
    "Bunker Oil": ProviderType.BUNKER_OIL,
    "Circle K": ProviderType.CIRCLE_K,
    "Driv": ProviderType.DRIV,
    "Esso": ProviderType.ESSO,
    "Haltbakk Express": ProviderType.HALTBAKK_EXPRESS,
    "Oljeleverandøren": ProviderType.OLJELEVERANDØREN,
    "St1": ProviderType.ST1,
    "Tanken": ProviderType.TANKEN,
    "Trønder Oil": ProviderType.TRONDER_OIL,
    "Uno-X": ProviderType.UNO_X,
    "YX": ProviderType.YX,
    "YX Truck": ProviderType.YX_TRUCK,
}
