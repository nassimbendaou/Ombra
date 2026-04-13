import requests

response = requests.post(
    'http://localhost:8001/api/chat',
    json={
        'message': 'Use tools to list the files in the backend folder and tell me the first five names only.',
        'session_id': 'tool_test_session',
        'enable_tools': True,
    },
    timeout=60,
)
print('STATUS', response.status_code)
print(response.text[:4000])
