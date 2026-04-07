import json
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_logged_in_user
from app.core.config import get_settings
from app.core.schemas import CamelCaseModel
from app.users.models import User

tools_router = APIRouter(prefix="/tools", tags=["tools"])

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 256
_SYSTEM_PROMPT = """
You are a fuel price sign reader for Norwegian fuel stations.
Extract fuel prices from this image of a price sign.

Output ONLY valid JSON in this exact format, nothing else:
{"diesel":null,"gasoline_95":null,"gasoline_98":null}

Rules:
- Replace null with the price as a number if visible (e.g. 20.47)
- Prices are in NOK per litre, typically between 10.00 and 35.00
- Use decimal point, not comma
- "D" or "Diesel" = diesel
- "95" = gasoline_95 (unleaded 95)
- "98" = gasoline_98 (unleaded 98)
- If a fuel type is not visible or unreadable, keep it as null
- Output ONLY the raw JSON object, no markdown, no explanation
""".strip()

_client = httpx.AsyncClient(timeout=30.0)


class PostExtractPricesRequestBody(CamelCaseModel):
    image_base64: str


class ParsedFuelPrices(CamelCaseModel):
    diesel: float | None = None
    gasoline_95: float | None = None
    gasoline_98: float | None = None


@tools_router.post("/extract-prices", response_model=ParsedFuelPrices)
async def extract_prices(
    body: PostExtractPricesRequestBody,
    _: Annotated[User, Depends(get_logged_in_user)],
) -> ParsedFuelPrices:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    payload = {
        "model": _MODEL,
        "max_tokens": _MAX_TOKENS,
        "system": _SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": body.image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Read the fuel prices from this Norwegian fuel station price sign.",  # noqa: E501
                    },
                ],
            }
        ],
    }

    try:
        response = await _client.post(
            _ANTHROPIC_URL,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            json=payload,
        )
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY) from e

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Anthropic API error: {response.status_code}",
        )

    data = response.json()

    if data.get("stop_reason") != "end_turn":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unexpected stop reason: {data.get('stop_reason')}",
        )

    text_block = next(
        (b for b in data.get("content", []) if b.get("type") == "text"), None
    )
    if text_block is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY)

    raw_text = text_block["text"].strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        return ParsedFuelPrices.model_validate(json.loads(raw_text))
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to parse prices",
        ) from e
