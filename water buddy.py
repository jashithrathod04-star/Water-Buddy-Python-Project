"""
Water Buddy - Standalone Python (Tkinter) app (single file)
Run with: python water_buddy_desktop.py  (or open in IDLE and Run Module)

No external libraries required.

Features:
- Profile (name, age, weight kg, activity level)
- Goal calculation: base 35 ml/kg (adjusted by activity & age)
- Log water (quick buttons + custom)
- Reminders via Tkinter popup (configurable interval)
- Daily progress ring (Canvas) and weekly bar chart (Canvas)
- SQLite local storage (profile + logs)
- Eco Mode estimate: bottles saved
- Gamification: streaks & badges
- Export data to CSV
- Simple "predictor" that adjusts suggestions based on recent activity
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
import os
from datetime import datetime, date, timedelta
import math
import csv

# ---------------------------
# Constants & DB
# ---------------------------
DB_PATH = "water_buddy_local.db"
BASE_ML_PER_KG = 35  # ml per kg base guideline

# create DB & tables if not exist
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            weight_kg REAL,
            activity TEXT,
            created_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY,
            logged_at TEXT,
            amount_ml INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY,
            name TEXT,
            earned_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------------------
# Data helpers
# ---------------------------
def get_profile():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM profile ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        return {'id':row[0],'name':row[1],'age':row[2],'weight_kg':row[3],'activity':row[4],'created_at':row[5]}
    return None

def set_profile(name, age, weight_kg, activity):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO profile (name, age, weight_kg, activity, created_at) VALUES (?, ?, ?, ?, ?)',
              (name, age, weight_kg, activity, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def log_water_ml(amount_ml):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO logs (logged_at, amount_ml) VALUES (?, ?)', (datetime.utcnow().isoformat(), amount_ml))
    conn.commit()
    conn.close()
    check_badges_and_streaks()

def get_totals_for_days(days=7):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    totals = []
    for i in range(days-1, -1, -1):
        d = date.today() - timedelta(days=i)
        start = datetime.combine(d, datetime.min.time()).isoformat()
        end = datetime.combine(d, datetime.max.time()).isoformat()
        c.execute('SELECT SUM(amount_ml) FROM logs WHERE logged_at BETWEEN ? AND ?', (start, end))
        row = c.fetchone()
        total = row[0] if row and row[0] else 0
        totals.append({'date': d, 'total_ml': total})
    conn.close()
    return totals

def get_today_total():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    start = datetime.combine(date.today(), datetime.min.time()).isoformat()
    end = datetime.combine(date.today(), datetime.max.time()).isoformat()
    c.execute('SELECT SUM(amount_ml) FROM logs WHERE logged_at BETWEEN ? AND ?', (start, end))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else 0

def export_logs_csv(path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT logged_at, amount_ml FROM logs ORDER BY logged_at')
    rows = c.fetchall()
    conn.close()
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['logged_at', 'amount_ml'])
        writer.writerows(rows)

# ---------------------------
# Business logic
# ---------------------------
def calculate_goal_ml(weight_kg, age=None, activity='normal', weather_temp_c=None):
    # base formula
    base = weight_kg * BASE_ML_PER_KG
    multiplier = 1.0
    if activity == 'low':
        multiplier *= 0.95
    elif activity == 'high':
        multiplier *= 1.2
    if age and age >= 65:
        multiplier *= 0.9
    if weather_temp_c is not None:
        if weather_temp_c >= 30:
            multiplier *= 1.25
        elif weather_temp_c >= 25:
            multiplier *= 1.10
    return int(base * multiplier)

def estimate_bottles_saved(total_ml, bottle_size_ml=500):
    # naive eco estimate: how many plastic bottles equivalent avoided if user uses refill bottle
    return total_ml / bottle_size_ml

# Simple predictor: checks last 3 days average and suggests increasing reminders if intake low
def predictor_adjustment():
    totals = get_totals_for_days(7)
    recent = totals[-3:]  # last 3 days
    avg = sum(t['total_ml'] for t in recent) / 3
    profile = get_profile()
    if not profile:
        return 1.0
    goal = calculate_goal_ml(profile['weight_kg'], age=profile['age'], activity=profile['activity'])
    # if avg is below 70% of goal -> be more aggressive
    if avg < 0.7 * goal:
        return 1.2
    elif avg < 0.9 * goal:
        return 1.05
    else:
        return 1.0

# Badges & streaks
def check_badges_and_streaks():
    # award a badge for 7 days of logging >75% goal
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # check last 7 days totals
    totals = get_totals_for_days(7)
    profile = get_profile()
    if not profile:
        conn.close(); return
    goal = calculate_goal_ml(profile['weight_kg'], age=profile['age'], activity=profile['activity'])
    good_days = sum(1 for t in totals if t['total_ml'] >= 0.75 * goal)
    c.execute('SELECT * FROM badges WHERE name = ?', ('7-day-streak',))
    if good_days == 7 and not c.fetchone():
        c.execute('INSERT INTO badges (name, earned_at) VALUES (?, ?)', ('7-day-streak', datetime.utcnow().isoformat()))
    # simple 'first-log' badge
    c.execute('SELECT COUNT(*) FROM logs')
    total_logs = c.fetchone()[0]
    c.execute('SELECT * FROM badges WHERE name = ?', ('first-log',))
    if total_logs >= 1 and not c.fetchone():
        c.execute('INSERT INTO badges (name, earned_at) VALUES (?, ?)', ('first-log', datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_badges():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT name, earned_at FROM badges ORDER BY earned_at DESC')
    rows = c.fetchall()
    conn.close()
    return rows

# ---------------------------
# UI
# ---------------------------
class WaterBuddyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Water Buddy")
        self.geometry("1250x640")
        self.configure(bg="#071928")
        self.resizable(False, False)

        # state
        self.profile = get_profile()
        self.reminder_interval_min = 60  # default
        self.reminder_job = None
        self.reminder_enabled = False

        # build UI
        self._build_header()
        self._build_left_panel()
        self._build_main_panel()
        self._load_profile_state()
        self.refresh_ui()

    def _build_header(self):
        header = tk.Frame(self, bg="#062027", height=80)
        header.pack(side=tk.TOP, fill=tk.X)
        title = tk.Label(header, text="Water Buddy", fg="#00E5FF", bg="#062027", font=("Montserrat", 22, "bold"))
        title.pack(side=tk.LEFT, padx=18, pady=12)
        subtitle = tk.Label(header, text="Formative Assessment 1 — Python", fg="#BFEFF6", bg="#062027", font=("Lato", 10))
        subtitle.pack(side=tk.LEFT, padx=6, pady=18)
        name = tk.Label(header, text="By: Jashith Rathod", fg="#A9F0FF", bg="#062027", font=("Lato", 10))
        name.pack(side=tk.RIGHT, padx=18)

    def _build_left_panel(self):
        left = tk.Frame(self, bg="#052022", width=300)
        left.pack(side=tk.LEFT, fill=tk.Y)

        # Profile card
        prof_card = tk.LabelFrame(left, text="Profile", fg="#DFF9FF", bg="#052022", bd=0, font=("Lato", 12, "bold"))
        prof_card.pack(padx=12, pady=12, fill=tk.X)
        self.lbl_profile = tk.Label(prof_card, text="No profile set", fg="#CFF8FF", bg="#052022", justify=tk.LEFT, anchor='w', font=("Lato", 11))
        self.lbl_profile.pack(padx=8, pady=6, fill=tk.X)
        tk.Button(prof_card, text="Edit Profile", command=self.open_profile_dialog, bg="#00CEDA", fg="black").pack(padx=8, pady=6, fill=tk.X)

        # Quick log
        log_card = tk.LabelFrame(left, text="Quick Log", fg="#DFF9FF", bg="#052022", bd=0, font=("Lato", 12, "bold"))
        log_card.pack(padx=12, pady=6, fill=tk.X)
        btns = tk.Frame(log_card, bg="#052022")
        btns.pack(padx=8, pady=6)
        for amt in (50, 100, 250, 500):
            b = tk.Button(btns, text=f"+{amt} ml", command=lambda a=amt: self.log_and_refresh(a), bg="#0BBEE6", fg="black")
            b.pack(side=tk.LEFT, padx=4, pady=4)

        custom_frame = tk.Frame(log_card, bg="#052022")
        custom_frame.pack(padx=8, pady=6, fill=tk.X)
        self.entry_custom = tk.Entry(custom_frame)
        self.entry_custom.pack(side=tk.LEFT, padx=4, pady=4, fill=tk.X, expand=True)
        tk.Button(custom_frame, text="Log", command=self.log_custom).pack(side=tk.LEFT, padx=4)

        # Reminders
        rem_card = tk.LabelFrame(left, text="Reminders", fg="#DFF9FF", bg="#052022", bd=0, font=("Lato", 12, "bold"))
        rem_card.pack(padx=12, pady=6, fill=tk.X)
        tk.Label(rem_card, text="Interval (mins):", bg="#052022", fg="#CFF8FF").pack(anchor='w', padx=8)
        self.spin_interval = tk.Spinbox(rem_card, from_=15, to=240, increment=5, width=6)
        self.spin_interval.pack(padx=8, pady=4, anchor='w')
        btns_rem = tk.Frame(rem_card, bg="#052022")
        btns_rem.pack(padx=8, pady=6, fill=tk.X)
        tk.Button(btns_rem, text="Start", bg="#00E5FF", command=self.start_reminders).pack(side=tk.LEFT, padx=4)
        tk.Button(btns_rem, text="Stop", bg="#FF6B6B", command=self.stop_reminders).pack(side=tk.LEFT, padx=4)

        # Export & Settings
        util_card = tk.LabelFrame(left, text="Utilities", fg="#DFF9FF", bg="#052022", bd=0, font=("Lato", 12, "bold"))
        util_card.pack(padx=12, pady=6, fill=tk.X)
        tk.Button(util_card, text="Export logs to CSV", command=self.export_csv, bg="#3CE6A6").pack(padx=8, pady=6, fill=tk.X)
        tk.Button(util_card, text="Show Badges", command=self.show_badges, bg="#FFE26E").pack(padx=8, pady=6, fill=tk.X)

    def _build_main_panel(self):
        main = tk.Frame(self, bg="#071927")
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Top info: goal and progress
        top = tk.Frame(main, bg="#071927")
        top.pack(fill=tk.X)
        self.lbl_goal = tk.Label(top, text="Goal: -- ml", bg="#071927", fg="#CFF8FF", font=("Montserrat", 18, "bold"))
        self.lbl_goal.pack(side=tk.LEFT, padx=6)
        self.lbl_today = tk.Label(top, text="Today: 0 ml", bg="#071927", fg="#A9F0FF", font=("Lato", 12))
        self.lbl_today.pack(side=tk.LEFT, padx=24)

        # canvas area for progress ring and weekly chart
        canvas_frame = tk.Frame(main, bg="#071927")
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=12)

        left_canvas = tk.Canvas(canvas_frame, width=380, height=380, bg="#071927", highlightthickness=0)
        left_canvas.pack(side=tk.LEFT, padx=12, pady=6)
        self.left_canvas = left_canvas

        right_canvas = tk.Canvas(canvas_frame, width=520, height=380, bg="#071927", highlightthickness=0)
        right_canvas.pack(side=tk.LEFT, padx=12, pady=6, fill=tk.BOTH, expand=True)
        self.right_canvas = right_canvas

        # Buttons below
        bottom = tk.Frame(main, bg="#071927")
        bottom.pack(fill=tk.X, pady=6)
        tk.Button(bottom, text="Open Insights", command=self.open_insights, bg="#00E5FF").pack(side=tk.LEFT, padx=8)
        tk.Button(bottom, text="Eco Mode", command=self.open_eco_mode, bg="#4EEAF6").pack(side=tk.LEFT, padx=8)
        tk.Button(bottom, text="AI Suggest", command=self.show_ai_suggestion, bg="#8E6CFF").pack(side=tk.LEFT, padx=8)

    def _load_profile_state(self):
        if self.profile:
            self.lbl_profile.config(text=f"{self.profile['name']}\nAge: {self.profile['age']}\nWeight: {self.profile['weight_kg']} kg\nActivity: {self.profile['activity']}")
        else:
            self.lbl_profile.config(text="No profile set")

    # ---------------------------
    # Actions
    # ---------------------------
    def open_profile_dialog(self):
        dlg = ProfileDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            name, age, weight, activity = dlg.result
            set_profile(name, age, weight, activity)
            self.profile = get_profile()
            self._load_profile_state()
            self.refresh_ui()

    def log_and_refresh(self, ml):
        log_water_ml(ml)
        messagebox.showinfo("Logged", f"Logged {ml} ml")
        self.refresh_ui()

    def log_custom(self):
        val = self.entry_custom.get().strip()
        try:
            amt = int(val)
            if amt <= 0:
                raise ValueError()
        except:
            messagebox.showerror("Invalid", "Enter a positive integer for ml")
            return
        self.log_and_refresh(amt)
        self.entry_custom.delete(0, tk.END)

    def refresh_ui(self):
        # update profile & goals
        self.profile = get_profile()
        if self.profile:
            goal = calculate_goal_ml(self.profile['weight_kg'], age=self.profile['age'], activity=self.profile['activity'])
        else:
            goal = 2000
        today = get_today_total()
        self.lbl_goal.config(text=f"Goal: {goal} ml")
        self.lbl_today.config(text=f"Today: {today} ml")
        # draw progress ring
        self.draw_progress_ring(self.left_canvas, consumed=today, goal=goal)
        # weekly chart
        totals = get_totals_for_days(7)
        self.draw_weekly_chart(self.right_canvas, totals, goal)
        # update badges label left
        if self.profile:
            self.lbl_profile.config(text=f"{self.profile['name']}\nAge: {self.profile['age']}\nWeight: {self.profile['weight_kg']} kg\nActivity: {self.profile['activity']}")

    def draw_progress_ring(self, canvas, consumed, goal):
        canvas.delete("all")
        # ring background
        cx, cy = 190, 190
        r = 120
        canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#04262B", outline="")
        # progress arc
        pct = min(1.0, consumed/goal) if goal>0 else 0
        extent = pct * 360
        # gradient-like using multiple arcs
        canvas.create_oval(cx-90, cy-90, cx+90, cy+90, outline="#0C5C6A", width=16)
        canvas.create_arc(cx-90, cy-90, cx+90, cy+90, start=90, extent=-extent, style='arc', outline="#00E5FF", width=16)
        # center text
        canvas.create_text(cx, cy-10, text=f"{int(pct*100)}%", fill="#CFF8FF", font=("Montserrat", 24, "bold"))
        canvas.create_text(cx, cy+24, text=f"{consumed} / {goal} ml", fill="#AEEFF6", font=("Lato", 12))

        # small quick log buttons drawn near ring
        btn_y = cy + r + 20
        x_start = cx - 120
        for i, amt in enumerate((50, 100, 250, 500)):
            x = x_start + i * 70
            # clickable rectangles - map clicks handled by binding
            rect = canvas.create_rectangle(x-28, btn_y-18, x+28, btn_y+18, fill="#092C30", outline="#00AFC0")
            text = canvas.create_text(x, btn_y, text=f"+{amt}", fill="#00E5FF")
            canvas.tag_bind(rect, "<Button-1>", lambda e, a=amt: self.log_and_refresh(a))
            canvas.tag_bind(text, "<Button-1>", lambda e, a=amt: self.log_and_refresh(a))

    def draw_weekly_chart(self, canvas, totals, goal):
        canvas.delete("all")
        w = int(canvas['width'])
        h = int(canvas['height'])
        margin = 40
        chart_w = w - 2*margin
        chart_h = h - 100
        left = margin
        top = 40
        # title
        canvas.create_text(w//2, 20, text="Weekly Hydration (ml)", fill="#CFF8FF", font=("Montserrat", 14, "bold"))
        # bars
        max_val = max(goal, max(t['total_ml'] for t in totals)+1)
        bar_w = chart_w / len(totals) * 0.6
        spacing = chart_w / len(totals)
        for i, t in enumerate(totals):
            x = left + spacing*i + spacing*0.2
            bar_h = (t['total_ml'] / max_val) * chart_h
            canvas.create_rectangle(x, top+chart_h-bar_h, x+bar_w, top+chart_h, fill="#00CFEA", outline="")
            # day label
            canvas.create_text(x+bar_w/2, top+chart_h+14, text=t['date'].strftime("%a")[0], fill="#BFF3F7")
            canvas.create_text(x+bar_w/2, top+chart_h-bar_h-10, text=str(int(t['total_ml'])), fill="#DFF9FF", font=("Lato", 8))

        # goal line
        goal_y = top + chart_h - (goal / max_val) * chart_h
        canvas.create_line(left, goal_y, left+chart_w, goal_y, dash=(4,4), fill="#89F9FF")
        canvas.create_text(left+chart_w-40, goal_y-8, text=f"Goal: {goal} ml", fill="#A9F0FF", font=("Lato", 9))

    def start_reminders(self):
        try:
            mins = int(self.spin_interval.get())
            if mins < 1:
                raise ValueError()
        except:
            messagebox.showerror("Invalid", "Set interval in minutes (>=1)")
            return
        self.reminder_interval_min = mins
        self.reminder_enabled = True
        self.schedule_next_reminder()
        messagebox.showinfo("Reminders", f"Reminders started every {mins} minutes")

    def stop_reminders(self):
        self.reminder_enabled = False
        if self.reminder_job:
            self.after_cancel(self.reminder_job)
            self.reminder_job = None
        messagebox.showinfo("Reminders", "Reminders stopped")

    def schedule_next_reminder(self):
        if not self.reminder_enabled:
            return
        # adapt interval slightly using predictor
        adj = predictor_adjustment()
        interval_ms = int(self.reminder_interval_min * 60 * 1000 / adj)
        # schedule
        if self.reminder_job:
            self.after_cancel(self.reminder_job)
        self.reminder_job = self.after(interval_ms, self.show_reminder)

    def show_reminder(self):
        today_total = get_today_total()
        profile = get_profile()
        if profile:
            goal = calculate_goal_ml(profile['weight_kg'], age=profile['age'], activity=profile['activity'])
        else:
            goal = 2000
        pct = int(min(100, (today_total/goal)*100)) if goal>0 else 0
        if pct >= 100:
            msg = "You reached your goal! Great job! 🎉"
        else:
            msg = f"Time to sip — you're at {pct}% of your daily goal."
        # popup
        popup = tk.Toplevel(self)
        popup.title("Water Buddy Reminder")
        popup.geometry("320x140")
        popup.configure(bg="#062028")
        tk.Label(popup, text="Water Buddy", bg="#062028", fg="#00E5FF", font=("Montserrat", 14, "bold")).pack(pady=(8,6))
        tk.Label(popup, text=msg, bg="#062028", fg="#E6FBFF").pack(pady=(0,12))
        btnf = tk.Frame(popup, bg="#062028")
        btnf.pack(pady=6)
        tk.Button(btnf, text="Log 250 ml", command=lambda: (log_water_ml(250), popup.destroy(), self.refresh_ui())).pack(side=tk.LEFT, padx=6)
        tk.Button(btnf, text="Snooze 10 min", command=lambda: (popup.destroy(), self.snooze(10))).pack(side=tk.LEFT, padx=6)
        # schedule next reminder
        self.schedule_next_reminder()

    def snooze(self, minutes):
        if self.reminder_job:
            self.after_cancel(self.reminder_job)
            self.reminder_job = None
        self.reminder_job = self.after(minutes * 60 * 1000, self.show_reminder)

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not path:
            return
        export_logs_csv(path)
        messagebox.showinfo("Export", f"Logs exported to {path}")

    def open_insights(self):
        # simple insights window with some stats
        w = tk.Toplevel(self)
        w.title("Daily Insights")
        w.geometry("560x420")
        w.configure(bg="#041A1D")
        profile = get_profile()
        if not profile:
            tk.Label(w, text="No profile set yet. Set your profile to get insights.", bg="#041A1D", fg="#CFF8FF").pack(padx=12, pady=12)
            return
        goal = calculate_goal_ml(profile['weight_kg'], age=profile['age'], activity=profile['activity'])
        totals = get_totals_for_days(14)
        avg = sum(t['total_ml'] for t in totals)/len(totals)
        lbl = tk.Label(w, text=f"14-day average intake: {int(avg)} ml\nDaily goal: {goal} ml", bg="#041A1D", fg="#E8FFFF", font=("Lato", 12))
        lbl.pack(padx=12, pady=12)
        # small chart canvas
        c = tk.Canvas(w, width=520, height=220, bg="#041A1D", highlightthickness=0)
        c.pack(padx=12, pady=6)
        # draw sparkline
        mx = max(max(t['total_ml'] for t in totals), goal)
        left = 20; top = 20; cw = 480; ch = 160
        points = []
        for i, t in enumerate(totals):
            x = left + (i/(len(totals)-1)) * cw
            y = top + ch - (t['total_ml']/mx)*ch
            points.append((x,y))
        for i in range(len(points)-1):
            c.create_line(points[i][0], points[i][1], points[i+1][0], points[i+1][1], fill="#0DE7FF", width=2)
        # goal line
        gy = top + ch - (goal/mx)*ch
        c.create_line(left, gy, left+cw, gy, dash=(3,3), fill="#89F9FF")
        # badges
        bdg = get_badges()
        tk.Label(w, text="Badges earned:", bg="#041A1D", fg="#CFF8FF").pack(anchor='w', padx=12)
        for name, earned in bdg:
            tk.Label(w, text=f"- {name} (earned {earned[:10]})", bg="#041A1D", fg="#AEEFF6").pack(anchor='w', padx=24)

    def open_eco_mode(self):
        profile = get_profile()
        if not profile:
            messagebox.showinfo("Eco Mode", "Set profile first.")
            return
        totals = get_totals_for_days(7)
        total_week = sum(t['total_ml'] for t in totals)
        bottles_saved = estimate_bottles_saved(total_week, bottle_size_ml=500)
        # show window
        w = tk.Toplevel(self)
        w.title("Eco Mode")
        w.geometry("420x300")
        w.configure(bg="#052022")
        tk.Label(w, text="Eco Mode — Your environmental impact", bg="#052022", fg="#AEEFF6", font=("Montserrat", 12, "bold")).pack(pady=8)
        tk.Label(w, text=f"This week you consumed {int(total_week)} ml", bg="#052022", fg="#DFF8FF").pack(pady=4)
        tk.Label(w, text=f"Equivalent refillable bottles used: {bottles_saved:.1f}", bg="#052022", fg="#CFF8FF", font=("Lato", 12, "bold")).pack(pady=8)
        tk.Label(w, text="Tip: Use a 500 ml refillable bottle to reduce single-use plastic.", bg="#052022", fg="#BFEFF6").pack(pady=6)
        tk.Button(w, text="Close", command=w.destroy, bg="#00E5FF").pack(pady=12)

    def show_badges(self):
        bdg = get_badges()
        txt = "\n".join([f"{name} — earned at {earned}" for name, earned in bdg]) if bdg else "No badges yet."
        messagebox.showinfo("Badges", txt)

    def show_ai_suggestion(self):
        # quick suggestion based on predictor
        adj = predictor_adjustment()
        if adj > 1.05:
            messagebox.showinfo("AI Suggestion", "We noticed your recent intake is low. We'll nudge you more often and suggest adding small 250 ml logs after chores.")
        else:
            messagebox.showinfo("AI Suggestion", "You're doing well! Maintain your streak and try eco mode for sustainability tips.")

# ---------------------------
# Dialogs
# ---------------------------
class ProfileDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Profile")
        self.geometry("320x240")
        self.configure(bg="#052022")
        self.result = None

        tk.Label(self, text="Name:", bg="#052022", fg="#CFF8FF").pack(anchor='w', padx=12, pady=(12,2))
        self.entry_name = tk.Entry(self)
        self.entry_name.pack(fill=tk.X, padx=12)

        tk.Label(self, text="Age:", bg="#052022", fg="#CFF8FF").pack(anchor='w', padx=12, pady=(8,2))
        self.entry_age = tk.Entry(self)
        self.entry_age.pack(fill=tk.X, padx=12)

        tk.Label(self, text="Weight (kg):", bg="#052022", fg="#CFF8FF").pack(anchor='w', padx=12, pady=(8,2))
        self.entry_weight = tk.Entry(self)
        self.entry_weight.pack(fill=tk.X, padx=12)

        tk.Label(self, text="Activity (low/normal/high):", bg="#052022", fg="#CFF8FF").pack(anchor='w', padx=12, pady=(8,2))
        self.entry_activity = tk.Entry(self)
        self.entry_activity.insert(0, "normal")
        self.entry_activity.pack(fill=tk.X, padx=12)

        btnf = tk.Frame(self, bg="#052022")
        btnf.pack(pady=12)
        tk.Button(btnf, text="Save", command=self.on_save, bg="#00E5FF").pack(side=tk.LEFT, padx=6)
        tk.Button(btnf, text="Cancel", command=self.destroy, bg="#FF6B6B").pack(side=tk.LEFT)

    def on_save(self):
        name = self.entry_name.get().strip() or "You"
        try:
            age = int(self.entry_age.get().strip())
            weight = float(self.entry_weight.get().strip())
        except:
            messagebox.showerror("Invalid", "Enter valid numeric age and weight.")
            return
        activity = self.entry_activity.get().strip().lower() or "normal"
        if activity not in ('low','normal','high'):
            messagebox.showerror("Invalid", "Activity must be low, normal or high")
            return
        self.result = (name, age, weight, activity)
        self.destroy()

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    app = WaterBuddyApp()
    app.mainloop()
