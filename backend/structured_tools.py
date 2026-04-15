"""
Ombra Structured Tool Calling
=============================
JSON-Schema validated tool dispatch with type checking.
Wraps all tool definitions with full schema validation before execution.
"""

import json
import jsonschema
from typing import Any


class ToolValidationError(Exception):
    """Raised when tool arguments fail schema validation."""
    def __init__(self, tool_name: str, errors: list[str]):
        self.tool_name = tool_name
        self.errors = errors
        super().__init__(f"Validation failed for tool '{tool_name}': {'; '.join(errors)}")


class StructuredToolRegistry:
    """
    Central registry for tools with JSON Schema validation.
    Tools are registered with their schema and handler, then dispatched
    through a single validated entry point.
    """

    def __init__(self):
        self._tools: dict[str, dict] = {}
        self._handlers: dict[str, Any] = {}
        self._schemas: dict[str, dict] = {}  # compiled schemas for fast validation

    def register(self, name: str, description: str, parameters_schema: dict,
                 handler, *, is_async: bool = False, category: str = "general",
                 requires_permission: str | None = None):
        """Register a tool with its JSON schema and handler function."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters_schema,
            "is_async": is_async,
            "category": category,
            "requires_permission": requires_permission,
        }
        self._handlers[name] = handler
        self._schemas[name] = parameters_schema

    def unregister(self, name: str):
        """Remove a tool from the registry."""
        self._tools.pop(name, None)
        self._handlers.pop(name, None)
        self._schemas.pop(name, None)

    def list_tools(self, category: str | None = None) -> list[dict]:
        """List all registered tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t["category"] == category]
        return tools

    def get_openai_definitions(self, tool_names: list[str] | None = None) -> list[dict]:
        """
        Export tool definitions in OpenAI function-calling format.
        If tool_names is provided, only export those tools.
        """
        definitions = []
        for name, tool in self._tools.items():
            if tool_names and name not in tool_names:
                continue
            definitions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                }
            })
        return definitions

    def validate_args(self, name: str, args: dict) -> list[str]:
        """
        Validate tool arguments against the registered JSON schema.
        Returns list of validation error messages (empty = valid).
        """
        if name not in self._schemas:
            return [f"Unknown tool: {name}"]
        schema = self._schemas[name]
        errors = []
        try:
            jsonschema.validate(instance=args, schema=schema)
        except jsonschema.ValidationError as e:
            errors.append(f"{e.json_path}: {e.message}")
        except jsonschema.SchemaError as e:
            errors.append(f"Schema error: {e.message}")
        return errors

    async def execute(self, name: str, args: dict, *, db=None,
                      skip_validation: bool = False) -> dict:
        """
        Validate args and execute a tool. Returns result dict.
        """
        if name not in self._handlers:
            return {"success": False, "output": f"Unknown tool: {name}"}

        if not skip_validation:
            errors = self.validate_args(name, args)
            if errors:
                return {
                    "success": False,
                    "output": f"Argument validation failed: {'; '.join(errors)}",
                    "validation_errors": errors
                }

        handler = self._handlers[name]
        tool_info = self._tools[name]

        try:
            if tool_info["is_async"]:
                result = await handler(**args) if not db else await handler(db=db, **args)
            else:
                result = handler(**args) if not db else handler(db=db, **args)
        except Exception as e:
            result = {"success": False, "output": f"Tool execution error: {str(e)}"}

        # Ensure result is always a dict with success and output
        if not isinstance(result, dict):
            result = {"success": True, "output": str(result)}
        if "success" not in result:
            result["success"] = True
        if "output" not in result:
            result["output"] = ""

        return result

    def get_tool_info(self, name: str) -> dict | None:
        """Get full info about a registered tool."""
        return self._tools.get(name)

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())


# ── Global registry instance ──────────────────────────────────────────────────
tool_registry = StructuredToolRegistry()


def register_existing_tools(tool_definitions: list[dict], execute_tool_func):
    """
    Bridge: import existing TOOL_DEFINITIONS and execute_tool into the registry.
    Called once at startup to migrate the legacy tool list.
    """
    import asyncio
    import inspect

    for td in tool_definitions:
        func = td.get("function", {})
        name = func.get("name", "")
        if not name:
            continue

        desc = func.get("description", "")
        params = func.get("parameters", {"type": "object", "properties": {}})

        # Create a wrapper that calls the legacy execute_tool dispatcher
        async def _make_handler(tool_name):
            async def _handler(db=None, **kwargs):
                return await execute_tool_func(tool_name, kwargs, db)
            return _handler

        handler = asyncio.get_event_loop().run_until_complete(_make_handler(name)) \
            if asyncio.get_event_loop().is_running() else None

        # Direct lambda-based registration (sync-safe)
        tool_registry.register(
            name=name,
            description=desc,
            parameters_schema=params,
            handler=execute_tool_func,  # Will be called as execute_tool(name, args, db)
            is_async=True,
            category=_categorize_tool(name),
        )


def _categorize_tool(name: str) -> str:
    """Auto-categorize a tool by name."""
    categories = {
        "terminal": "system", "read_file": "filesystem", "write_file": "filesystem",
        "list_dir": "filesystem", "python_exec": "code", "git_run": "code",
        "web_search": "web", "fetch_url": "web", "browser_research": "web",
        "http_request": "web", "memory_store": "data", "create_task": "data",
        "draft_email": "communication", "read_emails": "communication",
        "install_packages": "system", "generate_video": "media",
        "screenshot": "media",
    }
    return categories.get(name, "general")
