"""
Ombra MCP Client
================
Model Context Protocol client implementation.
Connects to external MCP tool servers via stdio or HTTP/SSE transport,
discovers their tools dynamically, and exposes them to the agent loop.

MCP Spec: https://spec.modelcontextprotocol.io/
"""

import os
import json
import asyncio
import subprocess
import time
import uuid
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field

# ── Data Types ────────────────────────────────────────────────────────────────

@dataclass
class MCPTool:
    """A tool discovered from an MCP server."""
    name: str
    description: str
    input_schema: dict
    server_id: str

    def to_openai_format(self) -> dict:
        """Convert to OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": f"mcp_{self.server_id}_{self.name}",
                "description": f"[MCP:{self.server_id}] {self.description}",
                "parameters": self.input_schema,
            }
        }


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    server_id: str
    name: str
    transport: str = "stdio"    # "stdio" or "sse"
    command: str = ""           # For stdio: command to run
    args: list = field(default_factory=list)
    env: dict = field(default_factory=dict)
    url: str = ""               # For SSE: endpoint URL
    enabled: bool = True
    auto_start: bool = True


# ── Stdio Transport ──────────────────────────────────────────────────────────

class StdioTransport:
    """Communicate with an MCP server via stdin/stdout using JSON-RPC."""

    def __init__(self, command: str, args: list = None, env: dict = None):
        self.command = command
        self.args = args or []
        self.env = {**os.environ, **(env or {})}
        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the MCP server process."""
        self._process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
        )
        self._reader_task = asyncio.create_task(self._read_loop())

    async def stop(self):
        """Stop the MCP server process."""
        if self._reader_task:
            self._reader_task.cancel()
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()

    async def send_request(self, method: str, params: dict = None) -> dict:
        """Send a JSON-RPC request and wait for the response."""
        self._request_id += 1
        req_id = self._request_id

        message = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params:
            message["params"] = params

        data = json.dumps(message) + "\n"

        if not self._process or not self._process.stdin:
            raise RuntimeError("Transport not started")

        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()

        # Create a future for the response
        future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        try:
            result = await asyncio.wait_for(future, timeout=30)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise RuntimeError(f"MCP request timed out: {method}")

    async def send_notification(self, method: str, params: dict = None):
        """Send a JSON-RPC notification (no response expected)."""
        message = {"jsonrpc": "2.0", "method": method}
        if params:
            message["params"] = params
        data = json.dumps(message) + "\n"
        if self._process and self._process.stdin:
            self._process.stdin.write(data.encode())
            await self._process.stdin.drain()

    async def _read_loop(self):
        """Read responses from stdout."""
        try:
            while self._process and self._process.stdout:
                line = await self._process.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode().strip())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                req_id = msg.get("id")
                if req_id and req_id in self._pending:
                    future = self._pending.pop(req_id)
                    if "error" in msg:
                        future.set_exception(RuntimeError(
                            f"MCP error: {msg['error'].get('message', 'Unknown')}"
                        ))
                    else:
                        future.set_result(msg.get("result", {}))
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None


# ── SSE Transport ─────────────────────────────────────────────────────────────

class SSETransport:
    """Communicate with an MCP server via HTTP/SSE."""

    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self._session = None

    async def start(self):
        import httpx
        self._session = httpx.AsyncClient(timeout=30)

    async def stop(self):
        if self._session:
            await self._session.aclose()

    async def send_request(self, method: str, params: dict = None) -> dict:
        if not self._session:
            raise RuntimeError("Transport not started")

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
        }
        if params:
            payload["params"] = params

        resp = await self._session.post(f"{self.url}/message", json=payload)
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            raise RuntimeError(f"MCP error: {result['error'].get('message', 'Unknown')}")
        return result.get("result", {})

    async def send_notification(self, method: str, params: dict = None):
        if not self._session:
            return
        payload = {"jsonrpc": "2.0", "method": method}
        if params:
            payload["params"] = params
        await self._session.post(f"{self.url}/message", json=payload)

    @property
    def is_running(self) -> bool:
        return self._session is not None


# ── MCP Server Connection ────────────────────────────────────────────────────

class MCPServer:
    """Manages a single MCP server connection."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.tools: list[MCPTool] = []
        self._transport = None
        self._initialized = False

    async def connect(self):
        """Connect to the MCP server and initialize."""
        if self.config.transport == "stdio":
            self._transport = StdioTransport(
                self.config.command, self.config.args, self.config.env
            )
        elif self.config.transport == "sse":
            self._transport = SSETransport(self.config.url)
        else:
            raise ValueError(f"Unknown transport: {self.config.transport}")

        await self._transport.start()

        # Send initialize request
        init_result = await self._transport.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ombra", "version": "1.0.0"}
        })

        # Send initialized notification
        await self._transport.send_notification("notifications/initialized")
        self._initialized = True

        # Discover tools
        await self.refresh_tools()
        return init_result

    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self._transport:
            await self._transport.stop()
        self._initialized = False

    async def refresh_tools(self):
        """Fetch available tools from the server."""
        if not self._initialized:
            return
        result = await self._transport.send_request("tools/list")
        self.tools = []
        for tool_data in result.get("tools", []):
            self.tools.append(MCPTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {"type": "object", "properties": {}}),
                server_id=self.config.server_id,
            ))

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server."""
        if not self._initialized:
            return {"success": False, "output": "MCP server not connected"}

        try:
            result = await self._transport.send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments,
            })
            # Extract text content from MCP response
            content_parts = result.get("content", [])
            output = ""
            for part in content_parts:
                if part.get("type") == "text":
                    output += part.get("text", "")
                elif part.get("type") == "image":
                    output += f"[Image: {part.get('mimeType', 'image/png')}]"

            is_error = result.get("isError", False)
            return {
                "success": not is_error,
                "output": output or "(no output)",
                "raw": result,
            }
        except Exception as e:
            return {"success": False, "output": f"MCP tool call failed: {str(e)}"}

    @property
    def is_connected(self) -> bool:
        return self._initialized and self._transport and self._transport.is_running


