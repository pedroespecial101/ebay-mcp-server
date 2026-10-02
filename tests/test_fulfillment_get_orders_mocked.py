import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ebay_mcp.fulfillment.server import fulfillment_get_orders
from models.mcp_tools import GetOrdersParams

@pytest.fixture
def mock_httpx_client():
    client = MagicMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({"orders": [{"orderId": "123", "orderFulfillmentStatus": "NOT_STARTED"}]})
    mock_resp.raise_for_status = MagicMock()

    client.get = AsyncMock(return_value=mock_resp)
    return client

@pytest.mark.asyncio
@patch('ebay_mcp.fulfillment.server.execute_ebay_api_call')
async def test_fulfillment_get_orders_filter_construction(mock_execute, mock_httpx_client):
    """Test that the get_orders tool constructs the right filter query parameters."""

    # We will simulate the behavior of execute_ebay_api_call by extracting
    # the callback passed to it and awaiting it directly with our mock client.
    async def side_effect(tool_name, client, api_call_logic):
        return await api_call_logic("dummy_token", mock_httpx_client)

    mock_execute.side_effect = side_effect

    # No filter
    result_str = await fulfillment_get_orders(limit=10, offset=5)

    mock_httpx_client.get.assert_called_once()
    args, kwargs = mock_httpx_client.get.call_args
    assert kwargs['params']['limit'] == '10'
    assert kwargs['params']['offset'] == '5'
    assert 'filter' not in kwargs['params']
    assert 'orderIds' not in kwargs['params']

    mock_httpx_client.get.reset_mock()

    # Test 2: Status filter
    result_str = await fulfillment_get_orders(order_fulfillment_status="NOT_STARTED")

    mock_httpx_client.get.assert_called_once()
    args, kwargs = mock_httpx_client.get.call_args
    assert kwargs['params']['filter'] == "orderfulfillmentstatus:{NOT_STARTED}"

    mock_httpx_client.get.reset_mock()

    # Test 3: Date filters and IDs
    result_str = await fulfillment_get_orders(
        order_ids="123,456",
        creation_date_start="2023-01-01T00:00:00.000Z"
    )

    mock_httpx_client.get.assert_called_once()
    args, kwargs = mock_httpx_client.get.call_args
    assert kwargs['params']['orderIds'] == "123,456"
    assert "creationdate:[2023-01-01T00:00:00.000Z..]" in kwargs['params']['filter']


def test_get_orders_rejects_invalid_filters_before_request():
    with pytest.raises(ValueError, match="at most 50"):
        GetOrdersParams(order_ids=",".join(str(index) for index in range(51)))

    with pytest.raises(ValueError, match="ISO 8601"):
        GetOrdersParams(creation_date_start="not-a-date")

    with pytest.raises(ValueError, match="timezone"):
        GetOrdersParams(creation_date_start="2026-08-14")


@pytest.mark.asyncio
@patch("ebay_mcp.fulfillment.server.execute_ebay_api_call")
async def test_get_orders_rejects_invalid_status_without_call(mock_execute):
    result = await fulfillment_get_orders(order_fulfillment_status="SHIPPED")

    assert "Validation error" in result
    mock_execute.assert_not_called()
