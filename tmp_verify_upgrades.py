import requests

base = 'http://localhost:8001'

# 1) command path quick check
r1 = requests.post(base + '/api/chat', json={'message': '/sessions', 'session_id': 'verify_upgrades_cmd', 'enable_tools': False}, timeout=30)
print('cmd_status', r1.status_code)

# 2) tool path check
r2 = requests.post(base + '/api/chat', json={'message': 'Use tools to list backend files and answer in one sentence', 'session_id': 'verify_upgrades_tool', 'enable_tools': True}, timeout=90)
print('tool_status', r2.status_code)
if r2.status_code == 200:
    data = r2.json()
    print('tool_route', data.get('routing', {}).get('route'))
    print('tool_calls_len', len(data.get('tool_calls') or []))
    if data.get('tool_calls'):
        tc = data['tool_calls'][0]
        print('first_tool', tc.get('tool'))
        print('first_success', tc.get('success'))

# 3) autonomy status contains new observability counters
r3 = requests.get(base + '/api/autonomy/status', timeout=20)
print('autonomy_status', r3.status_code)
if r3.status_code == 200:
    stats = r3.json().get('stats', {})
    keys = ['plan_runs', 'verify_failures', 'retry_attempts', 'retry_exhausted', 'loop_guard_skips']
    print('new_stats_present', all(k in stats for k in keys), {k: stats.get(k) for k in keys})
