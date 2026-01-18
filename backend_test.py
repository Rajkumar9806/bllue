#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for DateNightPlanner
Tests all backend endpoints with realistic data
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://surprisely.preview.emergentagent.com/api"
TIMEOUT = 30

class DateNightPlannerTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.session.timeout = TIMEOUT
        self.test_results = []
        self.user_token = None
        self.user_id = None
        self.user2_id = None
        self.test_phone = "+1234567890"
        self.test_phone2 = "+1987654321"
        
    def log_test(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        if response_data:
            result["response"] = response_data
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        
    def make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None, headers: Dict = None) -> tuple:
        """Make HTTP request and return (success, response_data, status_code)"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            if headers is None:
                headers = {"Content-Type": "application/json"}
            
            if method.upper() == "GET":
                response = self.session.get(url, params=params, headers=headers)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, params=params, headers=headers)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, headers=headers)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params, headers=headers)
            else:
                return False, {"error": f"Unsupported method: {method}"}, 0
                
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}
                
            return response.status_code < 400, response_data, response.status_code
            
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}, 0
    
    def test_auth_flow(self):
        """Test complete authentication flow"""
        print("\n=== Testing Authentication Flow ===")
        
        # Test 1: Send OTP
        success, response, status_code = self.make_request(
            "POST", "/auth/send-otp",
            {"phone_number": self.test_phone}
        )
        
        if success and response.get("success"):
            otp = response.get("otp")  # In MVP, OTP is returned for testing
            self.log_test("Send OTP", True, f"OTP sent successfully: {otp}")
        else:
            self.log_test("Send OTP", False, f"Failed to send OTP: {response}")
            return False
            
        # Test 2: Verify OTP
        success, response, status_code = self.make_request(
            "POST", "/auth/verify-otp",
            {"phone_number": self.test_phone, "otp": otp}
        )
        
        if success and response.get("success"):
            self.user_token = response.get("token")
            self.user_id = response.get("user", {}).get("id")
            is_new_user = response.get("is_new_user")
            self.log_test("Verify OTP", True, f"OTP verified, new_user: {is_new_user}, user_id: {self.user_id}")
        else:
            self.log_test("Verify OTP", False, f"Failed to verify OTP: {response}")
            return False
            
        return True
    
    def test_user_profile(self):
        """Test user profile operations"""
        print("\n=== Testing User Profile ===")
        
        if not self.user_id:
            self.log_test("User Profile", False, "No user_id available")
            return False
            
        # Test 3: Get user profile
        success, response, status_code = self.make_request(
            "GET", f"/user/profile/{self.user_id}"
        )
        
        if success and response.get("id"):
            self.log_test("Get User Profile", True, f"Profile retrieved for user: {response.get('phone_number')}")
        else:
            self.log_test("Get User Profile", False, f"Failed to get profile: {response}")
            
        # Test 4: Update user profile
        profile_updates = {
            "name": "Sarah Johnson",
            "email": "sarah.johnson@email.com"
        }
        
        success, response, status_code = self.make_request(
            "PUT", f"/user/profile/{self.user_id}",
            profile_updates
        )
        
        if success and response.get("name") == "Sarah Johnson":
            self.log_test("Update User Profile", True, f"Profile updated successfully")
        else:
            self.log_test("Update User Profile", False, f"Failed to update profile: {response}")
            
        return True
    
    def test_personality_questionnaire(self):
        """Test personality questionnaire submission"""
        print("\n=== Testing Personality Questionnaire ===")
        
        if not self.user_id:
            self.log_test("Personality Questionnaire", False, "No user_id available")
            return False
            
        # Test 5: Submit personality questionnaire
        questionnaire_data = {
            "user_id": self.user_id,
            "personality_type": "romantic",
            "interests": ["movies", "dining", "travel", "art", "music"],
            "budget_range": "medium",
            "indoor_outdoor_preference": "both",
            "favorite_activities": ["dinner dates", "movie nights", "hiking", "concerts"],
            "relationship_status": "dating"
        }
        
        success, response, status_code = self.make_request(
            "POST", "/personality/submit",
            questionnaire_data
        )
        
        if success and response.get("success"):
            self.log_test("Submit Personality Questionnaire", True, "Personality data saved successfully")
        else:
            self.log_test("Submit Personality Questionnaire", False, f"Failed to save personality: {response}")
            
        return True
    
    def test_date_ideas_generation(self):
        """Test AI-powered date ideas generation"""
        print("\n=== Testing Date Ideas Generation ===")
        
        if not self.user_id:
            self.log_test("Date Ideas Generation", False, "No user_id available")
            return False
            
        # Test 6: Generate personalized date ideas
        success, response, status_code = self.make_request(
            "POST", "/date-ideas/generate",
            {"user_id": self.user_id, "count": 5}
        )
        
        if success and response.get("success") and response.get("date_ideas"):
            ideas = response.get("date_ideas", [])
            self.log_test("Generate Personalized Date Ideas", True, f"Generated {len(ideas)} personalized ideas")
            
            # Validate structure of first idea
            if ideas and len(ideas) > 0:
                first_idea = ideas[0]
                required_fields = ["id", "title", "description", "category", "budget_estimate", "duration", "location_type"]
                missing_fields = [field for field in required_fields if field not in first_idea]
                if not missing_fields:
                    self.log_test("Date Ideas Structure Validation", True, "All required fields present")
                else:
                    self.log_test("Date Ideas Structure Validation", False, f"Missing fields: {missing_fields}")
        else:
            self.log_test("Generate Personalized Date Ideas", False, f"Failed to generate ideas: {response}")
            
        # Test 7: Get trending date ideas
        success, response, status_code = self.make_request(
            "GET", "/date-ideas/trending",
            params={"count": 8}
        )
        
        if success and response.get("success") and response.get("date_ideas"):
            trending_ideas = response.get("date_ideas", [])
            self.log_test("Get Trending Date Ideas", True, f"Retrieved {len(trending_ideas)} trending ideas")
        else:
            self.log_test("Get Trending Date Ideas", False, f"Failed to get trending ideas: {response}")
            
        return True
    
    def test_wishlist_operations(self):
        """Test wishlist operations"""
        print("\n=== Testing Wishlist Operations ===")
        
        if not self.user_id:
            self.log_test("Wishlist Operations", False, "No user_id available")
            return False
            
        # Create a sample date idea for wishlist
        sample_date_idea = {
            "id": "test-date-idea-123",
            "title": "Sunset Beach Picnic",
            "description": "Romantic picnic on the beach during sunset with homemade treats",
            "category": "romantic",
            "budget_estimate": "$",
            "duration": "3-4 hours",
            "location_type": "outdoor"
        }
        
        # Test 8: Add to wishlist
        wishlist_item = {
            "user_id": self.user_id,
            "date_idea_id": sample_date_idea["id"],
            "date_idea": sample_date_idea,
            "notes": "Perfect for our anniversary!",
            "is_favorite": True
        }
        
        success, response, status_code = self.make_request(
            "POST", "/wishlist/add",
            wishlist_item
        )
        
        item_id = None
        if success and response.get("success"):
            item_id = response.get("item_id")
            self.log_test("Add to Wishlist", True, f"Added to wishlist with ID: {item_id}")
        else:
            self.log_test("Add to Wishlist", False, f"Failed to add to wishlist: {response}")
            
        # Test 9: Get user wishlist
        success, response, status_code = self.make_request(
            "GET", f"/wishlist/{self.user_id}"
        )
        
        if success and response.get("success"):
            wishlist = response.get("wishlist", [])
            self.log_test("Get User Wishlist", True, f"Retrieved wishlist with {len(wishlist)} items")
        else:
            self.log_test("Get User Wishlist", False, f"Failed to get wishlist: {response}")
            
        # Test 10: Remove from wishlist
        if item_id:
            success, response, status_code = self.make_request(
                "DELETE", f"/wishlist/{item_id}",
                params={"user_id": self.user_id}
            )
            
            if success and response.get("success"):
                self.log_test("Remove from Wishlist", True, "Item removed successfully")
            else:
                self.log_test("Remove from Wishlist", False, f"Failed to remove item: {response}")
        
        return True
    
    def test_connections_flow(self):
        """Test connections and invite system"""
        print("\n=== Testing Connections Flow ===")
        
        if not self.user_id:
            self.log_test("Connections Flow", False, "No user_id available")
            return False
            
        # Create second user for connection testing
        success, response, status_code = self.make_request(
            "POST", "/auth/send-otp",
            {"phone_number": self.test_phone2}
        )
        
        if success and response.get("otp"):
            otp2 = response.get("otp")
            success, response, status_code = self.make_request(
                "POST", "/auth/verify-otp",
                {"phone_number": self.test_phone2, "otp": otp2}
            )
            if success:
                self.user2_id = response.get("user", {}).get("id")
                self.log_test("Create Second User", True, f"Second user created: {self.user2_id}")
            
        # Test 11: Create invite code
        success, response, status_code = self.make_request(
            "POST", "/connections/create-invite",
            params={"user_id": self.user_id, "connection_type": "partner"}
        )
        
        invite_code = None
        if success and response.get("success"):
            invite_code = response.get("invite_code")
            self.log_test("Create Connection Invite", True, f"Invite code created: {invite_code}")
        else:
            self.log_test("Create Connection Invite", False, f"Failed to create invite: {response}")
            
        # Test 12: Accept invite
        if invite_code and self.user2_id:
            success, response, status_code = self.make_request(
                "POST", "/connections/accept-invite",
                {"invite_code": invite_code, "user_id": self.user2_id}
            )
            
            if success and response.get("success"):
                self.log_test("Accept Connection Invite", True, "Connection established successfully")
            else:
                self.log_test("Accept Connection Invite", False, f"Failed to accept invite: {response}")
                
        # Test 13: Get user connections
        success, response, status_code = self.make_request(
            "GET", f"/connections/{self.user_id}"
        )
        
        if success and response.get("success"):
            connections = response.get("connections", [])
            self.log_test("Get User Connections", True, f"Retrieved {len(connections)} connections")
        else:
            self.log_test("Get User Connections", False, f"Failed to get connections: {response}")
            
        # Test 14: Get partner wishlist
        success, response, status_code = self.make_request(
            "GET", f"/connections/partner-wishlist/{self.user_id}"
        )
        
        if success and response.get("success"):
            partner_wishlists = response.get("partner_wishlists", [])
            self.log_test("Get Partner Wishlist", True, f"Retrieved {len(partner_wishlists)} partner wishlists")
        else:
            self.log_test("Get Partner Wishlist", False, f"Failed to get partner wishlist: {response}")
            
        return True
    
    def test_occasions_calendar(self):
        """Test occasions and calendar functionality"""
        print("\n=== Testing Occasions & Calendar ===")
        
        if not self.user_id:
            self.log_test("Occasions Calendar", False, "No user_id available")
            return False
            
        # Test 15: Add occasion
        future_date = datetime.now() + timedelta(days=30)
        occasion_data = {
            "user_id": self.user_id,
            "person_name": "Sarah",
            "occasion_type": "birthday",
            "date": future_date.isoformat(),
            "reminder_days_before": 7,
            "notes": "Don't forget to plan something special!"
        }
        
        success, response, status_code = self.make_request(
            "POST", "/occasions/add",
            occasion_data
        )
        
        occasion_id = None
        if success and response.get("success"):
            occasion_id = response.get("occasion_id")
            self.log_test("Add Occasion", True, f"Occasion added with ID: {occasion_id}")
        else:
            self.log_test("Add Occasion", False, f"Failed to add occasion: {response}")
            
        # Test 16: Get all occasions
        success, response, status_code = self.make_request(
            "GET", f"/occasions/{self.user_id}"
        )
        
        if success and response.get("success"):
            occasions = response.get("occasions", [])
            self.log_test("Get All Occasions", True, f"Retrieved {len(occasions)} occasions")
        else:
            self.log_test("Get All Occasions", False, f"Failed to get occasions: {response}")
            
        # Test 17: Get upcoming occasions
        success, response, status_code = self.make_request(
            "GET", f"/occasions/upcoming/{self.user_id}",
            params={"days": 60}
        )
        
        if success and response.get("success"):
            upcoming = response.get("upcoming_occasions", [])
            self.log_test("Get Upcoming Occasions", True, f"Retrieved {len(upcoming)} upcoming occasions")
        else:
            self.log_test("Get Upcoming Occasions", False, f"Failed to get upcoming occasions: {response}")
            
        # Test 18: Delete occasion
        if occasion_id:
            success, response, status_code = self.make_request(
                "DELETE", f"/occasions/{occasion_id}",
                params={"user_id": self.user_id}
            )
            
            if success and response.get("success"):
                self.log_test("Delete Occasion", True, "Occasion deleted successfully")
            else:
                self.log_test("Delete Occasion", False, f"Failed to delete occasion: {response}")
                
        return True
    
    def test_gift_suggestions(self):
        """Test AI-powered gift suggestions"""
        print("\n=== Testing Gift Suggestions ===")
        
        # Test 19: Get gift suggestions
        success, response, status_code = self.make_request(
            "POST", "/gifts/suggestions",
            params={
                "occasion_type": "birthday",
                "person_name": "Sarah",
                "budget": "medium"
            }
        )
        
        if success and response.get("success"):
            suggestions = response.get("suggestions", [])
            self.log_test("Get Gift Suggestions", True, f"Generated {len(suggestions)} gift suggestions")
        else:
            self.log_test("Get Gift Suggestions", False, f"Failed to get gift suggestions: {response}")
            
        return True
    
    def test_user_behavior_tracking(self):
        """Test user behavior tracking"""
        print("\n=== Testing User Behavior Tracking ===")
        
        if not self.user_id:
            self.log_test("User Behavior Tracking", False, "No user_id available")
            return False
            
        # Test 20: Track user behavior
        behavior_data = {
            "user_id": self.user_id,
            "date_idea_id": "test-idea-456",
            "action": "liked"
        }
        
        success, response, status_code = self.make_request(
            "POST", "/behavior/track",
            behavior_data
        )
        
        if success and response.get("success"):
            self.log_test("Track User Behavior", True, "Behavior tracked successfully")
        else:
            self.log_test("Track User Behavior", False, f"Failed to track behavior: {response}")
            
        return True
    
    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting DateNightPlanner Backend API Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        start_time = time.time()
        
        # Run all test suites
        test_suites = [
            self.test_auth_flow,
            self.test_user_profile,
            self.test_personality_questionnaire,
            self.test_date_ideas_generation,
            self.test_wishlist_operations,
            self.test_connections_flow,
            self.test_occasions_calendar,
            self.test_gift_suggestions,
            self.test_user_behavior_tracking
        ]
        
        for test_suite in test_suites:
            try:
                test_suite()
            except Exception as e:
                print(f"❌ CRITICAL ERROR in {test_suite.__name__}: {str(e)}")
                self.log_test(test_suite.__name__, False, f"Critical error: {str(e)}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Generate summary
        self.generate_summary(duration)
    
    def generate_summary(self, duration: float):
        """Generate test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t["success"]])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print(f"Duration: {duration:.2f} seconds")
        
        if failed_tests > 0:
            print("\n🔍 FAILED TESTS:")
            for test in self.test_results:
                if not test["success"]:
                    print(f"  ❌ {test['test']}: {test['details']}")
        
        print("\n✨ Test completed!")
        
        # Save detailed results to file
        with open("/app/backend_test_results.json", "w") as f:
            json.dump({
                "summary": {
                    "total_tests": total_tests,
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "success_rate": (passed_tests/total_tests)*100,
                    "duration": duration,
                    "timestamp": datetime.now().isoformat()
                },
                "detailed_results": self.test_results
            }, f, indent=2)

if __name__ == "__main__":
    tester = DateNightPlannerTester()
    tester.run_all_tests()