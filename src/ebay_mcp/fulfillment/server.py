import logging
import httpx

from fastmcp import FastMCP
from models.mcp_tools import GetOrdersParams
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers

logger = logging.getLogger(__name__)

fulfillment_mcp = FastMCP(
    name="eBay Fulfillment API",
    instructions="Provides operations for eBay Fulfillment such as fetching orders."
)

@fulfillment_mcp.tool()
async def fulfillment_get_orders(
    order_ids: str | None = None,
    creation_date_start: str | None = None,
    creation_date_end: str | None = None,
    last_modified_date_start: str | None = None,
    last_modified_date_end: str | None = None,
    order_fulfillment_status: str | None = None,
    limit: int = 50,
    offset: int = 0
) -> str:
    """
    Read eBay orders by order IDs, creation dates, last-modified dates, or fulfillment status.

    This tool is read-only. Order responses can contain buyer and delivery data,
    so use it only in trusted seller MCP clients.
    """
    try:
        params = GetOrdersParams(
            order_ids=order_ids,
            creation_date_start=creation_date_start,
            creation_date_end=creation_date_end,
            last_modified_date_start=last_modified_date_start,
            last_modified_date_end=last_modified_date_end,
            order_fulfillment_status=order_fulfillment_status,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Parameter validation error: {e}")
        return f"Validation error: {e}"

    logger.info(f"Executing fulfillment_get_orders with limit={params.limit}, offset={params.offset}")

    async def _api_call(access_token: str, client: httpx.AsyncClient) -> str:
        headers = get_standard_ebay_headers(access_token)
        url = "https://api.ebay.com/sell/fulfillment/v1/order"

        query_params = {
            "limit": str(params.limit),
            "offset": str(params.offset),
        }

        if params.order_ids:
            query_params["orderIds"] = params.order_ids

        # Build filter parameter
        filter_criteria = []
        if params.creation_date_start or params.creation_date_end:
            start = params.creation_date_start or "1970-01-01T00:00:00.000Z"
            end = params.creation_date_end or ""
            filter_criteria.append(f"creationdate:[{start}..{end}]")

        if params.last_modified_date_start or params.last_modified_date_end:
            start = params.last_modified_date_start or "1970-01-01T00:00:00.000Z"
            end = params.last_modified_date_end or ""
            filter_criteria.append(f"lastmodifieddate:[{start}..{end}]")

        if params.order_fulfillment_status:
            filter_criteria.append(f"orderfulfillmentstatus:{{{params.order_fulfillment_status}}}")

        if filter_criteria:
            query_params["filter"] = ",".join(filter_criteria)

        response = await client.get(url, headers=headers, params=query_params)
        response.raise_for_status()

        return response.text

    async with httpx.AsyncClient() as client:
        result_str = await execute_ebay_api_call("fulfillment_get_orders", client, _api_call)
        return result_str
