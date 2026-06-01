# AutoReach Web Dashboard

A Flask-based web dashboard for managing your AutoReach lead generation and email outreach campaigns.

## Features

- **Dashboard**: View key statistics (total leads, emails sent, leads with emails)
- **Leads Management**: View, add, and manage your business leads
- **Find Leads**: Search for new leads using Google Maps integration
- **Email Scraping**: Automatically scrape emails from lead websites
- **Outreach Campaigns**: Run automated email outreach campaigns
- **Sent Log**: Track all sent emails with timestamps
- **Reports**: Generate comprehensive outreach reports

## Installation

Flask has already been installed in your virtual environment at `C:\autoreach\venv\`.

## Running the Dashboard

1. Activate your virtual environment:
   ```bash
   source venv/Scripts/activate
   ```

2. Run the Flask app:
   ```bash
   python app.py
   ```

3. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Project Structure

```
autoreach/
├── app.py                 # Main Flask application
├── templates/             # HTML templates
│   ├── base.html         # Base template with navigation
│   ├── index.html        # Dashboard homepage
│   ├── leads.html        # Leads listing page
│   ├── add_lead.html     # Manual lead entry form
│   ├── find_leads.html   # Google Maps search form
│   ├── sent.html         # Sent emails log
│   ├── outreach.html     # Outreach campaign page
│   └── report.html       # Statistics report
├── static/                # Static assets
│   └── style.css         # Application styles
├── businesses.csv         # Leads database
├── sent_log.csv          # Sent emails log
└── .env                  # Environment configuration
```

## API Endpoints

- `GET /` - Dashboard homepage
- `GET /leads` - View all leads
- `GET /add_lead` - Manual lead entry form
- `POST /add_lead` - Submit new lead
- `GET /find_leads` - Google Maps search form
- `POST /find_leads` - Execute lead search
- `POST /scrape_emails` - Scrape emails from lead websites
- `GET /sent` - View sent emails log
- `GET /outreach` - Outreach campaign page
- `POST /outreach` - Run outreach campaign
- `GET /report` - View outreach report
- `GET /api/stats` - JSON API for statistics

## Notes

- Make sure your `.env` file is configured with SMTP settings before running outreach campaigns
- The dashboard integrates with your existing Python modules (lead_finder, emailer, email_scraper, etc.)
- All data is stored in CSV files (businesses.csv, sent_log.csv)

## Troubleshooting

If you encounter any issues:

1. Ensure Flask is installed: `pip list | grep -i flask`
2. Check that your virtual environment is activated
3. Verify your `.env` file has the correct SMTP credentials
4. Make sure port 5000 is not in use by another application
