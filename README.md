# PocketSmart AI — Your Smart Budget & Recommendation Assistant

AI-powered budget planning for **Home Interiors**, **Party Planning**, and **Jewelry Shopping**,
built with **FastAPI**, **Jinja2**, and **Google Gemini** (with automatic mock-data fallback so
the app works fully even without an API key).

---
## 1. Features
- User registration / login (JWT stored in an httpOnly cookie)
- Three AI planners: Home Interior, Party, Jewelry (with optional outfit image upload)
- Real "shop on Amazon / Flipkart / IKEA / Swiggy / Zomato / OYO / ..." search links for every
  recommended item
- Recommendation history per user
- Dark-themed, responsive UI
- Works immediately in **mock mode** (rule-based recommendations) if no Gemini API key is set —
  switches automatically to real Gemini output once you add a key

---
## 2. VS Code Setup

### Step 1 — Open the project
1. Unzip `pocketsmart-ai.zip`
2. Open the folder in VS Code: `File > Open Folder...`
3. Install the **Python extension** (Microsoft) if you don't have it already

### Step 2 — Create a virtual environment
Open a terminal in VS Code (`` Ctrl+` ``) and run:

```bash
python -m venv venv
```

Activate it:
- **Windows (PowerShell):** `venv\Scripts\Activate.ps1`
- **Windows (cmd):** `venv\Scripts\activate.bat`
- **macOS / Linux:** `source venv/bin/activate`

In VS Code, select this environment as your interpreter: `Ctrl+Shift+P` → "Python: Select
Interpreter" → choose the one inside `venv`.

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Configure environment variables
```bash
copy .env.example .env      # Windows
cp .env.example .env        # macOS / Linux
```
Open `.env` and set:
```
GOOGLE_API_KEY=your_gemini_api_key_here     # optional — leave as-is to run in mock mode
SECRET_KEY=some_long_random_string
```
Get a free Gemini API key at **https://aistudio.google.com/app/apikey**.
If you skip this, the app still runs — it just generates rule-based ("mock") recommendations
instead of live Gemini output (you'll see a "MOCK DATA" badge on results).

### Step 5 — Run the app
```bash
uvicorn app:app --reload
```
Then open **http://127.0.0.1:8000** in your browser.

You can also just press `F5` in VS Code if you add this `launch.json` (Run > Add Configuration >
Python > FastAPI), or simply run `python app.py`.

---
## 3. Testing the app
1. Go to `http://127.0.0.1:8000` → click **Get Started** → register a new account.
2. Sign in → you'll land on the **Dashboard**.
3. Try each planner:
   - **Home Planner**: enter a budget + counts of lights/fans/furniture/tables → Generate
   - **Party Planner**: enter budget, guest count, party type → Generate
   - **Jewelry Planner**: enter budget + occasion, optionally upload an outfit photo → Get
     Recommendations
4. Click any "shop on ..." link under a recommended item — it opens a live search on that
   platform for that item.
5. Visit **History** to see everything you've generated, with full JSON details expandable.
6. Check `GET /health` (e.g. http://127.0.0.1:8000/health) to confirm whether the app is running
   in `gemini` or `mock` AI mode.

You can also test the JSON APIs directly from the interactive docs at
**http://127.0.0.1:8000/docs** (FastAPI's built-in Swagger UI) — note the planner endpoints
require you to be logged in (the cookie set by `/token` is used automatically if you log in via
the app first in the same browser).

---
## 4. Project Structure
```
pocketsmart-ai/
├── app.py              # FastAPI app: all page routes, auth routes, planner APIs
├── models.py            # Pydantic request/response models
├── auth.py               # Password hashing, JWT creation/validation, current-user dependency
├── ai_service.py         # Gemini integration + mock fallback + shopping-link builder
├── storage.py            # In-memory session & recommendation-history storage
├── requirements.txt
├── .env.example
├── static/
│   ├── styles.css        # Dark-themed UI styling
│   └── uploads/           # Uploaded outfit images land here
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── home_planner.html
    ├── party_planner.html
    ├── jewelry_planner.html
    └── history.html
```

---
## 5. Notes / Production Considerations
- **Storage is in-memory** (`auth.py` / `storage.py`) — all users, sessions and history are lost
  on server restart. For production, replace `users_db`, `active_sessions`, and
  `user_recommendations` with a real database (SQLite/PostgreSQL + SQLAlchemy is a natural
  upgrade).
- **CORS** is currently wide open (`allow_origins=["*"]`) for easy local testing — restrict this
  before deploying publicly.
- **SECRET_KEY** must be a strong random value in any real deployment (never reuse the example
  value).
- The Gemini model used is `gemini-1.5-flash` — swap the model name in `ai_service.py` if you
  want a different Gemini model.
