from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_cors import CORS
import csv
import html as _html
import io
import json
import os
import time
import threading
from datetime import datetime
from functools import wraps
from lead_finder import find_businesses
from email_scraper import scrape_emails
from auth import auth_bp
from followup import run_followups, get_followup_stats
from db import get_db, init_db
from moderation.policy import AUP_VERSION, POLICY_EN, POLICY_EL
from moderation.service import Decision, enqueue, moderate_and_queue, utc_now
from moderation.delivery import DeliveryBlocked, DeliveryQueued, send_moderated, user_message
from moderation.queue import retry_queued

app = Flask(__name__)
_secret_key = os.getenv('SECRET_KEY')
if not _secret_key:
    import warnings
    warnings.warn(
        'SECRET_KEY env var is not set — using an insecure fallback. '
        'Set SECRET_KEY in Render → Environment to keep sessions stable across restarts.',
        stacklevel=1,
    )
    _secret_key = 'autoreach-insecure-dev-key-change-me'
app.secret_key = _secret_key
CORS(app, supports_credentials=False)

# Guard against concurrent scrape runs
_scrape_lock = threading.Lock()
_scrape_running = False

app.register_blueprint(auth_bp)

# Ensure all DB tables exist on startup
init_db()

# ── Web UI auth ───────────────────────────────────────────────
WEB_PASSWORD = os.getenv('WEB_PASSWORD', '')

