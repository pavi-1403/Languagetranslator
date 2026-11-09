from flask import Flask, render_template, request, send_from_directory, session, redirect, url_for, flash
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from datetime import datetime, timedelta
import requests
from deep_translator import GoogleTranslator
from gtts import gTTS
from gtts.lang import tts_langs
import PyPDF2
import subprocess
import time
import gc
import whisper
import torch
from auth import (
    register_user, login_user, get_user_info, 
    save_translation, get_user_translations, delete_translation,
    user_exists, email_exists, update_password, get_username_by_email # Added new functions
)
import otp_manager # Added OTP manager
import re

# ---------------- APP SETUP ----------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "prod-secret-key-change-this-immediately")
UPLOAD_FOLDER = "uploads"
USER_FILES_FOLDER = "user_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(USER_FILES_FOLDER, exist_ok=True)

def check_ffmpeg():
    """Check if FFmpeg is installed and accessible"""
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print("[INFO] FFmpeg found. Video processing enabled.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[WARNING] FFmpeg not found! Video-to-text features will fail.")
        print("   Please install FFmpeg and add it to your system PATH.")

check_ffmpeg() # Run check on startup

# ---------------- 30+ gTTS-SUPPORTED LANGUAGES ----------------
LANGUAGES = {
    "en": "English",
    "ta": "Tamil",
    "hi": "Hindi",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "mr": "Marathi",
    "gu": "Gujarati",
    "bn": "Bengali",
    "ur": "Urdu",
    "ne": "Nepali",
    "si": "Sinhala",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "ja": "Japanese",
    "ko": "Korean",
    "id": "Indonesian",
    "tr": "Turkish",
    "sv": "Swedish",
    "nl": "Dutch",
    "pl": "Polish",
    "ro": "Romanian",
    "cs": "Czech"
}

# ---------------- GPU / CPU AUTO-SELECTION ----------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print("Using device:", device)

whisper_model = whisper.load_model("base", device=device)

# ---------------- SAFE DELETE ----------------
def safe_delete(path):
    if not os.path.exists(path):
        return
    for _ in range(5):
        try:
            os.remove(path)
            return
        except PermissionError:
            time.sleep(0.1)
            gc.collect()

# ---------------- FAST AUDIO EXTRACTION ----------------
def extract_audio_ffmpeg(video_path, wav_path):
    cmd = [
        "ffmpeg",
        "-y",
        "-threads", "4",
        "-i", video_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-b:a", "32k",
        wav_path
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception as e:
        print("FFmpeg audio extraction error:", e)
        return False

# ---------------- GPU-OPTIMIZED TRANSCRIPTION ----------------
def speech_to_text(wav_path):
    try:
        detect = whisper_model.transcribe(
            wav_path,
            fp16=torch.cuda.is_available(),
            temperature=0,
            task="transcribe"
        )

        detected_lang = detect.get("language", "auto")
        print("Detected language:", detected_lang)

        result = whisper_model.transcribe(
            wav_path,
            fp16=torch.cuda.is_available(),
            temperature=0,
            task="transcribe",
            language=detected_lang,
            beam_size=1,
            condition_on_previous_text=False
        )

        return result.get("text", "").strip()

    except Exception as e:
        print("Whisper error:", e)
        return ""

# ---------------- SAFE TTS (NO CRASHES) ----------------
def safe_tts(text, lang, path, retries=3):
    for attempt in range(retries):
        try:
            tts = gTTS(text=text, lang=lang)
            tts.save(path)
            return True
        except Exception as e:
            print(f"TTS error (attempt {attempt+1}):", e)
            time.sleep(1)
    return False

# ---------------- ROBUST TRANSLATION (WITH MULTI-FALLBACK & CHUNKING) ----------------
def translate_single_chunk(text, target_lang, source="auto"):
    if not text or not text.strip():
        return text

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }

    # Method 1: Google Translate API (gtx client)
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": source,
            "tl": target_lang,
            "dt": "t",
            "q": text
        }
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                translated_parts = [s[0] for s in data[0] if s and len(s) > 0 and s[0]]
                if translated_parts:
                    return "".join(translated_parts)
    except Exception as e:
        print(f"[WARN] Google GTX translation error: {e}")

    # Method 2: Google Translate API (dict-chrome-ex client)
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "dict-chrome-ex",
            "sl": source,
            "tl": target_lang,
            "dt": "t",
            "q": text
        }
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                translated_parts = [s[0] for s in data[0] if s and len(s) > 0 and s[0]]
                if translated_parts:
                    return "".join(translated_parts)
    except Exception as e:
        print(f"[WARN] Google dict-chrome-ex translation error: {e}")

    # Method 3: deep_translator MyMemory fallback
    try:
        from deep_translator import MyMemoryTranslator
        src = source if source != "auto" else "en"
        res = MyMemoryTranslator(source=src, target=target_lang).translate(text)
        if res:
            return res
    except Exception as e:
        print(f"[WARN] MyMemory fallback error: {e}")

    # Method 4: deep_translator GoogleTranslator fallback
    try:
        res = GoogleTranslator(source=source, target=target_lang).translate(text)
        if res:
            return res
    except Exception as e:
        print(f"[WARN] GoogleTranslator fallback error: {e}")

    raise Exception("Translation service temporarily unavailable. Please try again.")

