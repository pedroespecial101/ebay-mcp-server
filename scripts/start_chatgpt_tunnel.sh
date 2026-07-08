#!/bin/bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

exec /opt/homebrew/bin/doppler run \
  --project ebay-mcp \
  --config dev_chatgpt \
  -- \
  /usr/local/bin/tunnel-client run --profile ebay-seller-chatgpt