# ── MCP Manager ───────────────────────────────────────────────────────────────

class MCPManager:
    """
    Central manager for all MCP server connections.
    Handles lifecycle, tool discovery, and routing tool calls to the right server.
    Persists configs to a JSON file so servers survive restarts.
    """

    PERSIST_FILE = os.path.join(os.path.dirname(__file__), ".mcp_servers.json")

    def __init__(self):
        self._servers: dict[str, MCPServer] = {}
        self._configs: dict[str, MCPServerConfig] = {}
        self._tool_map: dict[str, tuple[str, str]] = {}  # prefixed_name -> (server_id, original_name)

    async def add_server(self, config: MCPServerConfig) -> dict:
        """Add and connect to an MCP server."""
        self._configs[config.server_id] = config
        server = MCPServer(config)

        if config.enabled and config.auto_start:
            try:
                init_result = await server.connect()
                self._servers[config.server_id] = server
                self._rebuild_tool_map()
                self._save_configs()
                return {
                    "success": True,
                    "server_id": config.server_id,
                    "tools_discovered": len(server.tools),
                    "tool_names": [t.name for t in server.tools],
                }
            except Exception as e:
                return {
                    "success": False,
                    "server_id": config.server_id,
                    "error": str(e),
                }
        self._save_configs()
        return {"success": True, "server_id": config.server_id, "status": "registered (not started)"}

    async def remove_server(self, server_id: str):
        """Disconnect and remove an MCP server."""
        if server_id in self._servers:
            await self._servers[server_id].disconnect()
            del self._servers[server_id]
        self._configs.pop(server_id, None)
        self._rebuild_tool_map()
        self._save_configs()

    async def call_tool(self, prefixed_name: str, arguments: dict) -> dict:
        """
        Call an MCP tool by its prefixed name (mcp_<server_id>_<tool_name>).
        """
        if prefixed_name not in self._tool_map:
            return {"success": False, "output": f"Unknown MCP tool: {prefixed_name}"}

        server_id, tool_name = self._tool_map[prefixed_name]
        server = self._servers.get(server_id)
        if not server or not server.is_connected:
            return {"success": False, "output": f"MCP server '{server_id}' not connected"}

        return await server.call_tool(tool_name, arguments)

    def get_all_tool_definitions(self) -> list[dict]:
        """Get OpenAI-format tool definitions for all connected MCP tools."""
        definitions = []
        for server in self._servers.values():
            for tool in server.tools:
                definitions.append(tool.to_openai_format())
        return definitions

    def _rebuild_tool_map(self):
        """Rebuild the tool name -> (server, name) lookup."""
        self._tool_map.clear()
        for server_id, server in self._servers.items():
            for tool in server.tools:
                prefixed = f"mcp_{server_id}_{tool.name}"
                self._tool_map[prefixed] = (server_id, tool.name)

    def get_status(self) -> dict:
        """Get status of all registered MCP servers."""
        servers = []
        for sid, config in self._configs.items():
            server = self._servers.get(sid)
            servers.append({
                "server_id": sid,
                "name": config.name,
                "transport": config.transport,
                "enabled": config.enabled,
                "connected": server.is_connected if server else False,
                "tools": len(server.tools) if server else 0,
                "tool_names": [t.name for t in server.tools] if server else [],
            })
        return {
            "total_servers": len(self._configs),
            "connected": sum(1 for s in self._servers.values() if s.is_connected),
            "total_tools": len(self._tool_map),
            "servers": servers,
        }

    async def shutdown(self):
        """Disconnect all servers."""
        for server in self._servers.values():
            await server.disconnect()
        self._servers.clear()
        self._tool_map.clear()

    # ── Persistence ───────────────────────────────────────────────────────

    def _save_configs(self):
        """Save all server configs to disk."""
        data = []
        for sid, config in self._configs.items():
            data.append({
                "server_id": config.server_id,
                "name": config.name,
                "transport": config.transport,
                "command": config.command,
                "args": config.args,
                "env": config.env,
                "url": config.url,
                "enabled": config.enabled,
                "auto_start": config.auto_start,
            })
        try:
            with open(self.PERSIST_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_configs(self) -> list[dict]:
        """Load saved server configs from disk."""
        try:
            if os.path.exists(self.PERSIST_FILE):
                with open(self.PERSIST_FILE, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    async def restore_servers(self):
        """Restore and reconnect all previously saved MCP servers."""
        saved = self._load_configs()
        for entry in saved:
            sid = entry.get("server_id", "")
            if not sid or sid in self._configs:
                continue
            config = MCPServerConfig(
                server_id=sid,
                name=entry.get("name", sid),
                transport=entry.get("transport", "stdio"),
                command=entry.get("command", ""),
                args=entry.get("args", []),
                env=entry.get("env", {}),
                url=entry.get("url", ""),
                enabled=entry.get("enabled", True),
                auto_start=entry.get("auto_start", True),
            )
            try:
                await self.add_server(config)
            except Exception:
                # Store config even if connection fails so UI shows it
                self._configs[sid] = config

    def is_mcp_tool(self, name: str) -> bool:
        """Check if a tool name belongs to an MCP server."""
        return name.startswith("mcp_") and name in self._tool_map


# ── Global instance ───────────────────────────────────────────────────────────
mcp_manager = MCPManager()
