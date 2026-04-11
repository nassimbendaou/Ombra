import requests
import sys
import json
import time
from datetime import datetime

class OmbraAPITester:
    def __init__(self, base_url="https://ombra-core.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.session_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/api{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response preview: {str(response_data)[:200]}...")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error text: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health(self):
        """Test health endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "/health",
            200
        )
        if success:
            print(f"   Ollama available: {response.get('ollama', {}).get('available', False)}")
            print(f"   API key configured: {response.get('api_key_configured', False)}")
            print(f"   MongoDB connected: {response.get('mongodb', {}).get('connected', False)}")
        return success

    def test_dashboard_summary(self):
        """Test dashboard summary endpoint"""
        success, response = self.run_test(
            "Dashboard Summary",
            "GET",
            "/dashboard/summary",
            200
        )
        if success:
            print(f"   Total interactions: {response.get('total_interactions', 0)}")
            print(f"   Tool executions: {response.get('tool_executions', 0)}")
        return success

    def test_dashboard_status(self):
        """Test dashboard status endpoint"""
        success, response = self.run_test(
            "Dashboard Status",
            "GET",
            "/dashboard/status",
            200
        )
        if success:
            print(f"   Ollama status: {response.get('ollama', {}).get('status', 'unknown')}")
            print(f"   Cloud API status: {response.get('cloud_api', {}).get('status', 'unknown')}")
            print(f"   Memory status: {response.get('memory', {}).get('status', 'unknown')}")
        return success

    def test_permissions_get(self):
        """Test get permissions endpoint"""
        success, response = self.run_test(
            "Get Permissions",
            "GET",
            "/permissions",
            200
        )
        if success:
            print(f"   Terminal: {response.get('terminal', False)}")
            print(f"   Filesystem: {response.get('filesystem', False)}")
            print(f"   Telegram: {response.get('telegram', False)}")
            print(f"   Onboarded: {response.get('onboarded', False)}")
        return success, response

    def test_permissions_update(self):
        """Test update permissions endpoint"""
        success, response = self.run_test(
            "Update Permissions",
            "PUT",
            "/permissions",
            200,
            data={"terminal": True, "filesystem": False, "telegram": True}
        )
        return success

    def test_onboarding(self):
        """Test onboarding completion"""
        success, response = self.run_test(
            "Complete Onboarding",
            "POST",
            "/onboarding",
            200,
            data={"terminal": True, "filesystem": True, "telegram": False}
        )
        return success

    def test_activity_get(self):
        """Test get activity endpoint"""
        success, response = self.run_test(
            "Get Activity",
            "GET",
            "/activity",
            200
        )
        if success:
            activities = response.get('activities', [])
            print(f"   Total activities: {response.get('total', 0)}")
            print(f"   Returned activities: {len(activities)}")
        return success

    def test_activity_summary(self):
        """Test activity summary endpoint"""
        success, response = self.run_test(
            "Activity Summary",
            "GET",
            "/activity/summary",
            200
        )
        return success

    def test_settings_get(self):
        """Test get settings endpoint"""
        success, response = self.run_test(
            "Get Settings",
            "GET",
            "/settings",
            200
        )
        if success:
            print(f"   Ollama URL: {response.get('ollama_url', 'not set')}")
            print(f"   Learning enabled: {response.get('learning_enabled', False)}")
        return success

    def test_settings_update(self):
        """Test update settings endpoint"""
        success, response = self.run_test(
            "Update Settings",
            "PUT",
            "/settings",
            200,
            data={"learning_enabled": True, "white_card_enabled": False}
        )
        return success

    def test_chat_simple(self):
        """Test simple chat message (should route to Ollama)"""
        success, response = self.run_test(
            "Chat - Simple Message",
            "POST",
            "/chat",
            200,
            data={"message": "Hello", "white_card_mode": False},
            timeout=60  # Ollama can be slow
        )
        if success:
            self.session_id = response.get('session_id')
            print(f"   Session ID: {self.session_id}")
            print(f"   Provider used: {response.get('provider', 'unknown')}")
            print(f"   Model used: {response.get('model', 'unknown')}")
            print(f"   Routing score: {response.get('routing', {}).get('score', 'unknown')}")
            print(f"   Duration: {response.get('duration_ms', 0)}ms")
        return success

    def test_chat_complex(self):
        """Test complex chat message (should route to API)"""
        success, response = self.run_test(
            "Chat - Complex Message",
            "POST",
            "/chat",
            200,
            data={
                "message": "Please analyze the architectural patterns in modern distributed systems and compare microservices vs monolithic approaches with detailed pros and cons",
                "session_id": self.session_id,
                "white_card_mode": True
            },
            timeout=60
        )
        if success:
            print(f"   Provider used: {response.get('provider', 'unknown')}")
            print(f"   Model used: {response.get('model', 'unknown')}")
            print(f"   Routing score: {response.get('routing', {}).get('score', 'unknown')}")
            print(f"   Duration: {response.get('duration_ms', 0)}ms")
        return success

    def test_chat_history(self):
        """Test chat history endpoint"""
        if not self.session_id:
            print("⚠️  Skipping chat history test - no session ID")
            return True
            
        success, response = self.run_test(
            "Chat History",
            "GET",
            f"/chat/history?session_id={self.session_id}",
            200
        )
        if success:
            turns = response.get('turns', [])
            print(f"   Chat turns: {len(turns)}")
        return success

    def test_tasks_get(self):
        """Test get tasks endpoint"""
        success, response = self.run_test(
            "Get Tasks",
            "GET",
            "/tasks",
            200
        )
        if success:
            print(f"   Tasks count: {len(response)}")
        return success

    def test_tasks_create(self):
        """Test create task endpoint"""
        success, response = self.run_test(
            "Create Task",
            "POST",
            "/tasks",
            200,
            data={"title": "Test Task", "description": "Test task description", "priority": "medium"}
        )
        if success:
            print(f"   Created task ID: {response.get('_id', 'unknown')}")
        return success, response.get('_id') if success else None

    def test_memories_get(self):
        """Test get memories endpoint"""
        success, response = self.run_test(
            "Get Memories",
            "GET",
            "/memories",
            200
        )
        if success:
            print(f"   Memories count: {len(response)}")
        return success

    def test_white_card_suggestions(self):
        """Test white card suggestions endpoint"""
        success, response = self.run_test(
            "White Card Suggestions",
            "GET",
            "/white-card/suggestions",
            200
        )
        if success:
            suggestions = response.get('suggestions', [])
            print(f"   Suggestions count: {len(suggestions)}")
        return success

    # ============================================================
    # PHASE 4 TESTS: AUTONOMY DAEMON
    # ============================================================
    def test_autonomy_status(self):
        """Test autonomy daemon status endpoint"""
        success, response = self.run_test(
            "Autonomy Status",
            "GET",
            "/autonomy/status",
            200
        )
        if success:
            print(f"   Running: {response.get('running', False)}")
            print(f"   Paused: {response.get('paused', False)}")
            print(f"   Ticks: {response.get('stats', {}).get('ticks', 0)}")
            print(f"   Ideas generated: {response.get('stats', {}).get('ideas_generated', 0)}")
        return success, response

    def test_autonomy_pause(self):
        """Test autonomy daemon pause endpoint"""
        success, response = self.run_test(
            "Autonomy Pause",
            "POST",
            "/autonomy/pause",
            200
        )
        if success:
            print(f"   Status: {response.get('status', 'unknown')}")
        return success

    def test_autonomy_resume(self):
        """Test autonomy daemon resume endpoint"""
        success, response = self.run_test(
            "Autonomy Resume",
            "POST",
            "/autonomy/resume",
            200
        )
        if success:
            print(f"   Status: {response.get('status', 'unknown')}")
        return success

    def test_autonomy_stop(self):
        """Test autonomy daemon stop endpoint"""
        success, response = self.run_test(
            "Autonomy Stop",
            "POST",
            "/autonomy/stop",
            200
        )
        if success:
            print(f"   Status: {response.get('status', 'unknown')}")
        return success

    def test_autonomy_force_tick(self):
        """Test autonomy daemon force tick endpoint"""
        success, response = self.run_test(
            "Autonomy Force Tick",
            "POST",
            "/autonomy/tick",
            200
        )
        if success:
            print(f"   Status: {response.get('status', 'unknown')}")
            print(f"   Result: {response.get('result', {})}")
        return success

    # ============================================================
    # PHASE 4 TESTS: MEMORY MANAGEMENT
    # ============================================================
    def test_memory_decay(self):
        """Test memory decay endpoint"""
        success, response = self.run_test(
            "Memory Decay",
            "POST",
            "/memories/decay",
            200
        )
        if success:
            print(f"   Decayed: {response.get('decayed', 0)}")
            print(f"   Removed: {response.get('removed', 0)}")
        return success

    def test_memory_pin(self, memory_id):
        """Test memory pin/unpin endpoint"""
        if not memory_id:
            print("⚠️  Skipping memory pin test - no memory ID")
            return True
            
        success, response = self.run_test(
            "Memory Pin",
            "PUT",
            f"/memories/{memory_id}/pin?pinned=true",
            200
        )
        if success:
            print(f"   Pinned: {response.get('pinned', False)}")
        return success

    # ============================================================
    # PHASE 4 TESTS: TOOL SAFETY
    # ============================================================
    def test_tool_policies_get(self):
        """Test get tool policies endpoint"""
        success, response = self.run_test(
            "Get Tool Policies",
            "GET",
            "/tools/policies",
            200
        )
        if success:
            print(f"   Mode: {response.get('mode', 'unknown')}")
            print(f"   Denylist items: {len(response.get('denylist', []))}")
            print(f"   Allowlist items: {len(response.get('allowlist', []))}")
        return success

    def test_tool_policies_update(self):
        """Test update tool policies endpoint"""
        success, response = self.run_test(
            "Update Tool Policies",
            "PUT",
            "/tools/policies",
            200,
            data={"mode": "denylist", "denylist": ["rm -rf /", "shutdown"], "allowlist": ["ls", "cat"]}
        )
        return success

    def test_terminal_command_safe(self):
        """Test terminal command execution with safe command"""
        success, response = self.run_test(
            "Terminal Safe Command",
            "POST",
            "/tools/terminal",
            200,
            data={"command": "echo 'Hello World'", "timeout": 10}
        )
        if success:
            print(f"   Success: {response.get('success', False)}")
            print(f"   Output: {response.get('stdout', '')[:50]}...")
        return success

    def test_terminal_command_blocked(self):
        """Test terminal command execution with blocked command"""
        success, response = self.run_test(
            "Terminal Blocked Command",
            "POST",
            "/tools/terminal",
            200,
            data={"command": "rm -rf /", "timeout": 10}
        )
        if success:
            print(f"   Success: {response.get('success', False)}")
            print(f"   Error: {response.get('error', '')[:50]}...")
            # Should be blocked, so success=False in response
            if not response.get('success', True):
                print("   ✅ Command correctly blocked by safety policy")
            else:
                print("   ❌ Command was not blocked - safety policy failed!")
        return success

    # ============================================================
    # PHASE 4 TESTS: AGENTS & K1
    # ============================================================
    def test_agents_list(self):
        """Test list agents endpoint"""
        success, response = self.run_test(
            "List Agents",
            "GET",
            "/agents",
            200
        )
        if success:
            print(f"   Agents count: {len(response)}")
            builtin_agents = [a for a in response if a.get('builtin', False)]
            print(f"   Built-in agents: {len(builtin_agents)}")
        return success, response

    def test_k1_prompts(self):
        """Test K1 prompts endpoint"""
        success, response = self.run_test(
            "K1 Prompts",
            "GET",
            "/k1/prompts",
            200
        )
        if success:
            print(f"   K1 prompts count: {len(response)}")
            active_prompts = [p for p in response if p.get('active', False)]
            print(f"   Active prompts: {len(active_prompts)}")
        return success

    def test_k1_distillations(self):
        """Test K1 distillations endpoint"""
        success, response = self.run_test(
            "K1 Distillations",
            "GET",
            "/k1/distillations",
            200
        )
        if success:
            print(f"   Distillations count: {len(response)}")
        return success

    def test_learning_metrics(self):
        """Test learning metrics endpoint"""
        success, response = self.run_test(
            "Learning Metrics",
            "GET",
            "/learning/metrics",
            200
        )
        if success:
            print(f"   Provider performance entries: {len(response.get('provider_performance', {}))}")
            print(f"   Total feedback: {response.get('total_feedback', 0)}")
            print(f"   K1 prompts: {len(response.get('k1_prompts', []))}")
            print(f"   Distillations: {response.get('distillations', 0)}")
        return success

def main():
    print("🚀 Starting Ombra Phase 4 API Testing...")
    print("=" * 60)
    
    tester = OmbraAPITester()
    
    # Test basic health and system status
    print("\n📊 SYSTEM HEALTH TESTS")
    print("-" * 30)
    tester.test_health()
    tester.test_dashboard_summary()
    tester.test_dashboard_status()
    
    # Test permissions and onboarding
    print("\n🔐 PERMISSIONS & ONBOARDING TESTS")
    print("-" * 30)
    success, perms = tester.test_permissions_get()
    if success and not perms.get('onboarded', False):
        print("   User not onboarded, testing onboarding flow...")
        tester.test_onboarding()
    tester.test_permissions_update()
    
    # Test activity and settings
    print("\n⚙️  ACTIVITY & SETTINGS TESTS")
    print("-" * 30)
    tester.test_activity_get()
    tester.test_activity_summary()
    tester.test_settings_get()
    tester.test_settings_update()
    
    # Test chat functionality (most important)
    print("\n💬 CHAT FUNCTIONALITY TESTS")
    print("-" * 30)
    print("   Note: Chat responses may take 4-10 seconds due to Ollama...")
    tester.test_chat_simple()
    time.sleep(2)  # Brief pause between chat tests
    tester.test_chat_complex()
    tester.test_chat_history()
    
    # Test tasks and memories
    print("\n📋 TASKS & MEMORY TESTS")
    print("-" * 30)
    tester.test_tasks_get()
    task_success, task_id = tester.test_tasks_create()
    memories_success = tester.test_memories_get()
    tester.test_white_card_suggestions()
    
    # ============================================================
    # PHASE 4 TESTS
    # ============================================================
    
    # Test Autonomy Daemon
    print("\n🤖 PHASE 4: AUTONOMY DAEMON TESTS")
    print("-" * 30)
    autonomy_success, autonomy_status = tester.test_autonomy_status()
    if autonomy_success:
        # Test pause/resume/stop cycle
        tester.test_autonomy_pause()
        time.sleep(1)
        tester.test_autonomy_resume()
        time.sleep(1)
        tester.test_autonomy_force_tick()
        # Note: Not testing stop as it would permanently stop the daemon
    
    # Test Memory Management
    print("\n🧠 PHASE 4: MEMORY MANAGEMENT TESTS")
    print("-" * 30)
    tester.test_memory_decay()
    # Get a memory ID for pin test
    memories_success, memories_data = tester.run_test("Get Memories for Pin Test", "GET", "/memories", 200)
    if memories_success and memories_data:
        memory_id = memories_data[0].get('_id') if memories_data else None
        tester.test_memory_pin(memory_id)
    
    # Test Tool Safety
    print("\n🛡️  PHASE 4: TOOL SAFETY TESTS")
    print("-" * 30)
    tester.test_tool_policies_get()
    tester.test_tool_policies_update()
    tester.test_terminal_command_safe()
    tester.test_terminal_command_blocked()
    
    # Test Agents & K1 Learning
    print("\n🎯 PHASE 4: AGENTS & K1 LEARNING TESTS")
    print("-" * 30)
    agents_success, agents_data = tester.test_agents_list()
    tester.test_k1_prompts()
    tester.test_k1_distillations()
    tester.test_learning_metrics()
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 FINAL RESULTS: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed! Phase 4 backend is working correctly.")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed. Check the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())