def web_login_required(f):
    """
    For browser routes: checks session cookie.
    For API routes (XHR / Flutter): also accepts a valid Bearer JWT.
    Returns JSON 401 for API callers, redirect for browser callers.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. Bearer JWT — used by Flutter and any API client
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            from auth import verify_jwt
            payload = verify_jwt(auth_header[7:])
            if payload is not None:
                request.user = payload
                if not _aup_is_accepted(int(payload.get('sub') or 0)):
                    if request.path.startswith('/api/') or request.is_json:
                        return jsonify({'error': 'Accept the AutoReach acceptable-use policy before continuing.', 'code': 'aup_required', 'policy_url': url_for('acceptable_use')}), 428
                    return redirect(url_for('acceptable_use'))
                return f(*args, **kwargs)
            # Invalid/expired token → JSON error
            return jsonify({'error': 'Invalid or expired token'}), 401

        # 2. Session cookie — used by the web dashboard
        if WEB_PASSWORD and not session.get('web_authed'):
            # API-style requests get JSON, not a redirect
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Not authenticated'}), 401
            return redirect(url_for('web_login', next=request.path))

        if not WEB_PASSWORD and not app.testing and os.getenv('APP_ENV', '').lower() != 'development':
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication is not configured. Set WEB_PASSWORD or use a valid account token.'}), 503
            return redirect(url_for('setup'))

        request.user = {'sub': int(os.getenv('WEB_MODERATION_USER_ID', '0')), 'web_session': True}
        if not _aup_is_accepted(int(request.user['sub'])):
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'error': 'Accept the AutoReach acceptable-use policy before continuing.', 'code': 'aup_required', 'policy_url': url_for('acceptable_use')}), 428
            return redirect(url_for('acceptable_use'))

        return f(*args, **kwargs)
    return decorated


def _aup_is_accepted(user_id):
    db = get_db()
    try:
        if user_id == 0:
            row = db.execute("SELECT value FROM settings WHERE key = 'accepted_aup_version'").fetchone()
            accepted = row['value'] if row else None
        else:
            row = db.execute('SELECT accepted_aup_version FROM users WHERE id = ?', (user_id,)).fetchone()
            accepted = row['accepted_aup_version'] if row else None
        return accepted == AUP_VERSION
    finally:
        db.close()


def _current_user_id():
    return int((getattr(request, 'user', {}) or {}).get('sub') or 0)


def _is_moderation_admin(user_id):
    allowed_ids = {value.strip() for value in os.getenv('MODERATION_ADMIN_USER_IDS', '').split(',') if value.strip()}
    if str(user_id) in allowed_ids:
        return True
    if user_id == 0 and os.getenv('MODERATION_ADMIN_WEB_ENABLED', '').lower() == 'true':
        return bool(WEB_PASSWORD and session.get('web_authed'))
    db = get_db()
    try:
        row = db.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()
        return bool(row and row['role'] == 'admin')
    finally:
        db.close()


def moderation_admin_required(f):
    @wraps(f)
    @web_login_required
    def decorated(*args, **kwargs):
        if not _is_moderation_admin(_current_user_id()):
            return jsonify({'error': 'Administrator access required.'}), 403
        return f(*args, **kwargs)
    return decorated


def _save_aup_acceptance(user_id):
    db = get_db()
    accepted_at = utc_now()
    if user_id == 0:
        for key, value in (('accepted_aup_version', AUP_VERSION), ('accepted_aup_at', accepted_at)):
            db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    else:
        db.execute('UPDATE users SET accepted_aup_version = ?, accepted_aup_at = ? WHERE id = ?', (AUP_VERSION, accepted_at, user_id))
    db.commit()
    db.close()


@app.route('/acceptable-use')
def acceptable_use():
    return render_template('acceptable_use.html', version=AUP_VERSION, policy_en=POLICY_EN, policy_el=POLICY_EL)


@app.route('/accept-use', methods=['POST'])
def accept_use():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        from auth import verify_jwt
        payload = verify_jwt(auth_header[7:])
        if payload is None:
            return jsonify({'error': 'Invalid or expired token'}), 401
        _save_aup_acceptance(int(payload.get('sub') or 0))
        return jsonify({'ok': True, 'version': AUP_VERSION})
    if WEB_PASSWORD and not session.get('web_authed'):
        return redirect(url_for('web_login', next=url_for('acceptable_use')))
    if request.form.get('accept') != 'yes':
        flash('Please accept the acceptable-use policy to continue.', 'error')
        return redirect(url_for('acceptable_use'))
    _save_aup_acceptance(int(os.getenv('WEB_MODERATION_USER_ID', '0')))
    return redirect(request.args.get('next') or url_for('index'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """First-launch setup wizard — only accessible when WEB_PASSWORD is not set."""
    if WEB_PASSWORD:
        return redirect(url_for('index'))
    if request.method == 'POST':
        web_password    = request.form.get('web_password', '').strip()
        resend_api_key  = request.form.get('resend_api_key', '').strip()
        from_email      = request.form.get('from_email', '').strip()
        groq_key        = request.form.get('groq_key', '').strip()
        google_maps_key = request.form.get('google_maps_key', '').strip()

        if not web_password:
            flash('Dashboard password is required.', 'error')
            return render_template('setup.html')

        # Write a .env file with the provided values
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        lines = [
            f'WEB_PASSWORD={web_password}',
            f'SECRET_KEY={os.urandom(32).hex()}',
            f'RESEND_API_KEY={resend_api_key}',
            f'FROM_EMAIL={from_email or "onboarding@resend.dev"}',
            f'GROQ_API_KEY={groq_key}',
            f'GOOGLE_MAPS_API_KEY={google_maps_key}',
            f'BASE_URL={request.host_url.rstrip("/")}',
        ]
        with open(env_path, 'w') as f:
            f.write('\n'.join(lines) + '\n')

        flash('Setup complete! Please restart the server for changes to take effect.', 'success')
        return render_template('setup.html')

    return render_template('setup.html')

@app.route('/web-login', methods=['GET', 'POST'])
def web_login():
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD:
            session['web_authed'] = True
            if not _aup_is_accepted(int(os.getenv('WEB_MODERATION_USER_ID', '0'))):
                return redirect(url_for('acceptable_use'))
            return redirect(request.args.get('next') or url_for('index'))
        flash('Incorrect password.', 'error')
    return render_template('web_login.html')

@app.route('/web-logout')
def web_logout():
    session.pop('web_authed', None)
    return redirect(url_for('web_login'))

PIPELINE_STAGES = ['New', 'Contacted', 'Replied', 'Closed']
STAGE_COLORS = {
    'New':       '#6a9090',
    'Contacted': '#4ecdc4',
    'Replied':   '#e0b84a',
    'Closed':    '#7dd87d',
}

# ── DB-backed data helpers ────────────────────────────────────────────────────

def read_businesses():
    db = get_db()
    rows = db.execute('SELECT * FROM businesses ORDER BY id').fetchall()
    db.close()
    result = []
    for row in rows:
        d = dict(row)
        if not d.get('stage'):
            d['stage'] = 'New'
        result.append(d)
    return result

def write_businesses(businesses):
    """Full-replace: delete all rows and re-insert (used for bulk updates)."""
    db = get_db()
    db.execute('DELETE FROM businesses')
    for b in businesses:
        db.execute(
            'INSERT INTO businesses (name, address, phone, website, email, stage, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (
                b.get('name', ''),
                b.get('address', ''),
                b.get('phone', ''),
                b.get('website', ''),
                b.get('email', ''),
                b.get('stage', 'New') or 'New',
                b.get('notes', ''),
            )
        )
    db.commit()
    db.close()

def read_sent_log():
    db = get_db()
    rows = db.execute('SELECT * FROM sent_log ORDER BY id').fetchall()
    db.close()
    return [dict(row) for row in rows]

def count_stats():
    db = get_db()
    def _count(sql):
        row = db.execute(sql).fetchone()
        if row is None:
            return 0
        try:
            return int(row[0])
        except Exception:
            v = list(row.values())[0] if hasattr(row, 'values') else 0
            return int(v) if v is not None else 0
    total_leads      = _count('SELECT COUNT(*) AS n FROM businesses')
    emails_sent      = _count('SELECT COUNT(*) AS n FROM sent_log')
    leads_with_email = _count("SELECT COUNT(*) AS n FROM businesses WHERE email != ''")
    replied_count    = _count("SELECT COUNT(*) AS n FROM businesses WHERE stage = 'Replied'")
    followups_sent   = _count('SELECT COUNT(*) AS n FROM followup_log')
    db.close()
    return {
        'total_leads': total_leads,
        'emails_sent': emails_sent,
        'leads_with_emails': leads_with_email,
        'replied': replied_count,
        'followups_sent': followups_sent,
    }

@app.route('/')
@web_login_required
def index():
    if not WEB_PASSWORD:
        return redirect(url_for('setup'))
    stats = count_stats()
    return render_template('index.html', stats=stats)

@app.route('/leads')
@web_login_required
def leads():
    businesses = read_businesses()
    return render_template('leads.html', businesses=businesses,
                           stages=PIPELINE_STAGES, stage_colors=STAGE_COLORS)

@app.route('/pipeline')
@web_login_required
def pipeline():
    businesses = read_businesses()
    grouped = {s: [b for b in businesses if b.get('stage', 'New') == s] for s in PIPELINE_STAGES}
    return render_template('pipeline.html', grouped=grouped,
                           stages=PIPELINE_STAGES, stage_colors=STAGE_COLORS,
                           total=len(businesses))

@app.route('/update_stage', methods=['POST'])
@web_login_required
def update_stage():
    name  = request.form.get('name', '').strip()
    stage = request.form.get('stage', 'New').strip()
    if stage not in PIPELINE_STAGES:
        return jsonify({'error': 'Invalid stage'}), 400
    db = get_db()
    db.execute("UPDATE businesses SET stage = ? WHERE name = ?", (stage, name))
    db.commit()
    db.close()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'stage': stage})
    return redirect(request.referrer or url_for('leads'))

@app.route('/add_lead', methods=['GET', 'POST'])
@web_login_required
def add_lead():
    if request.method == 'POST':
        name    = (request.form.get('name') or '').strip()
        address = request.form.get('address', '').strip()
        phone   = request.form.get('phone', '').strip()
        website = request.form.get('website', '').strip()
        email   = request.form.get('email', '').strip()
        notes   = request.form.get('notes', '').strip()

        if not name:
            flash('Business name is required.', 'error')
            return render_template('add_lead.html')

        db = get_db()
        db.execute(
            'INSERT INTO businesses (name, address, phone, website, email, stage, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, address, phone, website, email, 'New', notes)
        )
        db.commit()
        db.close()
        flash(f'Successfully added {name} to leads!', 'success')
        return redirect(url_for('leads'))

    return render_template('add_lead.html')

DEFAULT_TEMPLATE = """Hi there,

