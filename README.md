# eBay MCP Server

This project is a demonstration of an MCP server using FastMCP.

## Installation

To install the dependencies, run:

```bash
uv sync
```

## Usage

To start the server, run:

```bash
uv run fastmcp run src/server.py
```

## Install
In Claude Desktop, run:
```bash
uv run fastmcp install src/server.py -e EBAY_APP_ID=<YOUR_EBAY_APP_ID> -e EBAY_CLIENT_ID=<YOUR_EBAY_CLIENT_ID>
```

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
