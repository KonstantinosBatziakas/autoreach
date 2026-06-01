# AUTOREACH

> yours for the outreach.

AI-powered cold email outreach tool. Finds businesses on Google Maps, scrapes their emails, writes personalized cold emails with Groq AI, and sends them via Gmail — all from a local web dashboard.

**[→ Project Website](https://konstantinosbatziakas.github.io/autoreach)**

---

## Features

- **Lead Discovery** — search Google Maps by city and business type
- **Email Scraping** — auto-finds emails from business websites
- **AI Email Generation** — Groq / Llama 3.1 writes a unique email per business (English or Greek)
- **Automated Sending** — Gmail SMTP, never emails the same lead twice
- **Web Dashboard** — full UI to manage everything at `localhost:5000`
- **Scheduler** — set a daily time for outreach to run automatically

## Setup

**1. Clone the repo**
```
git clone https://github.com/KonstantinosBatziakas/autoreach.git
cd autoreach
```

**2. Create a virtual environment**
```
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies**
```
pip install -r requirements.txt
```

**4. Add your API keys**

Copy `.env.example` to `.env` and fill in your keys:
```
GROQ_API_KEY=...
GMAIL_USER=...
GMAIL_APP_PASSWORD=...
GOOGLE_MAPS_API_KEY=...
```

- **Groq API key** — free at [console.groq.com](https://console.groq.com)
- **Gmail app password** — [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- **Google Maps API key** — enable Places API at [console.cloud.google.com](https://console.cloud.google.com)

**5. Run**
```
python app.py
```

Open [http://localhost:5000](http://localhost:5000)

## Project Structure

```
autoreach/
├── app.py               # Flask web dashboard
├── main.py              # CLI version
├── lead_finder.py       # Google Maps Places API
├── email_scraper.py     # Website email scraper
├── emailer.py           # AI email generation + Gmail sending
├── scheduler.py         # Daily scheduled sending
├── report_generator.py  # Outreach stats
├── templates/           # Web UI templates
├── docs/                # GitHub Pages website
├── .env.example         # API key template
└── requirements.txt
```

## License

MIT