def safe_translate(text, target_lang, source="auto", max_chunk_chars=2000):
    if not text or not text.strip():
        return text

    paragraphs = text.split("\n")
    translated_paragraphs = []

    current_chunk = []
    current_length = 0

    def flush_chunk(chunk_lines):
        if not chunk_lines:
            return ""
        chunk_text = "\n".join(chunk_lines)
        if not chunk_text.strip():
            return chunk_text
        for attempt in range(3):
            try:
                return translate_single_chunk(chunk_text, target_lang, source)
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(1 + attempt)
        return ""

    for line in paragraphs:
        if current_length + len(line) + 1 > max_chunk_chars and current_chunk:
            translated_paragraphs.append(flush_chunk(current_chunk))
            current_chunk = [line]
            current_length = len(line)
        else:
            current_chunk.append(line)
            current_length += len(line) + 1

    if current_chunk:
        translated_paragraphs.append(flush_chunk(current_chunk))

    return "\n".join(translated_paragraphs)

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    # If not logged in, redirect to login page
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # If logged in, redirect to translator page
    user = get_user_info(session['user_id'])
    return render_template("index.html", languages=LANGUAGES, user=user)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        user_id, message = login_user(username, password)
        
        if user_id:
            session['user_id'] = user_id
            session.permanent = True
            app.permanent_session_lifetime = timedelta(days=7)
            return redirect(url_for('index'))
        else:
            return render_template("login.html", error=message)
    
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        # Validation
        if not re.match(r"^[a-zA-Z0-9_]{3,20}$", username):
            return render_template("signup.html", error="Username must be 3-20 characters (letters, numbers, underscore only)")
        
        if password != confirm_password:
            return render_template("signup.html", error="Passwords do not match")

        # Check existing user
        if user_exists(username):
            return render_template("signup.html", error="Username already exists")
        
        if email_exists(email):
            return render_template("signup.html", error="Email already registered")
        
        # Store data in session to survive redirect
        session['signup_data'] = {
            'username': username,
            'email': email,
            'password': password
        }

        # Generate and Send OTP
        try:
            success, msg = otp_manager.resend_otp(email, username)
            if success:
                return redirect(url_for('verify_otp'))
            else:
                return render_template("signup.html", error=f"Failed to send OTP: {msg}")
        except Exception as e:
            return render_template("signup.html", error=f"Error sending OTP: {e}")
    
    return render_template("signup.html")

@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if 'signup_data' not in session:
        return redirect(url_for('signup'))
    
    email = session['signup_data']['email']
    username = session['signup_data']['username']

    if request.method == "POST":
        otp_input = request.form.get("otp", "").strip()
        
        success, msg = otp_manager.verify_otp(email, otp_input)
        
        if success:
            # Create actual user account
            password = session['signup_data']['password']
            reg_success, reg_msg = register_user(username, email, password)
            
            if reg_success:
                # Login automatically
                user_id, _ = login_user(username, password)
                session.pop('signup_data', None) # Clear temp data
                if user_id:
                    session['user_id'] = user_id
                    session.permanent = True
                    return redirect(url_for('index'))
                else:
                     return redirect(url_for('login'))
            else:
                return render_template("verify_otp.html", error=f"Registration failed: {reg_msg}")
        else:
            return render_template("verify_otp.html", error=msg)

    return render_template("verify_otp.html")

@app.route("/resend_otp")
def resend_otp_route():
    if 'signup_data' not in session:
        return redirect(url_for('signup'))
    
    email = session['signup_data']['email']
    username = session['signup_data']['username']
    
    success, msg = otp_manager.resend_otp(email, username)
    return render_template("verify_otp.html", success="OTP Resent!" if success else None, error=msg if not success else None)

# ---------------- PASSWORD RESET FLOW ----------------
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        
        if not email_exists(email):
            return render_template("forgot_password.html", error="Email address not found.")
        
        username = get_username_by_email(email)
        
        # Store in session for the verification steps
        session['reset_email'] = email
        session['reset_username'] = username
        
        # Send OTP
        success, msg = otp_manager.resend_otp(email, username)
        
        if success:
            return redirect(url_for('verify_reset_otp'))
        else:
            return render_template("forgot_password.html", error=f"Error sending OTP: {msg}")
            
    return render_template("forgot_password.html")

@app.route("/verify_reset_otp", methods=["GET", "POST"])
def verify_reset_otp():
    if 'reset_email' not in session:
        return redirect(url_for('forgot_password'))
        
    email = session['reset_email']
    
    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        
        success, msg = otp_manager.verify_otp(email, otp)
        if success:
            session['reset_verified'] = True
            return redirect(url_for('reset_new_password'))
        else:
            return render_template("verify_reset_otp.html", error=msg)
            
    return render_template("verify_reset_otp.html")

