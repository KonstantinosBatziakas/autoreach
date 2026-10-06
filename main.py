from datetime import datetime

from lead_finder import find_businesses
from emailer import run_outreach
from email_scraper import scrape_emails
from report_generator import generate_report
from scheduler import setup_scheduler
from db import get_db
from moderation.queue import retry_queued


def retry_moderation_queue():
    db = get_db()
    try:
        def record_sent(payload, _user_id):
            db.execute(
                'INSERT INTO sent_log (business_name, email, date_sent, subject, body) VALUES (?, ?, ?, ?, ?)',
                (payload.get('business_name', ''), payload['email'],
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                 payload.get('subject', ''), payload.get('body', '')),
            )
            db.commit()
        return retry_queued(db, on_delivered=record_sent)
    finally:
        db.close()

def add_manual_lead():
    print("\n--- Add Manual Lead ---")
    name = input("Business name: ")
    address = input("Address: ")
    phone = input("Phone: ")
    website = input("Website: ")
    email = input("Email: ")
    db = get_db()
    db.execute(
        'INSERT INTO businesses (name, address, phone, website, email, stage, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (name, address, phone, website, email, 'New', '')
    )
    db.commit()
    db.close()
    print(f"Added {name} to database!")

def main():
    try:
        retry_moderation_queue()
    except Exception as exc:
        print(f"Moderation retry check failed safely: {exc}")
    while True:
        print("\n=== AutoReach ===")
        print("1. Find leads (Google Maps)")
        print("2. Scrape emails from websites")
        print("3. Run email outreach")
        print("4. Add manual lead")
        print("5. Exit")
        print("6. View outreach report")
        print("7. Setup scheduled sending")
        print("8. Retry moderation queue")
        choice = input("Choose (1-8): ").strip()
        if choice == "1":
            city = input("Enter city: ")
            btype = input("Enter business type: ")
            find_businesses(city, btype)
        elif choice == "2":
            scrape_emails()
        elif choice == "3":
            run_outreach()
        elif choice == "4":
            add_manual_lead()
        elif choice == "5":
            print("Goodbye!")
            break
        elif choice == "6":
            generate_report()
        elif choice == "7":
            setup_scheduler()
        elif choice == "8":
            try:
                print(retry_moderation_queue())
            except Exception as exc:
                print(f"Moderation retry check failed safely: {exc}")
        else:
            print("Invalid choice, try again.")

if __name__ == "__main__":
    main()