I came across {name} and wanted to reach out about your online presence.

We help businesses like yours attract more customers through professional web design and digital marketing. I'd love to show you what we could do for {name}.

Would you be open to a quick 15-minute call this week?

Best regards,
{sender_name}"""

def get_email_template():
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key = 'email_template'").fetchone()
    db.close()
    if row:
        return row[0] or DEFAULT_TEMPLATE
    return DEFAULT_TEMPLATE

def save_email_template(content):
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('email_template', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (content,)
    )
    db.commit()
    db.close()

@app.route('/email_templates', methods=['GET', 'POST'])
@web_login_required
def email_templates():
    if request.method == 'POST':
        content = request.form.get('template', '').strip()
        if content:
            moderation_db = get_db()
            decision, queue_id = moderate_and_queue(
                content, _current_user_id(), 'save', 'email_template', moderation_db,
                payload={'content': content, 'content_type': 'email_template'},
            )
            moderation_db.close()
            if decision.verdict == 'allow':
                save_email_template(content)
                flash('Template saved after moderation.', 'success')
            elif decision.verdict == 'block':
                flash(f"Template not saved: {user_message(decision)}", 'error')
            else:
                flash(f"Template held for moderation review ({queue_id}). See the moderation queue.", 'error')
        return redirect(url_for('email_templates'))
    template = get_email_template()
    return render_template('email_templates.html', template=template)

@app.route('/export_leads')
@web_login_required
def export_leads():
    businesses = read_businesses()
    fieldnames = ['name', 'address', 'phone', 'website', 'email', 'stage', 'notes']
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for b in businesses:
        writer.writerow(b)
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'autoreach_leads_{datetime.now().strftime("%Y%m%d")}.csv'
    )

@app.route('/import_leads', methods=['GET', 'POST'])
@web_login_required
def import_leads():
    if request.method == 'POST':
        f = request.files.get('csv_file')
        if not f or not f.filename.endswith('.csv'):
            flash('Please upload a valid CSV file.', 'error')
            return redirect(url_for('import_leads'))
        try:
            content = f.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(content))
            imported = list(reader)
            db = get_db()
            existing_names = {
                row[0].lower()
                for row in db.execute('SELECT name FROM businesses').fetchall()
            }
            added = 0
            for row in imported:
                name = (row.get('name') or '').strip()
                if not name or name.lower() in existing_names:
                    continue
                db.execute(
                    'INSERT INTO businesses (name, address, phone, website, email, stage, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (
                        name,
                        row.get('address', '').strip(),
                        row.get('phone', '').strip(),
                        row.get('website', '').strip(),
                        row.get('email', '').strip(),
                        row.get('stage', 'New').strip() or 'New',
                        row.get('notes', '').strip(),
                    )
                )
                existing_names.add(name.lower())
                added += 1
            db.commit()
            db.close()
            flash(f'Imported {added} new leads ({len(imported) - added} skipped as duplicates).', 'success')
            return redirect(url_for('leads'))
        except Exception as e:
            flash(f'Import failed: {str(e)}', 'error')
    return render_template('import_leads.html')

@app.route('/delete_lead', methods=['POST'])
@web_login_required
def delete_lead():
    name = request.form.get('name', '').strip()
    db = get_db()
    db.execute('DELETE FROM businesses WHERE name = ?', (name,))
    db.commit()
    db.close()
    flash(f'Lead "{name}" deleted.', 'success')
    return redirect(url_for('leads'))

@app.route('/update_notes', methods=['POST'])
@web_login_required
def update_notes():
    name  = request.form.get('name', '').strip()
    notes = request.form.get('notes', '').strip()
    db = get_db()
    db.execute('UPDATE businesses SET notes = ? WHERE name = ?', (notes, name))
    db.commit()
    db.close()
    return jsonify({'ok': True})

@app.route('/find_leads', methods=['GET', 'POST'])
@web_login_required
def find_leads():
    if request.method == 'POST':
        city = (request.form.get('city') or '').strip()[:100]
        business_type = (request.form.get('business_type') or '').strip()[:100]

        if not city or not business_type:
            flash('City and business type are required.', 'error')
            return redirect(url_for('find_leads'))

        if not os.getenv('GOOGLE_MAPS_API_KEY'):
            flash('Google Maps API key not set. Add GOOGLE_MAPS_API_KEY in Render → Environment.', 'error')
            return redirect(url_for('find_leads'))
        try:
            results = find_businesses(city, business_type)
            flash(f'Found {len(results)} businesses for "{business_type}" in {city}.', 'success')
        except Exception as e:
            flash(f'Lead finder error: {str(e)}', 'error')

        return redirect(url_for('leads'))

    return render_template('find_leads.html')

@app.route('/scrape_emails', methods=['POST'])
@web_login_required
def scrape_emails_route():
    global _scrape_running
    with _scrape_lock:
        if _scrape_running:
            flash('Scraping is already running — please wait.', 'warning')
            return redirect(url_for('leads'))
        _scrape_running = True
    try:
        scrape_emails()
        flash('Email scraping complete — check leads for newly found emails.', 'success')
    except Exception as e:
        import traceback
        flash(f'Scraping error: {str(e)}', 'error')
        app.logger.error(traceback.format_exc())
    finally:
        _scrape_running = False

    return redirect(url_for('leads'))

@app.route('/sent')
@web_login_required
def sent():
    sent_emails = read_sent_log()
    return render_template('sent.html', sent_emails=sent_emails)

@app.route('/delete_sent', methods=['POST'])
@web_login_required
def delete_sent():
    """Remove a lead from the sent log so they can be re-contacted."""
    entry_id = request.form.get('id', '').strip()
    if entry_id:
        db = get_db()
        db.execute('DELETE FROM sent_log WHERE id = ?', (entry_id,))
        db.commit()
        db.close()
    flash('Lead removed from sent log — they can be contacted again.', 'success')
    return redirect(url_for('sent'))

@app.route('/outreach', methods=['GET'])
@web_login_required
def outreach():
    return render_template('outreach.html')

@app.route('/report')
@web_login_required
def report():
    try:
        sent_emails = read_sent_log()
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_count = sum(1 for row in sent_emails if row.get('date_sent', '').startswith(today_str))
        stats = count_stats()

        report_data = {
            'total_sent': len(sent_emails),
            'today_count': today_count,
            'followups_sent': stats.get('followups_sent', 0),
            'replied': stats.get('replied', 0),
            'emails': sent_emails,
        } if sent_emails else None

        return render_template('report.html', report=report_data)
    except Exception as e:
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/stats')
@web_login_required
def api_stats():
    return jsonify(count_stats())

@app.route('/api/add-lead', methods=['POST'])
@web_login_required
def api_add_lead():
    """Add a single lead via JSON (used by the Flutter app)."""
    try:
        data    = request.get_json(force=True)
        name    = (data.get('name') or '').strip()
        address = (data.get('address') or '').strip()
        phone   = (data.get('phone') or '').strip()
        website = (data.get('website') or '').strip()
        email   = (data.get('email') or '').strip()
        notes   = (data.get('notes') or '').strip()
        if not name:
            return jsonify({'error': 'name is required'}), 400
        db = get_db()
        # Skip if already exists
        existing = db.execute('SELECT id FROM businesses WHERE name = ?', (name,)).fetchone()
        if existing:
            db.close()
            return jsonify({'ok': True, 'skipped': True})
        db.execute(
            'INSERT INTO businesses (name, address, phone, website, email, stage, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, address, phone, website, email, 'New', notes)
        )
        db.commit()
        db.close()
        return jsonify({'ok': True, 'skipped': False})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scrape', methods=['POST'])
@web_login_required
def api_scrape():
    """Trigger email scraping in a background thread (used by the Flutter app)."""
    global _scrape_running
    with _scrape_lock:
        if _scrape_running:
            return jsonify({'ok': False, 'message': 'Scraping already in progress.'}), 409
        _scrape_running = True

    def _run():
        global _scrape_running
        try:
            scrape_emails()
        finally:
            _scrape_running = False

    try:
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return jsonify({'ok': True, 'message': 'Scraping started in background.'})
    except Exception as e:
        _scrape_running = False
        return jsonify({'error': str(e)}), 500

@app.route('/api/all-leads')
@web_login_required
def api_all_leads():
    """Return every lead in the database (for the Flutter leads screen)."""
    try:
        db = get_db()
        rows = db.execute(
            "SELECT name, address, phone, website, email, stage, notes FROM businesses ORDER BY id"
        ).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/sent')
@web_login_required
def api_sent():
    """Return the sent email log (for the Flutter sent screen)."""
    try:
        db = get_db()
        rows = db.execute(
            "SELECT id, business_name, email, subject, date_sent FROM sent_log ORDER BY id DESC"
        ).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/update-stage', methods=['POST'])
@web_login_required
def api_update_stage():
    """Update a lead's pipeline stage."""
    try:
        data  = request.get_json(force=True)
        name  = data.get('name', '').strip()
        stage = data.get('stage', '').strip()
        if not name or not stage:
            return jsonify({'error': 'name and stage required'}), 400
        db = get_db()
        db.execute("UPDATE businesses SET stage = ? WHERE name = ?", (stage, name))
        db.commit()
        db.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── ARIA Support Bot ──────────────────────────────────────────
