import json
from typing import Any, Dict, List, Union

from pydantic import BaseModel



class MCPToolParameter(BaseModel):
    """Represents a parameter for an MCP tool."""

    name: str
    type: str # Renamed from 'type_' to avoid Pydantic v2 field name conflict if 'type' was used directly.
    description: str = ""
    required: bool = True
    default: Any = None

    # Pydantic handles initialization automatically when inheriting from BaseModel.
    # The __init__ method is no longer needed unless custom initialization logic is required beyond field assignments.
        
    def get_html_input_type(self) -> str:
        """Get the HTML input type for this parameter type."""
        if self.type in ["string", "str"]:
            return "text"
        elif self.type in ["integer", "int"]:
            return "number"
        elif self.type in ["number", "float"]:
            return "number" 
        elif self.type in ["boolean", "bool"]:
            return "checkbox"
        elif self.type in ["array", "list"]:
            return "textarea" # Or handle more specifically if needed
        elif self.type in ["object", "dict"]:
            return "textarea" # Or handle more specifically if needed
        return "text"
    
    def parse_value(self, value: str) -> Any:
        """Parse a string value to the appropriate type."""
        if not value and not self.required:
            return self.default
        
        if self.type in ["string", "str"]:
            return value
        elif self.type in ["integer", "int"]:
            return int(value) if value else None
        elif self.type in ["number", "float"]:
            return float(value) if value else None
        elif self.type in ["boolean", "bool"]:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ["true", "1", "yes", "y", "on"]
            return bool(value)
        elif self.type in ["array", "list"]:
            try:
                if not value:
                    return []
                if value.startswith("[") and value.endswith("]"):
                    return json.loads(value)
                return [item.strip() for item in value.split(",")]
            except:
                # Consider logging a warning here
                return []
        elif self.type in ["object", "dict"]:
            try:
                return json.loads(value) if value else {}
            except:
                # Consider logging a warning here
                return {}
        return value


class MCPTool(BaseModel):
    """Represents an MCP tool with its parameters and metadata."""
    name: str
    description: str
    parameters: List[MCPToolParameter]


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        # Handle TextContent or other custom types
        if hasattr(obj, '__str__'):
            return str(obj)
        return super().default(obj)

