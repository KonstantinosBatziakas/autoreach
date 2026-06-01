import schedule
import time
from datetime import datetime
from emailer import run_outreach

def scheduled_outreach():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running scheduled email outreach...")
    run_outreach(auto_send=True)
    print("Scheduled outreach completed!")

def setup_scheduler():
    print("\n=== Setup Scheduled Email Sending ===")
    time_input = input("Enter time for daily emails (HH:MM format, e.g., 09:00): ").strip()

    try:
        datetime.strptime(time_input, "%H:%M")
    except ValueError:
        print("Invalid time format! Please use HH:MM format (e.g., 09:00)")
        return

    schedule.every().day.at(time_input).do(scheduled_outreach)
    print(f"\nScheduled daily emails at {time_input}")
    print("Scheduler is now running. Press Ctrl+C to stop.")
    print("Note: Keep this terminal window open for scheduled emails to work.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nScheduler stopped.")

if __name__ == "__main__":
    setup_scheduler()
