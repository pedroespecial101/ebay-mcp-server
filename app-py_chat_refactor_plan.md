Session Prompt: Refactor LLM Chat Components in MCP Test UI

**Objective:**
The primary goal is to refactor the LLM chat functionality currently residing in `mcp_test_ui/app.py` into more modular components. This will improve code organization, reduce the size of `app.py`, and make the codebase easier to maintain and for AI agents to work with. The refactored application must retain all existing chat functionalities, including support for multiple LLM providers, streaming, and MCP tool calling.

**Current State:**
- `mcp_test_ui/app.py` is approximately 900 lines long, with the majority of its code dedicated to the LLM chat interface.
- The MCP Test UI parts (tool listing/execution) have already been successfully refactored into `routes_mcp.py`, `mcp_utils.py`, `models.py`, and `config.py`.
- The application uses FastAPI.
- The project path is `/Users/petetreadaway/Projects/ebay-mcp-server/`.
- The virtual environment is `.venv`.

**Refactoring Tasks:**

1.  **Create `mcp_test_ui/routes_chat.py`:**
    *   Move the FastAPI routes `/chat` (renders `chat.html`) and `/chat/stream` (handles streaming chat responses) from `app.py` to this new router.
    *   Ensure `Jinja2Templates` and any other necessary dependencies are correctly passed to or initialized within this router (similar to `init_router_dependencies` in `routes_mcp.py`).

2.  **Create `mcp_test_ui/llm_handlers/` directory:**
    *   Inside this directory, create separate Python files for each LLM provider's logic:
        *   `openai_handler.py`: Move `call_openai()` and `stream_openai()` functions.
        *   `anthropic_handler.py`: Move `call_anthropic()` and `stream_anthropic()` functions.
        *   `gemini_handler.py`: Move `call_gemini()` and `stream_gemini()` functions.
        *   `openrouter_handler.py`: Move `call_openrouter()` and `stream_openrouter()` functions.
    *   Ensure these handlers can be called from `routes_chat.py`.

3.  **Create/Update `mcp_test_ui/llm_utils.py` (or use existing `mcp_utils.py` if more appropriate):**
    *   Move shared LLM helper functions. A key candidate is `get_mcp_tools_for_openai()`.
    *   Consider if any common logic from the `call_*` or `stream_*` functions (e.g., API key handling, error formatting) can be centralized here.

4.  **Update `mcp_test_ui/models.py`:**
    *   Move LLM-specific Pydantic models from `app.py` to `models.py`. These include `Message`, `ChatRequest`, `ToolCall`, and `ToolResult`. (Alternatively, create a new `llm_models.py` if preferred for separation).

5.  **Modify `mcp_test_ui/app.py`:**
    *   Remove all the functions, routes, and Pydantic models that have been moved to the new modules.
    *   Add necessary imports for the new modules and routers.
    *   Include the new chat router (from `routes_chat.py`) in the main FastAPI `app` instance, potentially with a prefix like `/chat` (e.g., `app.include_router(chat_router, prefix="/chat", tags=["LLM Chat"])`).
    *   Ensure the `run_server()` function and the `if __name__ == "__main__":` block correctly initialize and run the application with the refactored structure.

**Testing Strategy (using Playwright MCP):**

*   **Prerequisite:** Ensure the refactored UI server can be started (e.g., on `http://127.0.0.1:8001`).
*   **Chat Page Load:**
    *   Navigate to the main chat page (e.g., `/mcp/chat` or `/chat` depending on the new router prefix).
    *   Verify essential UI elements: chat input field, send button, provider selection dropdown, API key input (if visible), MCP server path display.
*   **Basic Chat Functionality (test for each supported provider, especially OpenRouter):**
    *   Select a provider from the UI. (Use OpenRouter and Gemini 2.5 Fast for the tests)
    *   Enter a valid API key if required (or confirm `.env` loading works).
    *   Send a simple message (e.g., "Hello, who are you?").
    *   Verify that a response is received from the LLM and displayed in the chat interface.
    *   If streaming is enabled by default or selected, verify the response appears incrementally.
