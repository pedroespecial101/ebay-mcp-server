## AI Agent Autonomous Testing Procedure

This section provides guidance for AI agents on how to autonomously test and debug the eBay MCP Server, based on the successful approach used in this project.

### Testing MCP Tools

1. **Server Setup**:
   - Start the MCP server using `./start.sh restart`
   - Start the MCP Test UI with `python mcp_test_ui_start.py`
   - Create a browser preview for the UI at `http://127.0.0.1:8000`

2. **Direct API Testing**:
   - Use curl commands to test MCP tools directly via the API endpoint:
     ```bash
     curl -X POST -H "Content-Type: application/x-www-form-urlencoded" -d "param1=value1&param2=value2" http://127.0.0.1:8000/execute/tool_name
     ```
   - This allows testing with exact parameter values and seeing raw responses

3. **Browser UI Testing**:
   - Use the browser preview to interact with the MCP Test UI
   - Fill out the form for the tool you want to test and submit
   - Inspect the response and any error messages

4. **Debugging Process**:
   - If a tool fails with a validation error, inspect the error message for specific details
   - Check the parameter types expected by the tool's Pydantic model
   - Look for type conversion issues in the MCP Test UI's `app.py` file
   - Add or modify field validators in the Pydantic models to handle problematic inputs
   - Restart both servers and test again

5. **Iterative Improvement**:
   - Start with a working test case and progressively introduce more complex parameters
   - Document all errors and their solutions in the CHANGELOG.md
   - After each fix, test all previously problematic tools to ensure they still work

### Logging and Error Inspection

- Monitor server logs: `tail -f logs/fastmcp_server.log`
- Check MCP Test UI console output for client-side errors
- Add debug logging statements in the code to track parameter values and types

### Validation and Verification

When validating fixes, verify:

1. The tool accepts all valid parameter types (strings, integers, etc.)
2. The tool correctly handles edge cases (empty strings, zeros, etc.)
3. The fix doesn't break other tools or functionality
4. The solution is robust against future changes

This autonomous testing approach enables AI agents to effectively identify, debug, and fix issues in the MCP server without requiring constant human intervention.
