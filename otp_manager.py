import random
import string
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# In-memory OTP storage
OTP_STORAGE = {}

# ============= OTP GENERATION =============
def generate_otp(length=6):
    """Generate a random OTP"""
    return ''.join(random.choices(string.digits, k=length))

# ============= OTP STORAGE =============
def store_otp(email, username, otp=None):
    """Store OTP for email"""
    try:
        if otp is None:
            otp = generate_otp()
        
        OTP_STORAGE[email] = {
            'otp': otp,
            'username': username,
            'created_at': datetime.now(),
            'attempts': 0
        }
        
        print(f"[OTP] Stored for {email}: {otp}")
        return otp
    
    except Exception as e:
        print(f"[ERROR] Error storing OTP: {e}")
        return None

def verify_otp(email, otp_code):
    """Verify OTP for email"""
    try:
        if email not in OTP_STORAGE:
            return False, "No OTP found for this email"
        
        otp_data = OTP_STORAGE[email]
        
        # Check if OTP is expired (10 minutes)
        created_at = otp_data['created_at']
        if datetime.now() - created_at > timedelta(minutes=10):
            del OTP_STORAGE[email]
            return False, "OTP has expired"
        
        # Check if too many attempts (5 attempts)
        if otp_data['attempts'] >= 5:
            del OTP_STORAGE[email]
            return False, "Too many incorrect attempts"
        
        # Verify OTP
        if otp_data['otp'] != str(otp_code):
            otp_data['attempts'] += 1
            return False, f"Invalid OTP. Attempts remaining: {5 - otp_data['attempts']}"
        
        # Success - remove OTP
        username = otp_data['username']
        del OTP_STORAGE[email]
        print(f"[OTP] Verified for {email}")
        return True, username
    
    except Exception as e:
        print(f"[ERROR] Error verifying OTP: {e}")
        return False, str(e)

def resend_otp(email, username):
    """Resend OTP to email"""
    try:
        otp = generate_otp()
        
        # Store the OTP
        store_otp(email, username, otp)
        
        # Send email
        success = send_otp_email(email, username, otp)
        
        if success:
            return True, f"OTP sent to {email}"
        else:
            return True, "OTP generated (Check terminal for code if email fails)"
    
    except Exception as e:
        print(f"[ERROR] Error resending OTP: {e}")
        return False, str(e)

# ============= EMAIL SENDING =============
def send_otp_email(email, username, otp):
    """Send OTP via email"""
    # Reload environment in case .env was updated
    load_dotenv(override=True)
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    sender_email = os.getenv("SENDER_EMAIL", "rakzan2k@gmail.com")
    sender_password = os.getenv("SENDER_PASSWORD", "").replace(" ", "")

    try:
        # Create email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = email
        msg['Subject'] = 'Your OTP Verification Code - Language Translator'
        
        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h2 style="color: #333;">Welcome, {username}!</h2>
                    
                    <p style="color: #666; font-size: 16px;">Your OTP verification code is:</p>
                    
                    <div style="background-color: #007bff; color: white; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0;">
                        <h1 style="margin: 0; font-size: 32px; letter-spacing: 5px;">{otp}</h1>
                    </div>
                    
                    <p style="color: #666; font-size: 14px;">
                        This code will expire in <strong>10 minutes</strong>. 
                        Do not share this code with anyone.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                    
                    <p style="color: #999; font-size: 12px;">
                        If you didn't request this code, please ignore this email.
                    </p>
                    
                    <p style="color: #999; font-size: 12px; margin-top: 20px;">
                        Language Translator Team
                    </p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        try:
            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
                if sender_password:
                    server.login(sender_email, sender_password)
                server.send_message(msg)
                server.quit()
            else:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
                server.ehlo()
                server.starttls()
                server.ehlo()
                if sender_password:
                    server.login(sender_email, sender_password)
                server.send_message(msg)
                server.quit()
            
            print(f"[SUCCESS] OTP email sent successfully to {email}")
            return True
        
        except smtplib.SMTPAuthenticationError:
            print(f"[WARNING] SMTP authentication failed for {sender_email}. Check Google App Password in .env")
            return False
        
        except Exception as e:
            print(f"[WARNING] Error sending email to {email}: {e}")
            return False
    
    except Exception as e:
        print(f"[ERROR] Error preparing email: {e}")
        return False

def get_otp_expiry_time(email):
    """Get remaining time for OTP in seconds"""
    try:
        if email not in OTP_STORAGE:
            return None
        
        otp_data = OTP_STORAGE[email]
        created_at = otp_data['created_at']
        expiry_time = created_at + timedelta(minutes=10)
        
        remaining = (expiry_time - datetime.now()).total_seconds()
        
        return max(0, int(remaining))
    
    except Exception as e:
        print(f"[ERROR] Error getting OTP expiry: {e}")
        return None

def cleanup_expired_otps():
    """Remove expired OTPs from storage"""
    try:
        expired = []
        
        for email, otp_data in OTP_STORAGE.items():
            created_at = otp_data['created_at']
            if datetime.now() - created_at > timedelta(minutes=10):
                expired.append(email)
        
        for email in expired:
            del OTP_STORAGE[email]
            print(f"[INFO] Cleaned up expired OTP for {email}")
    
    except Exception as e:
        print(f"[ERROR] Error cleaning up OTPs: {e}")
