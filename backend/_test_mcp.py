import urllib.request, json

data = json.dumps({
    "server_id": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp/ombra_workspace"]
}).encode()

req = urllib.request.Request(
    "http://localhost:8001/api/mcp/connect",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
)
resp = urllib.request.urlopen(req, timeout=30)
print(resp.read().decode())
