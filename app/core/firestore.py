"""Firestore client helpers."""

import firebase_admin.firestore  # type: ignore[import-untyped]

from app.core.auth import get_firebase_app


def fetch_all_stations_sync() -> list[dict[str, object]]:
    """Fetch all station documents from Firestore (sync — run via asyncio.to_thread)."""
    client = firebase_admin.firestore.client(app=get_firebase_app())
    docs = client.collection("stations").stream()
    return [doc.to_dict() for doc in docs]


def fetch_all_prices_sync() -> list[dict[str, object]]:
    """Fetch all price documents from Firestore (sync — run via asyncio.to_thread)."""
    client = firebase_admin.firestore.client(app=get_firebase_app())
    return [doc.to_dict() for doc in client.collection("currentPrices").stream()]
