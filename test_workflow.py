
import os
import unittest
import json
import shutil
from flask import session
from app import app
import auth
import otp_manager

class TestWorkflow(unittest.TestCase):
    def setUp(self):
        self.test_email = "testflow@example.com"
        self.test_user = "flowuser"
        self.test_pass = "password123"
        self.app = app.test_client()
        self.app.testing = True
        
        # Ensure clean state for JSON DB
        self.clean_json_db()

    def clean_json_db(self):
        # Remove test user from JSON file
        auth.ensure_db_exists()
        users = auth.load_json(auth.USERS_FILE)
        users = [u for u in users if u['username'] != self.test_user]
        auth.save_json(auth.USERS_FILE, users)

    def test_signup_otp_flow(self):
        print("\nTesting Signup -> OTP Flow (JSON DB)...")
        
        # 1. Signup Request
        response = self.app.post('/signup', data={
            'username': self.test_user,
            'email': self.test_email,
            'password': self.test_pass,
            'confirm_password': self.test_pass
        }, follow_redirects=True)
        
        # Should be redirected to verify_otp
        self.assertIn(b'Verify your email', response.data)
        
        # 2. Extract OTP (Backend backdoor for testing)
        otp = otp_manager.OTP_STORAGE.get(self.test_email, {}).get('otp')
        self.assertIsNotNone(otp, "OTP was not generated/stored")
        print(f"Captured OTP: {otp}")
        
        # 3. Submit OTP
        with self.app.session_transaction() as sess:
            # Simulate session state that signals valid signup flow
            sess['signup_data'] = {
                'username': self.test_user,
                'email': self.test_email,
                'password': self.test_pass
            }
            
        response = self.app.post('/verify_otp', data={'otp': otp}, follow_redirects=True)
        
        # 4. Success - should be on Translator page (index)
        self.assertIn(b'AI Multilingual Translator', response.data)
        
        # 5. Verify DB (JSON)
        exists = auth.user_exists(self.test_user)
        self.assertTrue(exists, "User should be in JSON database after verification")
        
        # Verify JSON file content directly
        users = auth.load_json(auth.USERS_FILE)
        user_record = next((u for u in users if u['username'] == self.test_user), None)
        self.assertIsNotNone(user_record)
        self.assertEqual(user_record['email'], self.test_email)
        
        print("Flow Verified Successfully")

    def tearDown(self):
        # Cleanup
        self.clean_json_db()

if __name__ == '__main__':
    unittest.main()