@app.route('/aria')
@web_login_required
def aria():
    return render_template('aria.html')

@app.route('/aria/chat', methods=['POST'])
def aria_chat():
    # App clients now call their selected provider directly with their own API key.
    # Keep this response for older app versions without exposing the hosted key.
    return jsonify({
        'error': 'ARIA now uses your selected provider directly. Update the app and add your provider details in Settings.'
    }), 410

# ── Client-side outreach API ──────────────────────────────────
# Groq is called directly by the browser/Flutter app (avoids Render IP blocks).
# These endpoints just handle the SMTP send + DB log.

@app.route('/unsubscribe')
def unsubscribe():
    """Public unsubscribe link — no login required. Called from email footer."""
    email = (request.args.get('email') or '').strip().lower()
    if not email:
        return render_template('unsubscribe.html', status='invalid', email='')
    try:
        db = get_db()
        db.execute(
            "UPDATE businesses SET unsubscribed = 1, stage = 'Unsubscribed' WHERE LOWER(email) = ?",
            (email,)
        )
        db.commit()
        db.close()
        return render_template('unsubscribe.html', status='ok', email=email)
    except Exception as e:
        return render_template('unsubscribe.html', status='error', email=email)


@app.route('/api/leads')
@web_login_required
def api_leads():
    """Return all leads that have an email and haven't been contacted yet."""
    try:
        db = get_db()
        sent_rows = db.execute('SELECT email FROM sent_log').fetchall()
        sent_emails = {
            (row['email'] or '').lower()
            for row in sent_rows
            if row.get('email')
        }
        rows = db.execute(
            "SELECT name, address, phone, website, email, stage, notes FROM businesses ORDER BY id"
        ).fetchall()
        db.close()
        leads = [
            dict(row) for row in rows
            if row.get('email')
            and row['email'].lower() not in sent_emails
            and not row.get('unsubscribed')
        ]
        return jsonify(leads)
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

