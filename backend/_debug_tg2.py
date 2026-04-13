import pymongo
db = pymongo.MongoClient("mongodb://localhost:27017")["ombra_dev"]

# Check: does an email provider exist?
print("=== Email Provider Config ===")
settings = db.settings.find_one({"user_id": "default"}) or {}
for k, v in settings.items():
    if "email" in str(k).lower():
        print(f"  {k}: {repr(str(v)[:80])}")

# Check last conversation turns fully
print("\n=== Last Telegram Conversation Full Detail ===")
conv = db.conversations.find_one({"session_id": {"$regex": "telegram_"}}, sort=[("updated_at", -1)])
if conv:
    for i, t in enumerate(conv.get("turns", [])):
        role = t.get("role")
        content = str(t.get("content", ""))[:300]
        routing = t.get("routing", {})
        tc = t.get("tool_calls")
        print(f"\n  [{i}] {role} | route={routing.get('route', '-')} | tools={len(tc) if tc else 0}")
        print(f"      {content}")
        if tc:
            for call in tc[:3]:
                print(f"      TOOL: {call.get('tool')} -> success={call.get('success')}")