@app.route("/reset_new_password", methods=["GET", "POST"])
def reset_new_password():
    if 'reset_email' not in session or not session.get('reset_verified'):
        return redirect(url_for('forgot_password'))
        
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        if password != confirm_password:
            return render_template("reset_new_password.html", error="Passwords do not match")
            
        if len(password) < 6:
             return render_template("reset_new_password.html", error="Password must be at least 6 characters")
             
        email = session['reset_email']
        if update_password(email, password):
            # Cleanup session
            session.pop('reset_email', None)
            session.pop('reset_username', None)
            session.pop('reset_verified', None)
            return redirect(url_for('login'))
        else:
            return render_template("reset_new_password.html", error="Failed to update password. Try again.")
            
    return render_template("reset_new_password.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_user_info(session['user_id'])
    translations = get_user_translations(session['user_id'])
    
    return render_template("dashboard.html", user=user, translations=translations)

@app.route("/delete_translation", methods=["POST"])
def delete_translation_route():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    translation_id = request.form.get("translation_id")
    delete_translation(translation_id, session['user_id'])
    
    return redirect(url_for('dashboard'))

@app.route("/translate_page")
def translate_page():
    user = None
    if 'user_id' in session:
        user = get_user_info(session['user_id'])
    return render_template("index.html", languages=LANGUAGES, user=user)

@app.route("/translate", methods=["POST"])
def translate():
    target_lang = request.form.get("language")
    uid = datetime.now().strftime("%Y%m%d%H%M%S")
    extracted_text = ""
    input_type = ""
    user_id = session.get('user_id')
    user = get_user_info(user_id) if user_id else None

    files = request.files.getlist("file")
    uploaded_file = None
    for f in files:
        if f.filename and f.filename.strip() != "":
            uploaded_file = f
            break

    message = request.form.get("message") or ""

    # ---------- TEXT ----------
    if message.strip():
        extracted_text = message.strip()
        input_type = "Text"

    # ---------- PDF ----------
    elif uploaded_file and uploaded_file.filename.lower().endswith(".pdf"):
        pdf_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(pdf_path)

        try:
            reader = PyPDF2.PdfReader(pdf_path)
            for page in reader.pages:
                extracted_text += page.extract_text() or ""
        except Exception as e:
            safe_delete(pdf_path)
            return render_template("result.html", error=f"PDF error: {e}", user=user)

        safe_delete(pdf_path)
        input_type = "PDF"

    # ---------- VIDEO ----------
    elif uploaded_file and uploaded_file.filename.lower().endswith(".mp4"):
        video_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(video_path)

        wav_path = os.path.join(UPLOAD_FOLDER, f"{uid}.wav")

        ok = extract_audio_ffmpeg(video_path, wav_path)
        if not ok:
            safe_delete(video_path)
            return render_template("result.html", error="Audio extraction failed.", user=user)

        extracted_text = speech_to_text(wav_path)

        safe_delete(video_path)
        safe_delete(wav_path)
        input_type = "Video"

    else:
        return render_template("result.html", error="No valid file selected", user=user)

    if not extracted_text:
        return render_template("result.html", error="No readable content found", user=user)

    # ---------- TRANSLATION ----------
    try:
        translated = safe_translate(extracted_text, target_lang=target_lang)
    except Exception as e:
        return render_template("result.html", error=f"Translation failed: {e}", user=user)

    # ---------- AUDIO OUTPUT (SAFE) ----------
    if target_lang not in tts_langs():
        return render_template("result.html", error="Audio output not supported for this language.", user=user)

    audio_name = f"translated_{uid}.mp3"
    text_name = f"translated_{uid}.txt"
    
    # Determine storage location
    if user:
        # Store in user folder
        user_folder = os.path.join(USER_FILES_FOLDER, user['username'])
        os.makedirs(user_folder, exist_ok=True)
        audio_path = os.path.join(user_folder, audio_name)
        text_path = os.path.join(user_folder, text_name)
    else:
        # Store in guest folder
        audio_path = os.path.join(UPLOAD_FOLDER, audio_name)
        text_path = os.path.join(UPLOAD_FOLDER, text_name)

    if not safe_tts(translated, target_lang, audio_path):
        return render_template("result.html", error="Text-to-speech failed. Check your internet.", user=user)

    # ---------- TEXT OUTPUT ----------
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(translated)

    # ---------- SAVE TO DATABASE IF USER IS LOGGED IN ----------
    if user:
        save_translation(
            user_id,
            input_type,
            extracted_text,
            translated,
            target_lang,
            LANGUAGES[target_lang],
            text_name,
            audio_name
        )

    return render_template(
        "result.html",
        original=extracted_text,
        translated=translated,
        audio_file=audio_name,
        text_file=text_name,
        language=LANGUAGES[target_lang],
        input_type=input_type,
        user=user
    )

@app.route("/uploads/<filename>")
def uploads(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/user_files/<username>/<filename>")
def download_user_file(username, filename):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_user_info(session['user_id'])
    if user['username'] != username:
        return "Unauthorized", 403
    
    user_folder = os.path.join(USER_FILES_FOLDER, username)
    return send_from_directory(user_folder, filename)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)