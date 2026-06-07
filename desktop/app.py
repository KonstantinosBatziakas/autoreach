"""
AutoReach Desktop — CustomTkinter GUI
Run: python desktop/app.py
Package: pyinstaller desktop/app.py --name AutoReach --onefile --windowed
"""

import sys
import os
import threading
import time
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import customtkinter as ctk
from tkinter import messagebox, filedialog

from autoreach_core import db
from autoreach_core.emailer     import generate_email, build_html, send_email, DELAY_BETWEEN, MAX_PER_RUN
from autoreach_core.lead_finder import find_businesses
from autoreach_core.scraper     import find_email_for_website
from autoreach_core.followup    import run_due_followups, check_for_replies
from autoreach_core.rotation    import get_next_sender, get_all_sender_capacity, NoSendersAvailable

# ── Theme ─────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG       = "#111c1c"
BG_DARK  = "#0a1414"
BG_CARD  = "#162424"
CORAL    = "#e8806a"
CORAL_D  = "#c4614a"
TEAL     = "#4ecdc4"
TEXT     = "#cde0de"
DIM      = "#6a9090"
BORDER   = "#1e3232"
WHITE    = "#ffffff"
GREEN    = "#27c93f"
RED_C    = "#ff5f56"
FONT_M   = ("JetBrains Mono", 13)
FONT_S   = ("JetBrains Mono", 11)
FONT_XS  = ("JetBrains Mono", 10)
FONT_L   = ("JetBrains Mono", 16, "bold")
FONT_XL  = ("JetBrains Mono", 22, "bold")


def styled_btn(parent, text, command, colour=CORAL, fg=WHITE, width=160, height=36, font=FONT_S):
    return ctk.CTkButton(
        parent, text=text, command=command,
        fg_color=colour, hover_color=CORAL_D if colour == CORAL else colour,
        text_color=fg, font=font,
        width=width, height=height,
        corner_radius=6,
    )


def card_frame(parent, **kwargs):
    return ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER, **kwargs)


def section_label(parent, text):
    return ctk.CTkLabel(parent, text=text, font=FONT_XS, text_color=TEAL)


# ══════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════

class AutoReachApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.conn = db.get_conn()

        self.title("AutoReach")
        self.geometry("1100x720")
        self.minsize(900, 620)
        self.configure(fg_color=BG)

        self._build_layout()
        self._show_tab("dashboard")

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_layout(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, fg_color=BG_DARK, width=200, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(28, 24), padx=18, fill="x")

        icon_box = ctk.CTkFrame(logo_frame, fg_color=CORAL, width=32, height=32, corner_radius=6)
        icon_box.pack(side="left")
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text="✉", font=("JetBrains Mono", 14), text_color=WHITE).pack(expand=True)

        ctk.CTkLabel(logo_frame, text=" AUTO", font=("JetBrains Mono", 15, "bold"),
                     text_color=WHITE).pack(side="left")
        ctk.CTkLabel(logo_frame, text="REACH", font=("JetBrains Mono", 15, "bold"),
                     text_color=CORAL).pack(side="left")

        # Nav buttons
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "📊  Dashboard"),
            ("leads",     "👥  Leads"),
            ("find",      "🔍  Find Leads"),
            ("scrape",    "🕸️  Scrape Emails"),
            ("send",      "📤  Send Emails"),
            ("followups", "🔁  Follow-ups"),
            ("accounts",  "✉️  Accounts"),
            ("settings",  "⚙️  Settings"),
        ]
        for key, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=label,
                command=lambda k=key: self._show_tab(k),
                fg_color="transparent", hover_color=BORDER,
                text_color=DIM, anchor="w",
                font=FONT_S, height=38, corner_radius=6,
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[key] = btn

        # Version label at bottom
        ctk.CTkLabel(self.sidebar, text="v1.0.0", font=FONT_XS, text_color=BORDER).pack(
            side="bottom", pady=14)

        # Main content area
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        # Tab frames (built lazily)
        self.tabs = {}

    def _show_tab(self, name):
        # Highlight active nav
        for key, btn in self.nav_buttons.items():
            btn.configure(
                fg_color=BORDER if key == name else "transparent",
                text_color=WHITE if key == name else DIM,
            )
        # Clear content
        for w in self.content.winfo_children():
            w.destroy()

        builders = {
            "dashboard": self._build_dashboard,
            "leads":     self._build_leads,
            "find":      self._build_find,
            "scrape":    self._build_scrape,
            "send":      self._build_send,
            "followups": self._build_followups,
            "accounts":  self._build_accounts,
            "settings":  self._build_settings,
        }
        builders[name]()

    # ── Dashboard ─────────────────────────────────────────────────────────

    def _build_dashboard(self):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(frame, text="Dashboard", font=FONT_XL, text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(frame, text="Your outreach at a glance", font=FONT_S, text_color=DIM).pack(anchor="w", pady=(2, 20))

        a = db.get_analytics(self.conn)
        from autoreach_core.rotation import total_remaining_today
        remaining_cap = total_remaining_today(self.conn)

        stats_row = ctk.CTkFrame(frame, fg_color="transparent")
        stats_row.pack(fill="x", pady=(0, 20))

        for label, value, colour in [
            ("Total Leads",    a["total_leads"],  TEAL),
            ("With Email",     a["with_email"],   CORAL),
            ("Emails Sent",    a["total_sent"],   GREEN),
            ("Sent Today",     a["sent_today"],   WHITE),
            ("Daily Cap Left", remaining_cap,     TEAL),
        ]:
            tile = card_frame(stats_row)
            tile.pack(side="left", padx=(0, 12), ipadx=14, ipady=14, expand=True, fill="x")
            ctk.CTkLabel(tile, text=str(value), font=("JetBrains Mono", 28, "bold"), text_color=colour).pack(pady=(16,4))
            ctk.CTkLabel(tile, text=label, font=FONT_XS, text_color=DIM).pack(pady=(0,16))

        # Recent sent log
        ctk.CTkLabel(frame, text="Recent Activity", font=FONT_M, text_color=WHITE).pack(anchor="w", pady=(8, 8))
        log_card = card_frame(frame)
        log_card.pack(fill="x")

        rows = self.conn.execute(
            "SELECT business_name, email, sent_at, status FROM sent_log ORDER BY id DESC LIMIT 8"
        ).fetchall()

        if not rows:
            ctk.CTkLabel(log_card, text="No emails sent yet.", font=FONT_S, text_color=DIM).pack(pady=20)
        else:
            header_row = ctk.CTkFrame(log_card, fg_color="transparent")
            header_row.pack(fill="x", padx=16, pady=(10, 2))
            for col, w in [("Business", 220), ("Email", 220), ("Sent at", 160), ("Status", 80)]:
                ctk.CTkLabel(header_row, text=col, font=FONT_XS, text_color=TEAL, width=w, anchor="w").pack(side="left")

            for row in rows:
                r = ctk.CTkFrame(log_card, fg_color="transparent")
                r.pack(fill="x", padx=16, pady=1)
                status_colour = GREEN if row["status"] == "sent" else RED_C
                for val, w in [(row["business_name"][:26], 220), (row["email"][:26], 220),
                               (row["sent_at"][:16], 160), (row["status"], 80)]:
                    ctk.CTkLabel(r, text=val, font=FONT_XS, text_color=status_colour if val == row["status"] else TEXT, width=w, anchor="w").pack(side="left")
            ctk.CTkFrame(log_card, fg_color="transparent", height=10).pack()

    # ── Leads ─────────────────────────────────────────────────────────────

    def _build_leads(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(top, text="Leads", font=FONT_XL, text_color=WHITE).pack(side="left")

        btn_row = ctk.CTkFrame(top, fg_color="transparent")
        btn_row.pack(side="right")
        styled_btn(btn_row, "Export CSV", self._export_csv, colour=BG_CARD, fg=TEAL, width=110).pack(side="left", padx=4)
        styled_btn(btn_row, "+ Add Lead",  self._add_lead_dialog, width=110).pack(side="left")

        # Table
        table_card = card_frame(frame)
        table_card.pack(fill="both", expand=True)

        hdr = ctk.CTkFrame(table_card, fg_color=BG_DARK, corner_radius=0)
        hdr.pack(fill="x", padx=0)
        for col, w in [("#", 40), ("Name", 200), ("Email", 200), ("Website", 180), ("Status", 80)]:
            ctk.CTkLabel(hdr, text=col, font=FONT_XS, text_color=TEAL, width=w, anchor="w").pack(side="left", padx=(12,0), pady=8)

        scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        leads = db.get_leads(self.conn)
        if not leads:
            ctk.CTkLabel(scroll, text="No leads yet — use Find Leads to get started.", font=FONT_S, text_color=DIM).pack(pady=30)
        for lead in leads:
            row = ctk.CTkFrame(scroll, fg_color="transparent", height=32)
            row.pack(fill="x", padx=0)
            row.pack_propagate(False)
            email_col = lead["email"] if lead["email"] else "—"
            ec = TEXT if lead["email"] else DIM
            for val, w, colour in [
                (str(lead["id"]), 40, DIM),
                (lead["name"][:26], 200, WHITE),
                (email_col[:26],   200, ec),
                ((lead["website"] or "—")[:24], 180, DIM),
                (lead["status"],    80, TEAL),
            ]:
                ctk.CTkLabel(row, text=val, font=FONT_XS, text_color=colour, width=w, anchor="w").pack(side="left", padx=(12,0))

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="autoreach_leads.csv",
        )
        if path:
            db.export_leads_csv(self.conn, path)
            messagebox.showinfo("AutoReach", f"Exported to:\n{path}")

    def _add_lead_dialog(self):
        win = ctk.CTkToplevel(self)
        win.title("Add Lead")
        win.geometry("420x380")
        win.configure(fg_color=BG_DARK)
        win.grab_set()

        ctk.CTkLabel(win, text="Add Lead", font=FONT_L, text_color=WHITE).pack(pady=(20, 10))

        fields = {}
        for label in ["Name *", "Email", "Website", "Phone", "Address"]:
            ctk.CTkLabel(win, text=label, font=FONT_XS, text_color=DIM).pack(anchor="w", padx=24)
            e = ctk.CTkEntry(win, fg_color=BG_CARD, border_color=BORDER, text_color=TEXT, font=FONT_S, width=360)
            e.pack(padx=24, pady=(2, 8))
            fields[label] = e

        def save():
            name = fields["Name *"].get().strip()
            if not name:
                messagebox.showerror("Error", "Name is required.")
                return
            db.add_lead(
                self.conn,
                name=name,
                email=fields["Email"].get().strip(),
                website=fields["Website"].get().strip(),
                phone=fields["Phone"].get().strip(),
                address=fields["Address"].get().strip(),
            )
            win.destroy()
            self._show_tab("leads")

        styled_btn(win, "Save Lead", save, width=360).pack(padx=24, pady=10)

    # ── Find Leads ────────────────────────────────────────────────────────

    def _build_find(self):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(frame, text="Find Leads", font=FONT_XL, text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(frame, text="Search Google Maps for businesses", font=FONT_S, text_color=DIM).pack(anchor="w", pady=(2, 20))

        card = card_frame(frame)
        card.pack(fill="x", pady=(0, 16))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=24, pady=20, fill="x")

        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(row1, text="City", font=FONT_XS, text_color=DIM, width=100, anchor="w").pack(side="left")
        city_e = ctk.CTkEntry(row1, fg_color=BG_DARK, border_color=BORDER, text_color=TEXT, font=FONT_S, width=280)
        city_e.pack(side="left")

        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(row2, text="Business type", font=FONT_XS, text_color=DIM, width=100, anchor="w").pack(side="left")
        type_e = ctk.CTkEntry(row2, fg_color=BG_DARK, border_color=BORDER, text_color=TEXT, font=FONT_S, width=280)
        type_e.pack(side="left")

        log_var = ctk.StringVar(value="")
        log_lbl = ctk.CTkLabel(inner, textvariable=log_var, font=FONT_XS, text_color=TEAL, wraplength=500, justify="left")
        log_lbl.pack(anchor="w", pady=(0, 12))

        def run_find():
            city = city_e.get().strip()
            btype = type_e.get().strip()
            if not city or not btype:
                log_var.set("⚠  Enter city and business type.")
                return
            cfg = db.get_all_config(self.conn)
            if not cfg.get("google_maps_api_key"):
                log_var.set("✗  Google Maps API key not set. Go to Settings.")
                return

            log_var.set("→  Searching Google Maps…")
            find_btn.configure(state="disabled")

            def task():
                try:
                    results = find_businesses(city, btype, cfg["google_maps_api_key"])
                    db.bulk_insert_leads(self.conn, results)
                    log_var.set(f"✓  Found and saved {len(results)} leads.")
                except Exception as e:
                    log_var.set(f"✗  Error: {e}")
                finally:
                    find_btn.configure(state="normal")

            threading.Thread(target=task, daemon=True).start()

        find_btn = styled_btn(inner, "Search", run_find, width=140)
        find_btn.pack(anchor="w")

    # ── Scrape Emails ─────────────────────────────────────────────────────

    def _build_scrape(self):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(frame, text="Scrape Emails", font=FONT_XL, text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(frame, text="Crawl lead websites to find contact emails", font=FONT_S, text_color=DIM).pack(anchor="w", pady=(2, 20))

        card = card_frame(frame)
        card.pack(fill="x")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=24, pady=20, fill="x")

        leads    = [dict(r) for r in db.get_leads(self.conn)]
        no_email = [l for l in leads if not l.get("email")]
        ctk.CTkLabel(inner, text=f"{len(no_email)} leads without email  ·  {len(leads)} total",
                     font=FONT_S, text_color=DIM).pack(anchor="w", pady=(0, 12))

        progress_var = ctk.DoubleVar(value=0)
        bar = ctk.CTkProgressBar(inner, variable=progress_var, fg_color=BG_DARK, progress_color=TEAL, width=480)
        bar.pack(anchor="w", pady=(0, 10))

        log_text = ctk.CTkTextbox(inner, height=200, fg_color=BG_DARK, text_color=TEXT,
                                  font=FONT_XS, border_color=BORDER, border_width=1)
        log_text.pack(fill="x", pady=(0, 14))
        log_text.configure(state="disabled")

        def append_log(msg):
            log_text.configure(state="normal")
            log_text.insert("end", msg + "\n")
            log_text.see("end")
            log_text.configure(state="disabled")

        def run_scrape():
            if not no_email:
                append_log("⚠  All leads already have emails.")
                return
            scrape_btn.configure(state="disabled")
            found = [0]
            total = len(no_email)

            def task():
                for i, lead in enumerate(no_email):
                    append_log(f"[{i+1}/{total}] {lead['name'][:40]}…")
                    email = find_email_for_website(lead.get("website", ""))
                    if email:
                        db.update_lead_email(self.conn, lead["id"], email)
                        append_log(f"     ✓ Found: {email}")
                        found[0] += 1
                    else:
                        append_log(f"     — none found")
                    progress_var.set((i + 1) / total)
                    time.sleep(2)
                append_log(f"\n✓ Done — {found[0]} emails found.")
                scrape_btn.configure(state="normal")

            threading.Thread(target=task, daemon=True).start()

        scrape_btn = styled_btn(inner, "Start Scraping", run_scrape, width=180)
        scrape_btn.pack(anchor="w")

    # ── Send Emails ───────────────────────────────────────────────────────

    def _build_send(self):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(frame, text="Send Emails", font=FONT_XL, text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(frame, text="Generate, preview, and send AI cold emails", font=FONT_S, text_color=DIM).pack(anchor="w", pady=(2, 20))

        cfg = db.get_all_config(self.conn)
        # Require Groq. Resend credentials checked below.
        if not cfg.get("groq_api_key"):
            card = card_frame(frame)
            card.pack(fill="x")
            ctk.CTkLabel(card, text="⚠  Groq API key not configured.\nGo to Settings to add it.",
                         font=FONT_S, text_color=CORAL, justify="center").pack(pady=30)
            return
        # Check Resend is configured
        try:
            get_next_sender(self.conn)  # dry-run check
        except NoSendersAvailable:
            card = card_frame(frame)
            card.pack(fill="x")
            ctk.CTkLabel(card,
                text="⚠  Resend API key not configured.\nGo to Settings and add your Resend API key and from_email.",
                font=FONT_S, text_color=CORAL, justify="center").pack(pady=30)
            return

        all_leads = [dict(r) for r in db.get_leads(self.conn, with_email_only=True)]
        sent_set  = db.get_sent_emails_set(self.conn)
        # Show ALL leads — mark already-sent ones but don't exclude them
        pending   = [l for l in all_leads if l["email"].lower() not in sent_set]
        already   = [l for l in all_leads if l["email"].lower() in sent_set]
        # Queue: unsent first, then already-sent at the end
        leads     = pending + already

        # Options card
        opt_card = card_frame(frame)
        opt_card.pack(fill="x", pady=(0, 16))
        opt_inner = ctk.CTkFrame(opt_card, fg_color="transparent")
        opt_inner.pack(padx=24, pady=16, fill="x")

        row1 = ctk.CTkFrame(opt_inner, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(row1, text="Language", font=FONT_XS, text_color=DIM, width=120, anchor="w").pack(side="left")
        lang_var = ctk.StringVar(value="english")
        ctk.CTkSegmentedButton(row1, values=["english", "greek"], variable=lang_var,
                               fg_color=BG_DARK, selected_color=CORAL,
                               font=FONT_XS, width=220).pack(side="left")

        row2 = ctk.CTkFrame(opt_inner, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(row2, text="Leads", font=FONT_XS, text_color=DIM, width=120, anchor="w").pack(side="left")
        ctk.CTkLabel(row2, text=f"{len(pending)} new  ·  {len(already)} already sent",
                     font=FONT_S, text_color=TEAL).pack(side="left")

        from autoreach_core.rotation import total_remaining_today
        remaining = total_remaining_today(self.conn)
        capacity  = get_all_sender_capacity(self.conn)
        cap_total = sum(s["daily_limit"] for s in capacity if s["enabled"])

        row3 = ctk.CTkFrame(opt_inner, fg_color="transparent")
        row3.pack(fill="x")
        ctk.CTkLabel(row3, text="Remaining today", font=FONT_XS, text_color=DIM, width=120, anchor="w").pack(side="left")
        ctk.CTkLabel(row3, text=f"{remaining} / {cap_total}  ({len([s for s in capacity if s['enabled']])} account(s))",
                     font=FONT_S, text_color=TEXT).pack(side="left")

        # Preview area
        preview_card = card_frame(frame)
        preview_card.pack(fill="x", pady=(0, 14))
        prev_inner = ctk.CTkFrame(preview_card, fg_color="transparent")
        prev_inner.pack(padx=24, pady=16, fill="x")

        ctk.CTkLabel(prev_inner, text="Email Preview", font=FONT_M, text_color=WHITE).pack(anchor="w", pady=(0, 8))

        subject_var = ctk.StringVar(value="—")
        ctk.CTkLabel(prev_inner, textvariable=subject_var, font=FONT_S, text_color=CORAL).pack(anchor="w", pady=(0, 6))

        body_box = ctk.CTkTextbox(prev_inner, height=160, fg_color=BG_DARK, text_color=TEXT,
                                  font=FONT_XS, border_color=BORDER, border_width=1)
        body_box.pack(fill="x", pady=(0, 10))
        body_box.configure(state="disabled")

        lead_label_var = ctk.StringVar(value="No lead selected")
        ctk.CTkLabel(prev_inner, textvariable=lead_label_var, font=FONT_XS, text_color=DIM).pack(anchor="w")

        # State
        self._current_idx  = [0]
        self._current_body = [""]
        self._current_subj = [""]

        def set_body(subj, body):
            subject_var.set(f"Subject: {subj}")
            body_box.configure(state="normal")
            body_box.delete("1.0", "end")
            body_box.insert("1.0", body)
            body_box.configure(state="disabled")

        def generate_next():
            if self._current_idx[0] >= len(leads):
                lead_label_var.set("✓ All leads processed for this session.")
                gen_btn.configure(state="disabled")
                send_btn.configure(state="disabled")
                return

            if total_remaining_today(self.conn) <= 0:
                lead_label_var.set("⚠ Daily limit reached across all sender accounts.")
                return

            lead = leads[self._current_idx[0]]
            already_sent = lead["email"].lower() in sent_set
            status_note  = "  ⚠ already sent before" if already_sent else ""
            lead_label_var.set(f"Generating for: {lead['name']} ({lead['email']}){status_note}")
            gen_btn.configure(state="disabled")
            send_btn.configure(state="disabled")

            def task():
                try:
                    subj, body = generate_email(lead, lang_var.get(), cfg["groq_api_key"])
                    self._current_body[0] = body
                    self._current_subj[0] = subj
                    set_body(subj, body)
                    already_sent2 = lead["email"].lower() in sent_set
                    note = "  ⚠ already sent before — sending again" if already_sent2 else ""
                    lead_label_var.set(f"Lead: {lead['name']}  ·  {lead['email']}{note}")
                    send_btn.configure(state="normal")
                except Exception as e:
                    lead_label_var.set(f"✗ Generation failed: {e}")
                finally:
                    gen_btn.configure(state="normal")

            threading.Thread(target=task, daemon=True).start()

        def send_current():
            if self._current_idx[0] >= len(leads):
                return
            lead = leads[self._current_idx[0]]
            send_btn.configure(state="disabled")

            def task():
                try:
                    resend_key, from_email = get_next_sender(self.conn)
                except NoSendersAvailable as e:
                    lead_label_var.set(f"✗ No sender available: {e}")
                    send_btn.configure(state="normal")
                    return

                html = build_html(self._current_body[0], lead["name"], lead["email"])
                try:
                    send_email(lead["email"], self._current_subj[0], html,
                               resend_key, from_email)
                    db.log_sent(self.conn, lead["id"], lead["name"], lead["email"],
                                self._current_subj[0], self._current_body[0],
                                lang_var.get(), "sent", from_email)
                    # Schedule follow-ups
                    delays_cfg = db.get_config(self.conn, "followup_delays", "3,7,14")
                    delays = [int(d.strip()) for d in delays_cfg.split(",")][:3]
                    db.schedule_followups(self.conn, lead["id"], lead["name"],
                                          lead["email"], lang_var.get(), delays)
                    lead_label_var.set(
                        f"✓ [{from_email}] Sent → follow-ups at +{delays[0]}d, +{delays[1]}d, +{delays[2]}d"
                    )
                    self._current_idx[0] += 1
                    time.sleep(1)
                    generate_next()
                except Exception as e:
                    lead_label_var.set(f"✗ Send failed: {e}")
                    db.log_sent(self.conn, lead["id"], lead["name"], lead["email"],
                                self._current_subj[0], self._current_body[0],
                                lang_var.get(), "failed", from_email)
                    send_btn.configure(state="normal")

            threading.Thread(target=task, daemon=True).start()

        def skip_current():
            self._current_idx[0] += 1
            set_body("", "")
            lead_label_var.set("Skipped.")
            generate_next()

        # Buttons
        btn_row = ctk.CTkFrame(prev_inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))

        gen_btn  = styled_btn(btn_row, "Generate ↻", generate_next, colour=BG_CARD, fg=TEAL, width=140)
        gen_btn.pack(side="left", padx=(0, 8))
        skip_btn = styled_btn(btn_row, "Skip →",     skip_current,  colour=BG_CARD, fg=DIM,  width=100)
        skip_btn.pack(side="left", padx=(0, 8))
        send_btn = styled_btn(btn_row, "Send ✓",     send_current,  width=120)
        send_btn.pack(side="left")
        send_btn.configure(state="disabled")

        if leads:
            generate_next()

    # ── Follow-ups ────────────────────────────────────────────────────────

    def _build_followups(self):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(frame, text="Follow-ups", font=FONT_XL, text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(frame, text="Automatically re-engage leads who haven't replied",
                     font=FONT_S, text_color=DIM).pack(anchor="w", pady=(2, 20))

        # Stats row
        fa = db.get_followup_analytics(self.conn)
        stats_row = ctk.CTkFrame(frame, fg_color="transparent")
        stats_row.pack(fill="x", pady=(0, 20))
        for label, value, colour in [
            ("Pending",      fa["pending"],  CORAL),
            ("Sent",         fa["sent"],     GREEN),
            ("Replied",      fa["replied"],  TEAL),
            ("Skipped",      fa["skipped"],  DIM),
        ]:
            tile = card_frame(stats_row)
            tile.pack(side="left", padx=(0, 12), ipadx=14, ipady=14, expand=True, fill="x")
            ctk.CTkLabel(tile, text=str(value), font=("JetBrains Mono", 24, "bold"),
                         text_color=colour).pack(pady=(14, 4))
            ctk.CTkLabel(tile, text=label, font=FONT_XS, text_color=DIM).pack(pady=(0, 14))

        # Action card
        action_card = card_frame(frame)
        action_card.pack(fill="x", pady=(0, 16))
        inner = ctk.CTkFrame(action_card, fg_color="transparent")
        inner.pack(padx=24, pady=18, fill="x")

        ctk.CTkLabel(inner, text="Run Follow-ups", font=FONT_M, text_color=WHITE).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(inner,
                     text="Checks the database for replied leads first, then sends any overdue follow-up emails via Resend.",
                     font=FONT_XS, text_color=DIM).pack(anchor="w", pady=(0, 14))

        log_text = ctk.CTkTextbox(inner, height=180, fg_color=BG_DARK, text_color=TEXT,
                                  font=FONT_XS, border_color=BORDER, border_width=1)
        log_text.pack(fill="x", pady=(0, 14))
        log_text.configure(state="disabled")

        def append_log(msg):
            log_text.configure(state="normal")
            log_text.insert("end", msg + "\n")
            log_text.see("end")
            log_text.configure(state="disabled")

        def run_fu():
            cfg = db.get_all_config(self.conn)
            missing = [k for k in ("groq_api_key", "resend_api_key") if not cfg.get(k)]
            if missing:
                append_log(f"✗ Missing config: {', '.join(missing)} — go to Settings.")
                return
            run_btn.configure(state="disabled")
            check_btn.configure(state="disabled")

            def confirm_cb(row, subj, body):
                """
                Called from the background thread for each follow-up.
                Shows a blocking dialog on the main thread and returns
                's' send / 'k' skip.
                """
                result = [None]
                event  = threading.Event()

                def show_dialog():
                    win = ctk.CTkToplevel(self)
                    win.title("Send Follow-up?")
                    win.geometry("520x420")
                    win.configure(fg_color=BG_DARK)
                    win.grab_set()
                    win.lift()
                    win.focus_force()

                    ctk.CTkLabel(win,
                        text=f"Follow-up #{row['sequence_num']} — {row['business_name']}",
                        font=FONT_M, text_color=WHITE).pack(anchor="w", padx=24, pady=(20, 2))
                    ctk.CTkLabel(win,
                        text=f"Scheduled: {row['scheduled_for']}  ·  To: {row['email']}",
                        font=FONT_XS, text_color=DIM).pack(anchor="w", padx=24, pady=(0, 10))

                    ctk.CTkLabel(win, text=f"Subject: {subj}",
                        font=FONT_XS, text_color=CORAL).pack(anchor="w", padx=24, pady=(0, 6))

                    body_box = ctk.CTkTextbox(win, height=160, fg_color=BG_CARD,
                        text_color=TEXT, font=FONT_XS, border_color=BORDER, border_width=1)
                    body_box.pack(fill="x", padx=24, pady=(0, 16))
                    body_box.insert("1.0", body)
                    body_box.configure(state="disabled")

                    btn_row = ctk.CTkFrame(win, fg_color="transparent")
                    btn_row.pack(padx=24, anchor="w")

                    def choose(val):
                        result[0] = val
                        win.destroy()
                        event.set()

                    styled_btn(btn_row, "Send ✓",  lambda: choose("s"), width=120).pack(side="left", padx=(0, 8))
                    styled_btn(btn_row, "Skip →",  lambda: choose("k"), colour=BG_CARD, fg=DIM, width=100).pack(side="left")

                    win.protocol("WM_DELETE_WINDOW", lambda: choose("k"))

                self.after(0, show_dialog)
                event.wait(timeout=120)   # wait up to 2 min for user response
                return result[0] if result[0] else "k"

            def task():
                counts = run_due_followups(
                    self.conn, cfg, auto=False,
                    progress_cb=append_log,
                    confirm_cb=confirm_cb,
                )
                append_log(
                    f"\nDone — Sent: {counts['sent']}  Skipped: {counts['skipped']}  "
                    f"Failed: {counts['failed']}  New replies: {counts['replies_found']}"
                )
                run_btn.configure(state="normal")
                check_btn.configure(state="normal")

            threading.Thread(target=task, daemon=True).start()

        def check_replies_only():
            check_btn.configure(state="disabled")

            def task():
                try:
                    n = check_for_replies(self.conn, progress_cb=append_log)
                    append_log(f"\n✓ {n} new reply(ies) detected." if n else "\n→ No new replies found.")
                except Exception as e:
                    append_log(f"✗ Error: {e}")
                finally:
                    check_btn.configure(state="normal")

            threading.Thread(target=task, daemon=True).start()

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(anchor="w")
        run_btn   = styled_btn(btn_row, "Run Follow-ups", run_fu, width=180)
        run_btn.pack(side="left", padx=(0, 10))
        check_btn = styled_btn(btn_row, "Check Replies", check_replies_only,
                               colour=BG_CARD, fg=TEAL, width=160)
        check_btn.pack(side="left")

        # Follow-up queue table
        ctk.CTkLabel(frame, text="Scheduled Queue", font=FONT_M, text_color=WHITE).pack(
            anchor="w", pady=(16, 8))
        table_card = card_frame(frame)
        table_card.pack(fill="both", expand=True)

        hdr = ctk.CTkFrame(table_card, fg_color=BG_DARK, corner_radius=0)
        hdr.pack(fill="x")
        for col, w in [("Lead", 200), ("Email", 190), ("#", 30), ("Scheduled", 110), ("Status", 80)]:
            ctk.CTkLabel(hdr, text=col, font=FONT_XS, text_color=TEAL,
                         width=w, anchor="w").pack(side="left", padx=(12, 0), pady=8)

        scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        rows = db.get_all_followups(self.conn)
        if not rows:
            ctk.CTkLabel(scroll, text="No follow-ups scheduled yet. Send emails first.",
                         font=FONT_S, text_color=DIM).pack(pady=20)
        else:
            STATUS_COLOURS = {
                "pending": CORAL, "sent": GREEN,
                "replied": TEAL,  "skipped": DIM,
            }
            for row in rows:
                r = ctk.CTkFrame(scroll, fg_color="transparent", height=30)
                r.pack(fill="x")
                r.pack_propagate(False)
                sc = STATUS_COLOURS.get(row["status"], TEXT)
                for val, w, colour in [
                    (row["lead_name"][:24],  200, WHITE),
                    (row["email"][:24],       190, DIM),
                    (str(row["sequence_num"]), 30, CORAL),
                    (row["scheduled_for"],    110, TEXT),
                    (row["status"],            80, sc),
                ]:
                    ctk.CTkLabel(r, text=val, font=FONT_XS, text_color=colour,
                                 width=w, anchor="w").pack(side="left", padx=(12, 0))

    # ── Accounts (Resend sender status) ──────────────────────────────────

    def _build_accounts(self):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(frame, text="Sender", font=FONT_XL, text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(frame,
                     text="AutoReach sends email via the Resend API — configure your key in Settings",
                     font=FONT_S, text_color=DIM).pack(anchor="w", pady=(2, 20))

        # ── Capacity overview ──────────────────────────────────────────
        cap_card = card_frame(frame)
        cap_card.pack(fill="x", pady=(0, 16))
        cap_inner = ctk.CTkFrame(cap_card, fg_color="transparent")
        cap_inner.pack(padx=24, pady=14, fill="x")

        ctk.CTkLabel(cap_inner, text="Daily Capacity", font=FONT_M, text_color=WHITE).pack(anchor="w", pady=(0, 8))
        capacity = get_all_sender_capacity(self.conn)

        if not capacity:
            ctk.CTkLabel(cap_inner,
                         text="Resend API key not set. Go to Settings to add it.",
                         font=FONT_XS, text_color=DIM).pack(anchor="w")
        else:
            s = capacity[0]
            remaining_c = GREEN if s["remaining"] > 0 else RED_C
            ctk.CTkLabel(cap_inner,
                         text=f"From: {s['email']}",
                         font=FONT_S, text_color=TEAL).pack(anchor="w")
            ctk.CTkLabel(cap_inner,
                         text=f"Sent today: {s['sent_today']}  ·  Remaining: {s['remaining']} / {s['daily_limit']}",
                         font=FONT_S, text_color=remaining_c).pack(anchor="w", pady=(4, 0))

        # ── Help note ──────────────────────────────────────────────────
        note_card = card_frame(frame)
        note_card.pack(fill="x", pady=(16, 0))
        note_inner = ctk.CTkFrame(note_card, fg_color="transparent")
        note_inner.pack(padx=24, pady=16, fill="x")
        ctk.CTkLabel(note_inner, text="About Resend", font=FONT_S, text_color=WHITE).pack(anchor="w", pady=(0, 6))
        for line in [
            "Resend is a developer-friendly email API — free tier: 3 000 emails/month.",
            "Sign up at resend.com, verify your domain or use onboarding@resend.dev for testing.",
            "Set resend_api_key and from_email in Settings.",
            "",
            "Replies are detected from the database (leads marked 'replied').",
            "You can mark a lead as replied directly in the Leads list.",
        ]:
            ctk.CTkLabel(note_inner, text=line, font=FONT_XS, text_color=DIM, anchor="w").pack(anchor="w")

    # ── Settings ──────────────────────────────────────────────────────────

    def _build_settings(self):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(frame, text="Settings", font=FONT_XL, text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(frame, text="API keys and preferences — saved locally", font=FONT_S, text_color=DIM).pack(anchor="w", pady=(2, 20))

        card = card_frame(frame)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=28, pady=24, fill="x")

        cfg = db.get_all_config(self.conn)

        fields_cfg = [
            ("groq_api_key",        "Groq API Key",                         True),
            ("resend_api_key",      "Resend API Key  (resend.com)",          True),
            ("from_email",          "From Email  (verified in Resend)",      False),
            ("google_maps_api_key", "Google Maps API Key",                   True),
            ("daily_limit",         "Daily limit (default 500)",             False),
            ("delay_seconds",       "Delay between sends (s)",               False),
            ("followup_delays",     "Follow-up delays (days, e.g. 3,7,14)", False),
        ]

        entries = {}
        for key, label, secret in fields_cfg:
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=6)
            ctk.CTkLabel(row, text=label, font=FONT_XS, text_color=DIM, width=200, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, fg_color=BG_DARK, border_color=BORDER, text_color=TEXT,
                             font=FONT_S, width=320, show="•" if secret else "")
            e.pack(side="left")
            if cfg.get(key):
                e.insert(0, cfg[key])
            entries[key] = e

        status_var = ctk.StringVar(value="")

        def save():
            for key, e in entries.items():
                val = e.get().strip()
                if val:
                    db.set_config(self.conn, key, val)
            status_var.set("✓  Settings saved.")

        styled_btn(inner, "Save Settings", save, width=180).pack(anchor="w", pady=(16, 4))
        ctk.CTkLabel(inner, textvariable=status_var, font=FONT_XS, text_color=GREEN).pack(anchor="w")

        # Info box
        info_card = card_frame(frame)
        info_card.pack(fill="x", pady=(16, 0))
        info_inner = ctk.CTkFrame(info_card, fg_color="transparent")
        info_inner.pack(padx=24, pady=18, fill="x")
        ctk.CTkLabel(info_inner, text="Where to get your API keys", font=FONT_S, text_color=WHITE).pack(anchor="w", pady=(0, 8))
        for line in [
            "Groq API key     →  console.groq.com  (free)",
            "Resend API key   →  resend.com  (free tier: 3 000 emails/month)",
            "From email       →  must be a verified domain/address in Resend",
            "Google Maps key  →  console.cloud.google.com → Places API",
            "",
            f"Config stored at: {db.DB_PATH}",
        ]:
            ctk.CTkLabel(info_inner, text=line, font=FONT_XS, text_color=DIM, anchor="w").pack(anchor="w")


# ── Entry ─────────────────────────────────────────────────────────────────

def main():
    app = AutoReachApp()
    app.mainloop()


if __name__ == "__main__":
    main()
