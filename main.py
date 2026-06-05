from lead_finder import find_businesses
from emailer import run_outreach
from email_scraper import scrape_emails
from report_generator import generate_report
from scheduler import setup_scheduler
import csv

def add_manual_lead():
    print("\n--- Add Manual Lead ---")
    name = input("Business name: ")
    address = input("Address: ")
    phone = input("Phone: ")
    website = input("Website: ")
    email = input("Email: ")
    row = {
        "name": name,
        "address": address,
        "phone": phone,
        "website": website,
        "email": email
    }
    with open("businesses.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "address", "phone", "website", "email"])
        writer.writerow(row)
    print(f"Added {name} to businesses.csv!")

def main():
    while True:
        print("\n=== AutoReach ===")
        print("1. Find leads (Google Maps)")
        print("2. Scrape emails from websites")
        print("3. Run email outreach")
        print("4. Add manual lead")
        print("5. Exit")
        print("6. View outreach report")
        print("7. Setup scheduled sending")
        choice = input("Choose (1-7): ").strip()
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
        else:
            print("Invalid choice, try again.")

if __name__ == "__main__":
    main()