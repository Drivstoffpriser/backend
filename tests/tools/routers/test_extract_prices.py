import json
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import RequestError, TimeoutException

import app.tools.routers as routers
from app.users.models import User
from tests.conftest import AuthenticatedClient

_REQUEST_BODY = {"imageBase64": "abc123"}


def _anthropic_response(
    prices: dict[str, float | None], stop_reason: str = "end_turn"
) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "stop_reason": stop_reason,
        "content": [{"type": "text", "text": json.dumps(prices)}],
    }
    return mock


@pytest.fixture
def mock_anthropic() -> Generator[MagicMock]:
    mock_settings = MagicMock()
    mock_settings.anthropic_api_key = "test-key"
    with (
        patch.object(routers, "_client") as mock_client,
        patch.object(routers, "get_settings", return_value=mock_settings),
    ):
        mock_client.post = AsyncMock()
        yield mock_client


async def test_extract_prices_returns_parsed_prices(
    client: AuthenticatedClient, unverified_user: User, mock_anthropic: MagicMock
) -> None:
    mock_anthropic.post.return_value = _anthropic_response(
        {"diesel": 20.47, "gasoline_95": 21.99, "gasoline_98": 23.10}
    )

    response = await client.post(
        "/tools/extract-prices", json=_REQUEST_BODY, authenticate_with=unverified_user
    )

    assert response.status_code == 200
    assert response.json() == {
        "diesel": 20.47,
        "gasoline95": 21.99,
        "gasoline98": 23.10,
    }


async def test_extract_prices_returns_partial_prices(
    client: AuthenticatedClient, unverified_user: User, mock_anthropic: MagicMock
) -> None:
    mock_anthropic.post.return_value = _anthropic_response(
        {"diesel": None, "gasoline_95": 21.99, "gasoline_98": None}
    )

    response = await client.post(
        "/tools/extract-prices", json=_REQUEST_BODY, authenticate_with=unverified_user
    )

    assert response.status_code == 200
    assert response.json() == {"diesel": None, "gasoline95": 21.99, "gasoline98": None}


async def test_extract_prices_requires_auth(client: AuthenticatedClient) -> None:
    response = await client.post("/tools/extract-prices", json=_REQUEST_BODY)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


async def test_extract_prices_403_for_guest_user(
    client: AuthenticatedClient, guest_user: User
) -> None:
    response = await client.post(
        "/tools/extract-prices", json=_REQUEST_BODY, authenticate_with=guest_user
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Email required"}


async def test_extract_prices_503_when_no_api_key(
    client: AuthenticatedClient, unverified_user: User
) -> None:
    with patch.object(routers, "get_settings") as mock_settings:
        mock_settings.return_value.anthropic_api_key = ""
        response = await client.post(
            "/tools/extract-prices",
            json=_REQUEST_BODY,
            authenticate_with=unverified_user,
        )

    assert response.status_code == 503


async def test_extract_prices_502_on_anthropic_error(
    client: AuthenticatedClient, unverified_user: User, mock_anthropic: MagicMock
) -> None:
    error_response = MagicMock()
    error_response.status_code = 500
    mock_anthropic.post.return_value = error_response

    response = await client.post(
        "/tools/extract-prices", json=_REQUEST_BODY, authenticate_with=unverified_user
    )

    assert response.status_code == 502


async def test_extract_prices_504_on_timeout(
    client: AuthenticatedClient, unverified_user: User, mock_anthropic: MagicMock
) -> None:
    mock_anthropic.post.side_effect = TimeoutException("timed out")

    response = await client.post(
        "/tools/extract-prices", json=_REQUEST_BODY, authenticate_with=unverified_user
    )

    assert response.status_code == 504


async def test_extract_prices_502_on_request_error(
    client: AuthenticatedClient, unverified_user: User, mock_anthropic: MagicMock
) -> None:
    mock_anthropic.post.side_effect = RequestError("connection failed")

    response = await client.post(
        "/tools/extract-prices", json=_REQUEST_BODY, authenticate_with=unverified_user
    )

    assert response.status_code == 502


async def test_extract_prices_502_on_max_tokens(
    client: AuthenticatedClient, unverified_user: User, mock_anthropic: MagicMock
) -> None:
    mock_anthropic.post.return_value = _anthropic_response(
        {"diesel": 20.47}, stop_reason="max_tokens"
    )

    response = await client.post(
        "/tools/extract-prices", json=_REQUEST_BODY, authenticate_with=unverified_user
    )

    assert response.status_code == 502


async def test_extract_prices_502_on_no_text_block(
    client: AuthenticatedClient, unverified_user: User, mock_anthropic: MagicMock
) -> None:
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"stop_reason": "end_turn", "content": []}
    mock_anthropic.post.return_value = mock

    response = await client.post(
        "/tools/extract-prices", json=_REQUEST_BODY, authenticate_with=unverified_user
    )

    assert response.status_code == 502


async def test_extract_prices_502_on_malformed_json(
    client: AuthenticatedClient, unverified_user: User, mock_anthropic: MagicMock
) -> None:
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "not valid json"}],
    }
    mock_anthropic.post.return_value = mock

    response = await client.post(
        "/tools/extract-prices", json=_REQUEST_BODY, authenticate_with=unverified_user
    )

    assert response.status_code == 502
