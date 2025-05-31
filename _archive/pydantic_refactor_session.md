# Prompt for New Agent: Implement Pydantic Throughout eBay MCP Server Project

Your task is to refactor the eBay MCP Server project to use Pydantic for data validation, type safety, and improved API interaction. Here's what we've found in the current codebase:

## Current State Analysis

1. **Project Structure**:
   - Main MCP server code is in `/src` directory
   - MCP Test UI is in `/mcp_test_ui` directory
   - eBay API documentation in JSON format is available in `/ebay_docs`

2. **Pydantic Usage**:
   - The main MCP server code does NOT currently use Pydantic
   - The MCP Test UI does use Pydantic (v2.0.0+)
   - MCP Test UI imports Pydantic with: `from pydantic import BaseModel, create_model`

3. **Dependencies**:
   - Main project requirements: FastMCP, HTTPX, requests, python-dotenv
   - MCP Test UI uses: FastAPI, Uvicorn, Jinja2, FastMCP, Pydantic

4. **Available Resources**:
   - eBay API documentation JSON files in `/ebay_docs` folder that can be used to model the API schemas
   - MCP Test UI can serve as an example of Pydantic integration with FastAPI

## Implementation Goals

1. Integrate Pydantic throughout the entire project for:
   - API request/response validation
   - MCP tool parameter validation
   - Data structure definitions for eBay API responses
   - Configuration management

2. Improve type safety and documentation by:
   - Creating explicit models for all data structures
   - Providing proper type annotations for functions
   - Documenting expected data formats with Pydantic models

3. Enhance the developer experience by:
   - Adding self-validating models
   - Reducing manual validation code
   - Improving IDE autocompletion and hints

## Specific Tasks

1. **Project Setup**:
   - Add Pydantic to the main project's requirements.txt
   - Create appropriate model structures and file organization

2. **Core Model Development**:
   - Create Pydantic models for eBay API requests/responses using the JSON docs in `/ebay_docs`
   - Develop models for MCP tool parameters and returns
   - Implement validation for configuration settings

3. **Integration**:
   - Refactor existing code to use Pydantic models
   - Update API endpoints to leverage model validation
   - Ensure compatibility with FastMCP client interfaces

4. **Testing and Documentation**:
   - Update test cases to use Pydantic models
   - Document the model structure and validation rules
   - Provide examples of model usage

## Implementation Notes

- Prefer an incremental approach to avoid breaking existing functionality
- Maintain backward compatibility where possible
- Focus on areas where validation would provide the most benefit first
- Keep models in dedicated files for better organization
- Update the CHANGELOG.md with your changes
- Remember that `.venv` is used for virtual environments, not `venv`
- Use Pydantic v2 features where appropriate

## Testing Approach Used in Previous Session

In the previous session, we successfully fixed the MCP Test UI by implementing a proactive testing approach:

1. **Server Management**: 
   - Implemented port handling with commands like `lsof -ti:8000 | xargs kill -9` to ensure clean server restarts
   - Used background processes to start the server while continuing to make code changes

2. **Direct API Testing**: 
   - Used curl commands to test endpoints directly instead of only relying on browser UI testing
   - Example: `curl -X POST -H "Content-Type: application/x-www-form-urlencoded" -d "a=5&b=7" http://127.0.0.1:8000/execute/add`
   - Tested simple tools (add) and complex ones (get_category_suggestions) to verify parameter handling

3. **Progressive Debugging**:
   - Analyzed error messages directly from API responses
   - Made incremental fixes based on observed issues (parameter format, JSON serialization)
   - Added extensive logging to understand how FastMCP Client was processing requests

4. **End-to-End Verification**:
   - Confirmed fixes by testing through both direct API calls and browser interface
   - Verified that parameter extraction, conversion, and passing were all working correctly

This testing approach allowed for rapid debugging and fixing without needing to constantly revert back to the user for verification. It's recommended to follow a similar approach when implementing Pydantic throughout the project.

The `/ebay_docs` folder contains JSON descriptor files for the eBay APIs which can be used to automatically generate Pydantic models for requests and responses. Feel free to use tools or write scripts to parse these files and generate the models, as this will save time and reduce errors.

Your implementation should make the codebase more robust, self-documenting, and maintainable while leveraging Pydantic's powerful validation capabilities.