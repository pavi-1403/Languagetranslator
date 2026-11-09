
import os
import unittest
import auth
import otp_manager
from app import app
from flask import session

class TestPasswordReset(unittest.TestCase):
    def setUp(self):
        self.test_email = "reset_test@example.com"
        self.test_user = "resetuser"
        self.old_pass = "oldpass123"
        self.new_pass = "newpass456"
        self.app = app.test_client()
        self.app.testing = True
        
        # Setup: Register user directly
        self.clean_json_db()
        auth.register_user(self.test_user, self.test_email, self.old_pass)

    def clean_json_db(self):
        auth.ensure_db_exists()
        users = auth.load_json(auth.USERS_FILE)
        users = [u for u in users if u['username'] != self.test_user]
        auth.save_json(auth.USERS_FILE, users)

    def test_reset_flow(self):
        print("\nTesting Password Reset Flow...")

        # 1. Request Forgot Password
        response = self.app.post('/forgot_password', data={'email': self.test_email}, follow_redirects=True)
        self.assertIn(b'Verify Identity', response.data)
        
        # 2. Get OTP
        otp = otp_manager.OTP_STORAGE.get(self.test_email, {}).get('otp')
        self.assertIsNotNone(otp)
        print(f"Captured OTP: {otp}")

        # 3. Verify OTP
        with self.app.session_transaction() as sess:
           sess['reset_email'] = self.test_email
           
        response = self.app.post('/verify_reset_otp', data={'otp': otp}, follow_redirects=True)
        self.assertIn(b'Set New Password', response.data)
        
        # 4. Set New Password
        with self.app.session_transaction() as sess:
            sess['reset_email'] = self.test_email
            sess['reset_verified'] = True
            
        response = self.app.post('/reset_new_password', data={
            'password': self.new_pass,
            'confirm_password': self.new_pass
        }, follow_redirects=True)
        
        # Should redirect to login
        self.assertIn(b'Login', response.data)
        
        # 5. Verify Login with new password
        login_res = self.app.post('/login', data={'username': self.test_user, 'password': self.new_pass}, follow_redirects=True)
        self.assertIn(b'Logout', login_res.data) # Check for logout button indicating success
        print("Password Reset Verified Successfully")

    def tearDown(self):
        self.clean_json_db()

if __name__ == '__main__':
    unittest.main()
