I need you to help me create a lightweight LLM chat interface for testing MCP servers. This will be integrated into my existing mcp_test_ui application as a new tab.
The usecase is for testing MCP servers and tools in a lightweight way, without the need for an external AI assistant.

Current Tech Stack:

    FastMCP

    FastAPI (Python)

    Jinja2 templates

    Existing mcp_test_ui with Swagger-type interface

Requirements:
Create a new tab/page in my existing FastAPI application with the following features:

    LLM Provider Selection: Dropdown to choose between OpenAI, Anthropic Claude, Gemini and potentially other providers (API creds in ./.env)

    Chat Interface:

        ChatGPT-style chat window with message history

        Input field for user messages

        Display of both user and assistant messages

        Real-time streaming of responses if possible

    MCP Integration:

        Connect to my local MCP servers

        Show when MCP tools are being called

        Display MCP tool results in a collapsible/expandable section

        Log MCP interactions for debugging

    Configuration:

        API key input fields for different LLM providers

        MCP server connection settings

        Model selection for each provider

Technical Implementation:

    Use FastAPI for the backend routes

    Jinja2 templates for the frontend

    WebSocket or SSE for real-time chat updates

    JavaScript for the chat interface interactions

    Integrate with FastMCP client to connect to my MCP servers

    Store chat history in memory (no database needed for now)

File Structure:
Please organize this as:

    New FastAPI routes in my existing app

    New Jinja2 template for the chat interface

    Static files (CSS/JS) for the chat functionality

    Integration points with my existing mcp_test_ui navigation

UI Design:

    Clean, modern chat interface similar to ChatGPT

    Separate sections for MCP tool calls and results

    Debug panel showing MCP server communications

    Responsive design that works well in a browser tab

Please produce the complete code including FastAPI routes, Jinja2 templates, JavaScript for the chat functionality, and CSS for styling. Make it production-ready but focused on development/testing use cases.