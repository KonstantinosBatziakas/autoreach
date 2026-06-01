from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import csv
import os
from datetime import datetime
from lead_finder import find_businesses
from emailer import run_outreach
from email_scraper import scrape_emails
from report_generator import generate_report

app = Flask(__name__)
app.secret_key = os.urandom(24)

def read_businesses():
    businesses = []
    if os.path.exists('businesses.csv'):
        with open('businesses.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                businesses.append(row)
    return businesses

def read_sent_log():
    sent_emails = []
    if os.path.exists('sent_log.csv'):
        with open('sent_log.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sent_emails.append(row)
    return sent_emails

def count_stats():
    businesses = read_businesses()
    sent_emails = read_sent_log()
    return {
        'total_leads': len(businesses),
        'emails_sent': len(sent_emails),
        'leads_with_emails': sum(1 for b in businesses if b.get('email'))
    }

@app.route('/')
def index():
    stats = count_stats()
    return render_template('index.html', stats=stats)

@app.route('/leads')
def leads():
    businesses = read_businesses()
    return render_template('leads.html', businesses=businesses)

@app.route('/add_lead', methods=['GET', 'POST'])
def add_lead():
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        website = request.form.get('website')
        email = request.form.get('email')

        row = {
            'name': name,
            'address': address,
            'phone': phone,
            'website': website,
            'email': email
        }

        file_exists = os.path.exists('businesses.csv')
        with open('businesses.csv', 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['name', 'address', 'phone', 'website', 'email'])
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        flash(f'Successfully added {name} to leads!', 'success')
        return redirect(url_for('leads'))

    return render_template('add_lead.html')

@app.route('/find_leads', methods=['GET', 'POST'])
def find_leads():
    if request.method == 'POST':
        city = request.form.get('city')
        business_type = request.form.get('business_type')

        try:
            find_businesses(city, business_type)
            flash(f'Successfully searched for {business_type} in {city}!', 'success')
        except Exception as e:
            flash(f'Error finding leads: {str(e)}', 'error')

        return redirect(url_for('leads'))

    return render_template('find_leads.html')

@app.route('/scrape_emails', methods=['POST'])
def scrape_emails_route():
    try:
        scrape_emails()
        flash('Email scraping completed!', 'success')
    except Exception as e:
        flash(f'Error scraping emails: {str(e)}', 'error')

    return redirect(url_for('leads'))

@app.route('/sent')
def sent():
    sent_emails = read_sent_log()
    return render_template('sent.html', sent_emails=sent_emails)

@app.route('/outreach', methods=['GET', 'POST'])
def outreach():
    if request.method == 'POST':
        try:
            run_outreach(auto_send=True)
            flash('Email outreach completed!', 'success')
        except Exception as e:
            flash(f'Error running outreach: {str(e)}', 'error')

        return redirect(url_for('sent'))

    return render_template('outreach.html')

@app.route('/report')
def report():
    try:
        sent_emails = read_sent_log()
        if not sent_emails:
            flash('No sent emails yet!', 'warning')
            return redirect(url_for('index'))

        total_sent = len(sent_emails)
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_count = sum(1 for row in sent_emails if row.get('date_sent', '').startswith(today_str))

        report_data = {
            'total_sent': total_sent,
            'today_count': today_count,
            'emails': sent_emails
        }

        return render_template('report.html', report=report_data)
    except Exception as e:
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/stats')
def api_stats():
    return jsonify(count_stats())

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
