import urllib.request, json

key = open("/home/azureuser/Ombra/backend/.env").read()
for line in key.splitlines():
    if line.startswith("EMERGENT_LLM_KEY="):
        api_key = line.split("=", 1)[1].strip()
        break

req = urllib.request.Request(
    "https://api.openai.com/v1/chat/completions",
    data=json.dumps({
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "say hi in 3 words"}],
        "max_tokens": 10
    }).encode(),
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
)
try:
    r = urllib.request.urlopen(req, timeout=15)
    data = json.loads(r.read())
    print("OK:", data["choices"][0]["message"]["content"])
except urllib.error.HTTPError as e:
    print("HTTP ERROR:", e.code, json.loads(e.read()))
except Exception as e:
    print("ERROR:", e)
