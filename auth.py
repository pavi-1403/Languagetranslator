
import json
import hashlib
import os
import time
from datetime import datetime

# Database file constants
DATABASE_FOLDER = "database"
USERS_FILE = os.path.join(DATABASE_FOLDER, "users.json")
TRANSLATIONS_FILE = os.path.join(DATABASE_FOLDER, "translations.json")

# ============= FILE HELPERS =============
def ensure_db_exists():
    """Ensure database folder and JSON files exist"""
    if not os.path.exists(DATABASE_FOLDER):
        os.makedirs(DATABASE_FOLDER)
    
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump([], f)
            
    if not os.path.exists(TRANSLATIONS_FILE):
        with open(TRANSLATIONS_FILE, 'w') as f:
            json.dump([], f)

def load_json(file_path):
    """Load data from JSON file"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_json(file_path, data):
    """Save data to JSON file"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

# ============= PASSWORD HASHING =============
def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    """Verify password against hash"""
    return hash_password(password) == password_hash

# ============= USER OPERATIONS =============
def get_next_id(data_list):
    """Generate next numeric ID"""
    if not data_list:
        return 1
    return max(item['id'] for item in data_list) + 1

def user_exists(username):
    """Check if username exists"""
    users = load_json(USERS_FILE)
    return any(u['username'] == username for u in users)

def email_exists(email):
    """Check if email exists"""
    users = load_json(USERS_FILE)
    return any(u['email'] == email for u in users)

def register_user(username, email, password):
    """Register a new user"""
    ensure_db_exists()
    users = load_json(USERS_FILE)
    
    if any(u['username'] == username for u in users):
        return False, "Username already exists"
    
    if any(u['email'] == email for u in users):
        return False, "Email already registered"
    
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    
    new_user = {
        'id': get_next_id(users),
        'username': username,
        'email': email,
        'password_hash': hash_password(password),
        'created_at': datetime.now().isoformat()
    }
    
    users.append(new_user)
    save_json(USERS_FILE, users)
    
    # Create user directory
    user_folder = f"user_files/{username}"
    os.makedirs(user_folder, exist_ok=True)
    
    return True, "User registered successfully"

def update_password(email, new_password):
    """Update user password"""
    ensure_db_exists()
    users = load_json(USERS_FILE)
    
    user = next((u for u in users if u['email'] == email), None)
    
    if user is None:
        return False, "User not found"
        
    user['password_hash'] = hash_password(new_password)
    save_json(USERS_FILE, users)
    
    return True, "Password updated successfully"

def get_username_by_email(email):
    """Find username by email address"""
    ensure_db_exists()
    users = load_json(USERS_FILE)
    user = next((u for u in users if u['email'] == email), None)
    return user['username'] if user else None

def login_user(username, password):
    """Login user and return user_id if successful"""
    ensure_db_exists()
    users = load_json(USERS_FILE)
    
    user = next((u for u in users if u['username'] == username), None)
    
    if user is None:
        return None, "Username not found"
    
    if not verify_password(password, user['password_hash']):
        return None, "Incorrect password"
    
    return user['id'], "Login successful"

def get_user_info(user_id):
    """Get user information by ID"""
    ensure_db_exists()
    users = load_json(USERS_FILE)
    
    user = next((u for u in users if u['id'] == user_id), None)
    
    if user:
        return {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "created_at": user['created_at']
        }
    return None

# ============= TRANSLATION HISTORY =============
def save_translation(user_id, input_type, original_text, translated_text, target_lang, lang_name, text_file, audio_file):
    """Save translation to history"""
    ensure_db_exists()
    translations = load_json(TRANSLATIONS_FILE)
    
    new_translation = {
        'id': get_next_id(translations),
        'user_id': user_id,
        'input_type': input_type,
        'original_text': original_text,
        'translated_text': translated_text,
        'target_language': target_lang,
        'language_name': lang_name,
        'text_file': text_file,
        'audio_file': audio_file,
        'created_at': datetime.now().isoformat()
    }
    
    translations.append(new_translation)
    save_json(TRANSLATIONS_FILE, translations)

def get_user_translations(user_id, limit=20):
    """Get translation history for a user"""
    ensure_db_exists()
    translations = load_json(TRANSLATIONS_FILE)
    
    # Filter by user_id
    user_translations = [t for t in translations if t['user_id'] == user_id]
    
    # Sort by created_at desc (newest first)
    user_translations.sort(key=lambda x: x['created_at'], reverse=True)
    
    return user_translations[:limit]

def delete_translation(translation_id, user_id):
    """Delete a translation record"""
    ensure_db_exists()
    translations = load_json(TRANSLATIONS_FILE)
    
    # Filter out the translation to be deleted
    # Convert translation_id to int because form data might be string
    try:
        t_id = int(translation_id)
        new_translations = [t for t in translations if not (t['id'] == t_id and t['user_id'] == user_id)]
        save_json(TRANSLATIONS_FILE, new_translations)
    except ValueError:
        pass # Invalid ID format

# Initialize database check on import
ensure_db_exists()
