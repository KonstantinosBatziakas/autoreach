# AUTOREACH

> Your own cold outreach machine. Open source, self-hosted, AI-powered.

AutoReach finds businesses on Google Maps, scrapes their emails, writes personalised cold emails with Groq AI, and sends them via Gmail — fully automated, zero SaaS fees.

**[→ Website](https://autoreach.dev)** · **[→ Live Demo](https://app.autoreach.dev)**

---

## Deploy in 2 minutes

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/KonstantinosBatziakas/autoreach)

After deploying, open your Render URL and the setup wizard will guide you through adding your API keys.

---

## Features

- **Lead Discovery** — search Google Maps by city and business type
- **Email Scraping** — auto-finds emails from business websites
- **AI Email Generation** — Groq / Llama 3.1 writes a unique email per business (English or Greek)
- **Automated Sending** — Gmail SMTP, never emails the same lead twice
- **Follow-up Sequences** — auto follow-ups at +3, +7, +14 days, stops if they reply
- **Lead Pipeline** — Kanban board with New / Contacted / Replied / Closed stages
- **Web Dashboard** — full UI to manage everything from your browser
- **ARIA Chatbot** — built-in AI assistant for help and setup guidance
- **Import / Export** — bulk CSV import and export
- **Email Templates** — write your own template, Groq personalises per lead

---

## Self-Host (Manual)

**1. Clone**
```bash
git clone https://github.com/KonstantinosBatziakas/autoreach.git
cd autoreach
```

**2. Install dependencies**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**3. Set environment variables**

Create a `.env` file (copy from `.env.example`):
```
SECRET_KEY=your-random-32-char-secret
WEB_PASSWORD=your-dashboard-password
GROQ_API_KEY=your-groq-key
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=your-gmail-app-password
GOOGLE_MAPS_API_KEY=your-google-maps-key
BASE_URL=http://localhost:5000
```

**4. Run**
```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000)

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Random secret for JWT signing. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `WEB_PASSWORD` | Yes | Password to access the web dashboard |
| `GROQ_API_KEY` | Yes | Free at [console.groq.com](https://console.groq.com) |
| `GMAIL_USER` | Yes | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Yes | Gmail app password — [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) |
| `GOOGLE_MAPS_API_KEY` | Yes | Enable Places API at [console.cloud.google.com](https://console.cloud.google.com) |
| `BASE_URL` | Yes | Your public URL (e.g. `https://yourapp.onrender.com`) |
| `GITHUB_CLIENT_ID` | Optional | For GitHub OAuth login in the Flutter app |
| `GITHUB_CLIENT_SECRET` | Optional | For GitHub OAuth login in the Flutter app |
| `DISCORD_CLIENT_ID` | Optional | For Discord OAuth login in the Flutter app |
| `DISCORD_CLIENT_SECRET` | Optional | For Discord OAuth login in the Flutter app |
| `GOOGLE_CLIENT_ID` | Optional | For Google OAuth login in the Flutter app |
| `GOOGLE_CLIENT_SECRET` | Optional | For Google OAuth login in the Flutter app |
| `DATA_DIR` | Optional | Directory to store data files. Defaults to `.` |

---

## Getting your API keys

**Groq API key** (free)
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up → API Keys → Create API Key

**Gmail App Password**
1. Enable 2-Step Verification on your Google account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Generate a password for "Mail"

**Google Maps API key**
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → APIs & Services → Enable "Places API"
3. Credentials → Create API Key

---

## Project Structure

```
autoreach/
├── app.py               # Flask web dashboard
├── auth.py              # OAuth + JWT authentication
├── emailer.py           # AI email generation + Gmail sending
├── followup.py          # Follow-up email sequences
├── lead_finder.py       # Google Maps Places API
├── email_scraper.py     # Website email scraper
├── scheduler.py         # Daily scheduled sending
├── templates/           # Web UI HTML templates
├── autoreach_flutter/   # Flutter mobile app
├── docs/                # Landing page (autoreach.dev)
├── Dockerfile           # For Docker/Fly.io deployment
├── fly.toml             # Fly.io config
└── requirements.txt
```

---

## License

Source Available — free to use, modify, and self-host. Commercial resale prohibited. See [LICENSE](LICENSE) for full terms.
