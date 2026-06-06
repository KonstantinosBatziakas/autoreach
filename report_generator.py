from datetime import datetime
from db import get_db

def generate_report():
    db = get_db()
    rows = [dict(r) for r in db.execute('SELECT * FROM sent_log ORDER BY id').fetchall()]
    db.close()

    if not rows:
        print("No sent emails yet!")
        return

    total_sent = len(rows)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_count = sum(1 for row in rows if row.get("date_sent", "").startswith(today_str))

    print("\n=== Email Outreach Report ===")
    print(f"Total emails sent: {total_sent}")
    print(f"Emails sent today: {today_count}")
    print("\n--- Full list of contacted businesses ---")

    for i, row in enumerate(rows, 1):
        print(f"{i}. {row['business_name']} ({row['email']}) - {row['date_sent']}")

    print("\n" + "=" * 40)

if __name__ == "__main__":
    generate_report()
