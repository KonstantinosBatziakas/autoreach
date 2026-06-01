import csv
import os
from datetime import datetime
from emailer import SENT_LOG_FILE, initialize_sent_log

def generate_report():
    initialize_sent_log()

    if not os.path.exists(SENT_LOG_FILE):
        print("No sent emails yet!")
        return

    with open(SENT_LOG_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("No sent emails yet!")
        return

    total_sent = len(rows)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_count = sum(1 for row in rows if row["date_sent"].startswith(today_str))

    print("\n=== Email Outreach Report ===")
    print(f"Total emails sent: {total_sent}")
    print(f"Emails sent today: {today_count}")
    print("\n--- Full list of contacted businesses ---")

    for i, row in enumerate(rows, 1):
        print(f"{i}. {row['business_name']} ({row['email']}) - {row['date_sent']}")

    print("\n" + "=" * 40)

if __name__ == "__main__":
    generate_report()
