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

def main():
    print("🚀 Starting Ombra API Testing...")
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
    task_id = tester.test_tasks_create()[1] if tester.test_tasks_create()[0] else None
    tester.test_memories_get()
    tester.test_white_card_suggestions()
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 FINAL RESULTS: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed! Backend is working correctly.")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed. Check the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())