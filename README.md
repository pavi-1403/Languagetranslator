# Language Translator

A Flask-based multilingual translation web app that converts **text, PDF documents, and videos** into **28+ languages**, producing both translated text and spoken audio (Text-to-Speech). It includes user accounts with email OTP verification, a personal translation history dashboard, and a robust multi-provider translation engine with automatic fallbacks.

---

## Features

- **Multi-format input**
  - Plain text
  - PDF files (text extraction via PyPDF2)
  - MP4 videos (audio extraction via FFmpeg + speech recognition via OpenAI Whisper)
- **28+ target languages** including English, Tamil, Hindi, Telugu, Malayalam, Kannada, French, German, Spanish, Arabic, Japanese, Korean, and more.
- **Automatic language detection** for video/audio transcription.
- **Text-to-Speech output** (MP3) using gTTS.
- **Downloadable results** – translated text (`.txt`) and audio (`.mp3`).
- **Robust translation engine** with multiple fallbacks:
  1. Google Translate (gtx client)
  2. Google Translate (dict-chrome-ex client)
  3. MyMemory (via `deep-translator`)
  4. GoogleTranslator (via `deep-translator`)
  - Long text is automatically chunked to avoid request limits.
- **User authentication**
  - Sign up with email OTP verification (6-digit, 10-minute expiry, 5-attempt limit).
  - Login / logout with session management (7-day sessions).
  - Forgot-password flow with OTP verification.
  - Passwords stored as SHA-256 hashes.
- **Personal dashboard** – view, download, and delete translation history.
- **Guest access** – translation works without logging in (history is not saved).
- **GPU acceleration** – automatically uses CUDA if available, otherwise CPU.
- **Production-ready** – runs via Waitress (`run_production.py`).

---

## Tech Stack

| Category | Technology |
|----------|------------|
| Backend | Flask, Python |
| Translation | `deep-translator`, Google Translate endpoints |
| Speech-to-Text | OpenAI Whisper |
| Text-to-Speech | gTTS |
| PDF Parsing | PyPDF2 |
| Audio/Video | FFmpeg |
| ML Runtime | PyTorch |
| Auth / OTP | `smtplib` (SMTP), SHA-256 |
| Storage | JSON files |
| Server | Waitress |

---

## Project Structure

```
language-translator/
├── app.py                 # Main Flask app: routes, translation, TTS, video pipeline
├── auth.py                # User registration, login, password hashing, history storage
├── otp_manager.py         # OTP generation, storage, verification, email sending
├── run_production.py      # Waitress production server entry point
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
├── database/              # JSON "database" (users.json, translations.json)
├── templates/             # HTML pages (login, signup, dashboard, result, etc.)
├── static/                # CSS and static assets
├── uploads/               # Temporary uploads + generated guest files
└── user_files/            # Per-user generated audio/text files
```

---

## Prerequisites

- **Python 3.9+**
- **FFmpeg** installed and available on your system `PATH` (required for video processing)
  - Linux: `sudo apt install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Windows: download from [ffmpeg.org](https://ffmpeg.org/) and add to `PATH`
- A Gmail account with an **App Password** for OTP emails (or any SMTP provider)

---

## Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd language-translator

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

> Note: `openai-whisper` will download the `base` model on first run. An internet connection is required.

---

## Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

`.env` variables:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
SECRET_KEY=change_this_to_a_random_string
```

- `SENDER_PASSWORD` must be a **Google App Password** (not your normal Gmail password) when using Gmail.
- `SECRET_KEY` should be a long random string — used to sign Flask sessions.

---

## Running the App

**Development:**

```bash
python app.py
```

**Production (Waitress):**

```bash
python run_production.py
```

The app will be available at `http://localhost:5000`.

---

## Usage

1. **Sign up** with a username, email, and password.
2. Enter the **OTP** sent to your email to verify your account.
3. On the translator page:
   - Enter text **or** upload a `.pdf` / `.mp4` file.
   - Select the target language.
   - Click translate.
4. View the **translated text**, play/download the **MP3 audio**, or download the **text file**.
5. Logged-in users can revisit results from the **Dashboard** and delete entries.

---

## How It Works

```
Input (Text / PDF / MP4)
        │
        ├── Text  ──────────────► raw text
        ├── PDF   ── PyPDF2 ────► extracted text
        └── MP4   ── FFmpeg ───► WAV ── Whisper ──► transcribed text
        │
        ▼
safe_translate()  (chunking + 4-provider fallback)
        │
        ▼
Translated text ── gTTS ──► MP3 audio
        │
        ▼
Save to user history (if logged in) + render result page
```

---

## Error Handling

- Invalid or missing uploads return a friendly error page.
- PDF parsing failures and FFmpeg/audio extraction failures are caught and reported.
- TTS is retried up to 3 times before failing gracefully.
- Translation retries per chunk and falls back across providers.
- Temporary upload files are cleaned up with retry logic (`safe_delete`) to handle file locks.
- OTPs expire after 10 minutes and are locked after 5 failed attempts.

---

## Security Notes

- Passwords are hashed with SHA-256 before storage.
- Credentials are loaded from environment variables (never hard-coded in `.env`).
- User file downloads are authorized — users can only access their own files.
- `.env`, uploads, and user files are excluded via `.gitignore`.

> For production, consider stronger password hashing (e.g. `bcrypt`/`argon2`), a real database, and HTTPS.

---

## Limitations

- JSON-file storage is simple but not ideal for concurrent/large-scale use.
- Translation relies on public Google endpoints and may be rate-limited.
- Audio output requires the target language to be supported by gTTS.
- Whisper `base` model trades accuracy for speed.

---

## Future Enhancements

- Migrate storage from JSON to SQLite/PostgreSQL.
- Add support for more input formats (DOCX, images via OCR).
- Offer additional TTS voices/engines.
- Dockerize the app for easier deployment.
- Add rate limiting and stronger authentication.

---

## License

This project is provided for educational and personal use. Add a license file (e.g. MIT) if you plan to distribute it.
