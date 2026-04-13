import requests

r = requests.post(
    'http://localhost:8001/api/chat',
    json={'message': 'use tools to list backend folder and return first 3 files', 'session_id': 'diag_tools4', 'enable_tools': True},
    timeout=70,
)
print('status', r.status_code)
print(r.text[:1000])