def _build_email_html(body: str, template_id: str, sender_name: str, to_email: str = '') -> str:
    """Build the HTML email wrapper for the given template."""
    # Escape user-supplied content so it can safely be placed inside an f-string
    # that also contains CSS braces — we replace after building the template.
    body_html   = _html.escape(body).replace('\n', '<br>')
    sender_safe = _html.escape(sender_name)
    year = datetime.now().year
    import urllib.parse
    _base_url = os.getenv('BASE_URL', 'https://app.autoreach.dev').rstrip('/')
    unsub_url = f"{_base_url}/unsubscribe?email={urllib.parse.quote(to_email)}"
    unsub_link = f'<a href="{unsub_url}" style="color:#aaa;text-decoration:underline;font-size:11px;">Unsubscribe</a>'

    if template_id == 'clean':
        return f"""<!DOCTYPE html><html><head><style>
        body{{margin:0;padding:0;background:#ffffff;font-family:'Helvetica Neue',Arial,sans-serif;}}
        .wrapper{{max-width:580px;margin:40px auto;background:#fff;border:1px solid #e8e8e8;border-radius:8px;overflow:hidden;}}
        .header{{padding:32px 40px 24px;border-bottom:3px solid #3B82F6;}}
        .header h1{{color:#1a1a1a;margin:0;font-size:22px;font-weight:700;letter-spacing:1px;}}
        .header p{{color:#6B7280;margin:4px 0 0;font-size:13px;}}
        .body{{padding:36px 40px;color:#374151;font-size:15px;line-height:1.8;}}
        .footer{{padding:20px 40px;background:#F9FAFB;color:#9CA3AF;font-size:12px;border-top:1px solid #E5E7EB;}}
        </style></head><body><div class='wrapper'>
        <div class='header'><h1>AutoReach</h1><p>Digital Presence Services</p></div>
        <div class='body'><p>{body_html}</p></div>
        <div class='footer'>&copy; {year} {sender_safe}. All rights reserved. &nbsp;|&nbsp; {unsub_link}</div>
        </div></body></html>"""

    elif template_id == 'purple':
        return f"""<!DOCTYPE html><html><head><style>
        body{{margin:0;padding:0;background:#F5F3FF;font-family:'Helvetica Neue',Arial,sans-serif;}}
        .wrapper{{max-width:580px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(109,99,255,0.10);}}
        .header{{background:linear-gradient(135deg,#6C63FF 0%,#9B59B6 100%);padding:36px 40px;}}
        .header h1{{color:#fff;margin:0;font-size:24px;font-weight:800;letter-spacing:2px;}}
        .header p{{color:rgba(255,255,255,0.75);margin:6px 0 0;font-size:13px;}}
        .body{{padding:40px;color:#2D2D2D;font-size:15px;line-height:1.8;}}
        .footer{{padding:20px 40px;border-top:1px solid #EDE9FE;color:#A78BFA;font-size:12px;}}
        </style></head><body><div class='wrapper'>
        <div class='header'><h1>AUTOREACH</h1><p>Digital Presence Services</p></div>
        <div class='body'><p>{body_html}</p></div>
        <div class='footer'>&copy; {year} {sender_safe}. All rights reserved. &nbsp;|&nbsp; {unsub_link}</div>
        </div></body></html>"""

    elif template_id == 'warm':
        return f"""<!DOCTYPE html><html><head><style>
        body{{margin:0;padding:0;background:#FFF7ED;font-family:Georgia,serif;}}
        .wrapper{{max-width:580px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #FED7AA;}}
        .header{{background:linear-gradient(135deg,#F97316 0%,#EF4444 100%);padding:32px 40px;}}
        .header h1{{color:#fff;margin:0;font-size:24px;font-weight:700;letter-spacing:1px;}}
        .header p{{color:rgba(255,255,255,0.8);margin:5px 0 0;font-size:13px;}}
        .body{{padding:40px;color:#431407;font-size:15px;line-height:1.9;}}
        .footer{{padding:20px 40px;border-top:1px solid #FED7AA;color:#FB923C;font-size:12px;background:#FFF7ED;}}
        </style></head><body><div class='wrapper'>
        <div class='header'><h1>AUTOREACH</h1><p>Digital Presence Services</p></div>
        <div class='body'><p>{body_html}</p></div>
        <div class='footer'>&copy; {year} {sender_safe}. All rights reserved. &nbsp;|&nbsp; {unsub_link}</div>
        </div></body></html>"""

    elif template_id == 'plain':
        return f"""<!DOCTYPE html><html><head><style>
        body{{margin:0;padding:0;background:#ffffff;font-family:Arial,sans-serif;}}
        .wrapper{{max-width:580px;margin:40px auto;padding:0 20px;}}
        .body{{color:#222;font-size:15px;line-height:1.8;}}
        .footer{{margin-top:32px;padding-top:16px;border-top:1px solid #eee;color:#aaa;font-size:12px;}}
        </style></head><body><div class='wrapper'>
        <div class='body'><p>{body_html}</p></div>
        <div class='footer'>{sender_safe} &nbsp;|&nbsp; {unsub_link}</div>
        </div></body></html>"""

    else:  # classic (default)
        return f"""<!DOCTYPE html><html><head><style>
        body{{margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;}}
        .wrapper{{max-width:600px;margin:40px auto;background:#fff;border-radius:10px;overflow:hidden;}}
        .header{{background:#000;padding:30px 40px;}}
        .header h1{{color:#fff;margin:0;font-size:24px;letter-spacing:2px;}}
        .header p{{color:#aaa;margin:5px 0 0;font-size:13px;}}
        .body{{padding:40px;color:#333;font-size:15px;line-height:1.7;}}
        .footer{{padding:20px 40px;border-top:1px solid #eee;color:#aaa;font-size:12px;}}
        </style></head><body><div class='wrapper'>
        <div class='header'><h1>AUTOREACH</h1><p>Digital Presence Services</p></div>
        <div class='body'><p>{body_html}</p></div>
        <div class='footer'>&copy; {year} {sender_safe}. All rights reserved. &nbsp;|&nbsp; {unsub_link}</div>
        </div></body></html>"""


