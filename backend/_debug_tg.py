import pymongo
db = pymongo.MongoClient("mongodb://localhost:27017")["ombra_dev"]

# Recent Telegram inbound
print("=== Recent Telegram Messages ===")
entries = list(db.activity_log.find({"type": "telegram_inbound"}).sort("timestamp", -1).limit(5))
for e in entries:
    d = e.get("details", {})
    print(f"  cmd={d.get('command')} | args={str(d.get('args',''))[:80]} | {e.get('timestamp')}")

# Check recent conversations from telegram
print("\n=== Recent Telegram Conversations ===")
convs = list(db.conversations.find({"session_id": {"$regex": "telegram_"}}).sort("updated_at", -1).limit(3))
for c in convs:
    print(f"  session={c.get('session_id')} | turns={len(c.get('turns',[]))}")
    for t in c.get("turns", [])[-4:]:
        role = t.get("role")
        content = str(t.get("content", ""))[:150]
        routing = t.get("routing", {})
        tc = t.get("tool_calls")
        tools_info = f" [tools: {len(tc)}]" if tc else ""
        route_info = f" [route: {routing.get('route', 'N/A')}]" if routing else ""
        print(f"    {role}: {content}{route_info}{tools_info}")