*   **MCP Tool Calling via LLM (test with a provider that supports it, e.g., OpenRouter or OpenAI):**
    *   Ensure the correct MCP server path is configured.
    *   Use a prompt designed to trigger an MCP tool, for example, "Use the test_auth tool to check eBay authentication."
    *   Verify the LLM's response indicates a tool call is being made.
    *   Monitor server logs (`mcp_test_ui` and `fastmcp_server.log`) to confirm the MCP tool (e.g., `test_auth`) is executed by `src/server.py`.
    *   Verify the tool's result is returned to the LLM.
    *   Verify the LLM processes the tool result and provides a final, coherent response in the chat UI.
*   **Error Handling:**
    *   Test with an invalid/missing API key for a selected provider.
    *   Test chat functionality when the MCP server path (for tool calls) is invalid or the server is not running.
    *   Verify that user-friendly error messages are displayed in the UI or appropriate error responses (e.g., 400, 500) are returned by the API.
*   **Log Verification:** Throughout testing, monitor browser console logs and server-side logs (`mcp_test_ui` FastAPI app logs and `fastmcp_server.log`) for any errors or unexpected behavior.

**Key Learnings & "Gotchas" from Previous Refactoring (for the AI Agent):**

*   **Python Executable Path:** When running Python scripts directly or as subprocesses (like `PythonStdioTransport` does), always use the absolute path to the Python executable within the project's virtual environment (e.g., `/Users/petetreadaway/Projects/ebay-mcp-server/.venv/bin/python`). Relying on `python` in the system PATH can lead to `command not found` errors or using the wrong interpreter.
*   **FastAPI Router Prefixes & Client-Side URLs:** If a FastAPI router is included with a `prefix` (e.g., `app.include_router(my_router, prefix="/module")`), all routes within `my_router` will be prepended with `/module`. Ensure any client-side JavaScript making AJAX calls uses the complete, correct URL (e.g., `/module/actual_route`).
*   **Pydantic v2+ Aliases:** For Pydantic models using field aliases (e.g., `field_name: str = Field(alias="json_alias")`), ensure that when instantiating the model, you use the alias as the keyword argument (e.g., `MyModel(json_alias="value")`) to avoid validation errors. This was critical for `MCPToolParameter`.
*   **`fastmcp.Client` Configuration:** The `fastmcp.Client` requires a `transport` argument. For running a local Python MCP server script, `PythonStdioTransport` is used, which itself needs `script_path` (path to `src/server.py`) and `python_cmd` (path to the venv Python executable).
*   **Playwright and Dynamic Content:** For UIs where content loads or appears dynamically (e.g., after an API call), use Playwright's `page.wait_for_selector()` or `page.evaluate()` with custom JavaScript polling logic to ensure elements are present and visible before attempting to interact with them or retrieve their content. This prevents race conditions and flakiness in tests.
*   **Server Restarts:** After making changes to backend Python code (FastAPI app, routers, utilities), the UI server must be restarted for changes to take effect. Use a command like `lsof -ti:<port> | xargs kill -9 2>/dev/null || true` before the start command to ensure the port is free. The FastMCP server (`src/server.py`) also needs restarting (`./start.sh restart`) if its code changes.
*   **`.env` File Parsing:** The `python-dotenv` library can be sensitive to the formatting of `.env` files. Ensure comments start at the beginning of a line and values are appropriately quoted if they contain special characters or spaces to avoid parsing warnings.
*   **Modular Imports & `sys.path`:** When moving code into subdirectories/modules, ensure Python's import system can find them. Prefer relative imports (e.g., `from .my_module import MyClass`) within a package. Avoid excessive `sys.path.append()` if possible.
*   **Configuration (`config.py`):** A centralized `config.py` for shared application settings (like `mcp_server_path`, API keys loaded from env, cached data) proved effective and should be utilized for chat-related configurations as well.
*   **Dependency Injection (e.g., Templates):** The pattern of using an initialization function (e.g., `init_router_dependencies(templates_obj)`) to pass shared objects like `Jinja2Templates` instances to routers is a clean way to manage dependencies.
*   **`CHANGELOG.md`:** Maintain the practice of prepending detailed, timestamped entries to `CHANGELOG.md` for each significant refactoring step, feature, or fix.
*   **README.md:** Finally Update the README to reflect the new structure and any changes in the refactoring process.