@app.route('/api/send-email', methods=['POST'])
@web_login_required
def api_send_email():
    """
    Receive a ready-to-send email from the client and deliver it via Resend HTTP API.
    Body JSON: {business_name, email, subject, body, resend_api_key, from_email}
    Groq generation and all credentials are handled client-side.
    Resend is used because Render free tier blocks outbound SMTP.
    """
    data = request.get_json(silent=True) or {}
    business_name  = (data.get('business_name') or '').strip()
    to_email       = (data.get('email') or '').strip()
    subject        = (data.get('subject') or '').strip()
    body           = (data.get('body') or '').strip()
    resend_api_key = (data.get('resend_api_key') or '').strip()
    from_email     = (data.get('from_email') or 'onboarding@resend.dev').strip()
    template_id    = (data.get('template_id') or 'classic').strip()
    sender_name    = (data.get('sender_name') or 'AutoReach Team').strip()

    if not resend_api_key:
        return jsonify({'error': 'Resend API key not provided. Get a free key at resend.com.'}), 400
    if not to_email or not subject or not body:
        return jsonify({'error': 'email, subject, and body are required'}), 400

    html = _build_email_html(body, template_id, sender_name, to_email)
    delivery_payload = {
        'business_name': business_name, 'email': to_email, 'subject': subject,
        'body': body, 'html': html, 'resend_api_key': resend_api_key,
        'from_email': from_email, 'template_id': template_id, 'sender_name': sender_name,
    }
    moderation_db = get_db()
    try:
        send_moderated(delivery_payload, _current_user_id(), moderation_db)
    except DeliveryBlocked as exc:
        moderation_db.close()
        return jsonify({'error': str(exc), 'category': list(exc.decision.categories), 'policy_url': url_for('acceptable_use')}), 422
    except DeliveryQueued as exc:
        moderation_db.close()
        return jsonify({'status': 'queued', 'queue_id': exc.queue_id, 'error': str(exc), 'policy_url': url_for('acceptable_use')}), 202
    except Exception:
        moderation_db.close()
        app.logger.exception('Resend delivery failed')
        return jsonify({'error': 'Email delivery failed. Please try again.'}), 502

    # Log to DB
    try:
        moderation_db.execute(
            'INSERT INTO sent_log (business_name, email, date_sent, subject, body) VALUES (?, ?, ?, ?, ?)',
            (business_name, to_email, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), subject, body)
        )
        moderation_db.commit()
    except Exception as e:
        app.logger.exception('Email sent but sent_log write failed')
        return jsonify({'ok': True, 'warning': 'Email sent, but the local send log could not be updated.'}), 200
    finally:
        moderation_db.close()

    return jsonify({'ok': True})


@app.route('/api/moderation/check', methods=['POST'])
@web_login_required
def api_moderation_check():
    data = request.get_json(silent=True) or {}
    content = data.get('content') or ''
    checkpoint = data.get('checkpoint')
    content_type = data.get('content_type') or 'email'
    if not isinstance(content, str) or not content.strip():
        return jsonify({'error': 'content is required'}), 400
    if len(content) > 20000:
        return jsonify({'error': 'content is too long to moderate'}), 413
    if checkpoint not in {'save', 'generate'}:
        return jsonify({'error': 'checkpoint must be save or generate'}), 400
    if content_type not in {'email', 'email_template', 'aria_prompt', 'campaign_instructions'}:
        return jsonify({'error': 'unsupported content_type'}), 400

    payload = data.get('payload') if isinstance(data.get('payload'), dict) else {'content': content}
    moderation_db = get_db()
    decision, queue_id = moderate_and_queue(
        content, _current_user_id(), checkpoint, content_type, moderation_db, payload=payload,
    )
    moderation_db.close()
    if decision.verdict == 'block':
        return jsonify({'error': user_message(decision), 'category': list(decision.categories), 'policy_url': url_for('acceptable_use')}), 422
    if decision.verdict == 'review':
        return jsonify({'status': 'queued', 'queue_id': queue_id, 'error': decision.reason, 'policy_url': url_for('acceptable_use')}), 202
    return jsonify({'status': 'allow', 'categories': list(decision.categories)})


@app.route('/moderation-queue')
@web_login_required
def moderation_queue_page():
    return render_template('moderation_queue.html')


