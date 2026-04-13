import requests

r = requests.post(
    'http://localhost:8001/api/chat',
    json={'message': 'ping', 'session_id': 'diag_ping4', 'enable_tools': False},
    timeout=50,
)
print('status', r.status_code)
print(r.text[:500])