@app.route('/api/moderation/queue', methods=['GET'])
@web_login_required
def api_moderation_queue():
    db = get_db()
    rows = db.execute(
        "SELECT id, checkpoint, content_type, payload_enc, status, categories, attempts, created_at "
        "FROM moderation_queue WHERE user_id = ? AND status IN ('retry','needs_review') ORDER BY created_at DESC LIMIT 100",
        (_current_user_id(),),
    ).fetchall()
    db.close()
    from moderation.service import decrypt_payload
    items = []
    for row in rows:
        try:
            payload = decrypt_payload(row['payload_enc'])
        except Exception:
            continue
        # Never return stored delivery or moderation credentials to the browser.
        for secret_key in ('resend_api_key', 'moderation_api_key', 'groq_api_key'):
            payload.pop(secret_key, None)
        items.append({
            'id': row['id'], 'checkpoint': row['checkpoint'], 'content_type': row['content_type'],
            'status': row['status'], 'categories': json.loads(row['categories'] or '[]'),
            'attempts': row['attempts'], 'created_at': row['created_at'], 'payload': payload,
        })
    return jsonify(items)


@app.route('/api/moderation/queue/<queue_id>/resubmit', methods=['POST'])
@web_login_required
def api_moderation_resubmit(queue_id):
    from moderation.service import decrypt_payload
    db = get_db()
    row = db.execute(
        "SELECT * FROM moderation_queue WHERE id = ? AND user_id = ? AND status = 'needs_review'",
        (queue_id, _current_user_id()),
    ).fetchone()
    if not row:
        db.close()
        return jsonify({'error': 'Review item not found.'}), 404
    try:
        payload = decrypt_payload(row['payload_enc'])
    except Exception:
        db.close()
        return jsonify({'error': 'The review item could not be opened securely.'}), 500
    data = request.get_json(silent=True) or {}
    content_type = row['content_type']
    if content_type in {'email', 'email_followup'}:
        payload['subject'] = str(data.get('subject') or payload.get('subject') or '').strip()
        payload['body'] = str(data.get('body') or payload.get('body') or '').strip()
        if not payload['subject'] or not payload['body']:
            db.close()
            return jsonify({'error': 'subject and body are required'}), 400
        payload['html'] = _build_email_html(payload['body'], payload.get('template_id', 'plain'), payload.get('sender_name', 'AutoReach'), payload.get('email', ''))
        try:
            send_moderated(payload, _current_user_id(), db)
        except DeliveryBlocked as exc:
            db.close()
            return jsonify({'error': str(exc), 'category': list(exc.decision.categories), 'policy_url': url_for('acceptable_use')}), 422
        except DeliveryQueued as exc:
            db.execute("UPDATE moderation_queue SET status='cancelled', updated_at=? WHERE id=?", (utc_now(), queue_id))
            db.commit(); db.close()
            return jsonify({'status': 'queued', 'queue_id': exc.queue_id, 'error': str(exc)}), 202
        except Exception:
            db.close(); app.logger.exception('Resubmitted email delivery failed')
            return jsonify({'error': 'Email delivery failed. Please try again.'}), 502
        db.execute("UPDATE moderation_queue SET status='delivered', updated_at=? WHERE id=?", (utc_now(), queue_id))
        db.execute(
            'INSERT INTO sent_log (business_name, email, date_sent, subject, body) VALUES (?, ?, ?, ?, ?)',
            (payload.get('business_name', ''), payload['email'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), payload['subject'], payload['body']),
        )
        db.commit(); db.close()
        return jsonify({'status': 'sent'})

    content = str(data.get('content') or payload.get('content') or '').strip()
    if not content:
        db.close()
        return jsonify({'error': 'content is required'}), 400
    decision, new_queue_id = moderate_and_queue(
        content, _current_user_id(), row['checkpoint'], content_type, db,
        payload={**payload, 'content': content},
    )
    if decision.verdict == 'allow':
        if content_type == 'email_template':
            save_email_template(content)
        db.execute("UPDATE moderation_queue SET status='cancelled', updated_at=? WHERE id=?", (utc_now(), queue_id))
        db.commit(); db.close()
        return jsonify({'status': 'saved'})
    if decision.verdict == 'block':
        db.close()
        return jsonify({'error': user_message(decision), 'category': list(decision.categories), 'policy_url': url_for('acceptable_use')}), 422
    db.execute("UPDATE moderation_queue SET status='cancelled', updated_at=? WHERE id=?", (utc_now(), queue_id))
    db.commit(); db.close()
    return jsonify({'status': 'queued', 'queue_id': new_queue_id, 'error': decision.reason}), 202


@app.route('/admin/moderation')
@moderation_admin_required
def moderation_admin_page():
    return render_template('moderation_admin.html')


@app.route('/api/admin/moderation', methods=['GET'])
@moderation_admin_required
def api_admin_moderation():
    user_id = request.args.get('user_id', type=int)
    category = (request.args.get('category') or '').strip()
    clauses, params = [], []
    if user_id is not None:
        clauses.append('user_id = ?'); params.append(user_id)
    if category:
        clauses.append('categories LIKE ?'); params.append(f'%"{category}"%')
    query = 'SELECT * FROM moderation_log' + (' WHERE ' + ' AND '.join(clauses) if clauses else '') + ' ORDER BY created_at DESC LIMIT 300'
    db = get_db(); rows = db.execute(query, tuple(params)).fetchall(); db.close()
    return jsonify([dict(row) for row in rows])


@app.route('/api/admin/blocklist', methods=['POST'])
@moderation_admin_required
def api_admin_blocklist_add():
    data = request.get_json(silent=True) or {}
    phrase = str(data.get('phrase') or '').strip()
    kind = data.get('type')
    target_user_id = data.get('user_id', _current_user_id())
    if not phrase or len(phrase) > 240 or kind not in {'word', 'regex', 'domain'}:
        return jsonify({'error': 'Enter a phrase (max 240 characters) and type word, regex, or domain.'}), 400
    if kind == 'regex':
        import re
        if re.search(r'\([^)]*[+*][^)]*\)[+*{]|\\[1-9]', phrase):
            return jsonify({'error': 'Regex contains a potentially unsafe nested repetition or backreference.'}), 400
        try: re.compile(phrase)
        except re.error: return jsonify({'error': 'Regex is invalid.'}), 400
    db = get_db()
    block_id = os.urandom(16).hex()
    db.execute('INSERT INTO blocklist (id, user_id, phrase, language, type, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
               (block_id, int(target_user_id), phrase, str(data.get('language') or 'und')[:12], kind, _current_user_id(), utc_now()))
    db.commit(); db.close()
    return jsonify({'id': block_id}), 201


@app.route('/api/admin/blocklist/<block_id>', methods=['DELETE'])
@moderation_admin_required
def api_admin_blocklist_delete(block_id):
    target_user_id = request.args.get('user_id', type=int, default=_current_user_id())
    db = get_db()
    db.execute('DELETE FROM blocklist WHERE id = ? AND user_id = ?', (block_id, target_user_id))
    db.commit(); db.close()
    return jsonify({'ok': True})


@app.route('/api/admin/blocklist', methods=['GET'])
@moderation_admin_required
def api_admin_blocklist_list():
    target_user_id = request.args.get('user_id', type=int, default=_current_user_id())
    db = get_db(); rows = db.execute('SELECT * FROM blocklist WHERE user_id = ? ORDER BY created_at DESC', (target_user_id,)).fetchall(); db.close()
    return jsonify([dict(row) for row in rows])


@app.route('/api/admin/strikes/<int:user_id>', methods=['POST'])
@moderation_admin_required
def api_admin_strikes(user_id):
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    if action == 'reset':
        status, count = 'active', 0
    elif action == 'override' and data.get('status') in {'active', 'warned', 'rate_limited', 'suspended'}:
        status = data['status']; count = max(0, int(data.get('strike_count', 0)))
    else:
        return jsonify({'error': 'Use reset or override with a valid status.'}), 400
    db = get_db()
    db.execute(
        """INSERT INTO user_strikes (user_id, strike_count, last_strike_at, status, notes) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET strike_count=excluded.strike_count,
           last_strike_at=excluded.last_strike_at, status=excluded.status, notes=excluded.notes""",
        (user_id, count, utc_now() if count else None, status, str(data.get('notes') or 'Admin override')[:500]),
    )
    db.commit(); db.close()
    return jsonify({'user_id': user_id, 'strike_count': count, 'status': status})


@app.route('/api/admin/strikes/<int:user_id>', methods=['GET'])
@moderation_admin_required
def api_admin_strikes_get(user_id):
    db = get_db()
    row = db.execute('SELECT user_id, strike_count, last_strike_at, status, notes FROM user_strikes WHERE user_id = ?', (user_id,)).fetchone()
    db.close()
    return jsonify(dict(row) if row else {'user_id': user_id, 'strike_count': 0, 'last_strike_at': None, 'status': 'active', 'notes': ''})

# ── Follow-up sequences ───────────────────────────────────────
@app.route('/followups')
@web_login_required
def followups():
    stats = get_followup_stats()
    return render_template('followups.html', stats=stats)

@app.route('/run_followups', methods=['POST'])
@web_login_required
def run_followups_route():
    try:
        summary = run_followups()
        flash(f"Follow-ups complete — {summary['sent']} sent, {summary['skipped_replied']} stopped (replied), {summary['errors']} errors.", 'success')
    except Exception as e:
        flash(f'Error running follow-ups: {str(e)}', 'error')
    return redirect(url_for('followups'))

@app.route('/api/followup_stats')
@web_login_required
def api_followup_stats():
    return jsonify(get_followup_stats())

def _daily_followup_thread():
    """Background thread — runs follow-ups once every 24 hours."""
    # Wait 60 seconds after startup before first run
    time.sleep(60)
    while True:
        print(f'[followup thread] Running at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        try:
            summary = run_followups()
            print(f'[followup thread] Done: {summary}')
        except Exception as e:
            print(f'[followup thread] Error: {e}')
        time.sleep(86400)  # 24 hours


def _record_queued_sent(payload, user_id):
    db = get_db()
    db.execute(
        'INSERT INTO sent_log (business_name, email, date_sent, subject, body) VALUES (?, ?, ?, ?, ?)',
        (payload.get('business_name', ''), payload['email'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), payload['subject'], payload.get('body', '')),
    )
    db.commit(); db.close()


def _moderation_retry_thread():
    if os.getenv('MODERATION_RETRY_WORKER_ENABLED', 'true').lower() == 'false':
        return
    time.sleep(max(5, int(os.getenv('MODERATION_RETRY_START_DELAY_SECONDS', '30'))))
    interval = max(30, int(os.getenv('MODERATION_RETRY_INTERVAL_SECONDS', '300')))
    while True:
        db = get_db()
        try:
            retry_queued(db, on_delivered=_record_queued_sent)
        except Exception:
            app.logger.exception('Moderation retry worker failed')
        finally:
            db.close()
        time.sleep(interval)

# Start background thread when the app starts
_thread = threading.Thread(target=_daily_followup_thread, daemon=True)
_thread.start()
_moderation_thread = threading.Thread(target=_moderation_retry_thread, daemon=True)
_moderation_thread.start()

@app.errorhandler(500)
def handle_500(e):
    import traceback
    return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
