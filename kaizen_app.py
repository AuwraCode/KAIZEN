import tkinter as tk
from tkinter import messagebox
import shutil
import os
import sys
import time
import threading
import subprocess
import webbrowser
import json
import queue
import random
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- CONFIGURATION & CONSTANTS ---
COLORS = {
    "bg": "#121212",
    "fg": "#E0E0E0",
    "accent": "#8A56CC",    # PURPLE (Royalty/Wisdom)
    "alert": "#FF5252",     # RED (Urgency)
    "break": "#29B6F6",     # BLUE (Calm)
    "panel": "#1E1E1E",
    "success": "#00C853",   # GREEN (Growth)
    "hover": "#333333",
    "input": "#2C2C2C"
}

FONTS = {
    "main": ("Segoe UI", 9),
    "bold": ("Segoe UI", 9, "bold"),
    "timer": ("Consolas", 22, "bold"), # Larger, clearer timer
    "small": ("Segoe UI", 8),
    "icon": ("Segoe UI", 11, "bold")
}

QUOTES = [
    "We suffer more often in imagination than in reality. – Seneca",
    "Discipline is doing what you hate to do, but doing it like you love it.",
    "Waste no more time arguing what a good man should be. Be one. – Aurelius",
    "Focus on the process, not the outcome. – Kaizen",
    "You have power over your mind - not outside events. – Aurelius"
]

CONFIG_FILE = Path.home() / ".kaizen_hud_config.json"

class Config:
    def __init__(self):
        self.watch_paths = [str(Path.home() / "Downloads")]
        self.monk_urls = ["https://github.com", "https://chatgpt.com"]
        self.extensions = {
            "Images": [".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif"],
            "Documents": [".pdf", ".docx", ".txt", ".xlsx", ".csv", ".pptx", ".md"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".iso"],
            "Code": [".py", ".ipynb", ".js", ".cpp", ".html", ".css", ".json", ".sql"],
            "Media": [".mp3", ".wav", ".mp4", ".mkv"],
            "Installers": [".exe", ".msi", ".AppImage", ".deb"]
        }
        self.pomo_work = 25
        self.pomo_break = 5
        self.autostart = False
        # ROI Stats
        self.stats = {
            "files_moved": 0,
            "minutes_focused": 0,
            "sessions_completed": 0
        }
        self.load()

    def to_dict(self):
        return {
            "watch_paths": self.watch_paths,
            "monk_urls": self.monk_urls,
            "pomo_work": self.pomo_work,
            "pomo_break": self.pomo_break,
            "autostart": self.autostart,
            "stats": self.stats
        }

    def save(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.to_dict(), f, indent=4)
        except Exception as e:
            print(f"Config Save Error: {e}")

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    if "watch_paths" in data: self.watch_paths = data["watch_paths"]
                    if "monk_urls" in data: self.monk_urls = data["monk_urls"]
                    if "pomo_work" in data: self.pomo_work = data.get("pomo_work", 25)
                    if "pomo_break" in data: self.pomo_break = data.get("pomo_break", 5)
                    if "autostart" in data: self.autostart = data.get("autostart", False)
                    if "stats" in data: self.stats = data.get("stats", self.stats)
            except Exception as e:
                print(f"Config Load Error: {e}")

    def increment_stat(self, key, value=1):
        if key in self.stats:
            self.stats[key] += value
            self.save()

CONFIG = Config()

# --- BACKEND (THREAD-SAFE) ---
class AutomationService:
    def __init__(self, gui_queue):
        self.gui_queue = gui_queue
        self.observer = None
        self._is_running = False

    def start_watching(self):
        if self._is_running: self.stop_watching()
        self.observer = Observer()
        handler = FileHandler(self.gui_queue)
        
        valid_paths = 0
        for path_str in CONFIG.watch_paths:
            path = Path(path_str)
            if path.exists() and path.is_dir():
                try:
                    self.observer.schedule(handler, str(path), recursive=False)
                    valid_paths += 1
                except Exception as e:
                    print(f"Error scheduling {path}: {e}")
        
        if valid_paths > 0:
            self.observer.start()
            self._is_running = True
            print(f"Automation started on {valid_paths} paths.")

    def stop_watching(self):
        if self._is_running and self.observer:
            self.observer.stop()
            self.observer.join()
            self._is_running = False

class FileHandler(FileSystemEventHandler):
    def __init__(self, gui_queue):
        self.gui_queue = gui_queue

    def on_created(self, event):
        if event.is_directory: return
        # Ignore temp files from browsers
        if event.src_path.endswith(('.crdownload', '.part', '.tmp', '.download')):
            return
        threading.Thread(target=self.process_file, args=(Path(event.src_path),)).start()

    def process_file(self, file_path: Path):
        # Wait for file unlock (simple retry logic)
        retries = 5
        while retries > 0:
            try:
                if not file_path.exists(): return
                
                # Check for open handle / size stability could be added here
                # For now, just a slightly longer delay for the OS to release the handle
                time.sleep(1.5) 
                
                # Categorize
                moved = False
                for category, exts in CONFIG.extensions.items():
                    if file_path.suffix.lower() in exts:
                        dest_dir = Path.home() / "Desktop" / category
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        
                        final_path = dest_dir / file_path.name
                        counter = 1
                        while final_path.exists():
                            final_path = dest_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                            counter += 1
                        
                        shutil.move(str(file_path), str(final_path))
                        
                        CONFIG.increment_stat("files_moved")
                        self.gui_queue.put(("notify", f"Kaizen: Moved {file_path.name} -> {category}"))
                        moved = True
                        break
                
                if moved: break
            except PermissionError:
                retries -= 1
                time.sleep(2)
            except Exception as e:
                print(f"Error processing file: {e}")
                break

# --- SETTINGS WINDOW ---
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, automator, refresh_callback):
        super().__init__(parent)
        self.automator = automator
        self.refresh_callback = refresh_callback
        self.title("Kaizen Config")
        self.configure(bg=COLORS["bg"])
        self.attributes("-topmost", True)
        self.geometry("320x400")
        self._build_ui()

    def _build_ui(self):
        pad = 12
        
        tk.Label(self, text="WATCH PATHS (;)", bg=COLORS["bg"], fg="#888", font=FONTS["small"]).pack(anchor="w", padx=pad, pady=(pad, 2))
        self.ent_paths = tk.Entry(self, bg=COLORS["input"], fg=COLORS["fg"], bd=1, relief="solid", insertbackground="white")
        self.ent_paths.insert(0, ";".join(CONFIG.watch_paths))
        self.ent_paths.pack(fill="x", padx=pad)

        tk.Label(self, text="MONK URLS (;)", bg=COLORS["bg"], fg="#888", font=FONTS["small"]).pack(anchor="w", padx=pad, pady=(10, 2))
        self.ent_urls = tk.Entry(self, bg=COLORS["input"], fg=COLORS["fg"], bd=1, relief="solid", insertbackground="white")
        self.ent_urls.insert(0, ";".join(CONFIG.monk_urls))
        self.ent_urls.pack(fill="x", padx=pad)

        # Timer Settings
        frame_timer = tk.Frame(self, bg=COLORS["bg"])
        frame_timer.pack(fill="x", padx=pad, pady=10)
        
        tk.Label(frame_timer, text="WORK (m)", bg=COLORS["bg"], fg=COLORS["accent"], font=FONTS["small"]).grid(row=0, column=0, padx=5)
        tk.Label(frame_timer, text="BREAK (m)", bg=COLORS["bg"], fg=COLORS["break"], font=FONTS["small"]).grid(row=0, column=1, padx=5)
        
        self.ent_work = tk.Entry(frame_timer, width=5, bg=COLORS["input"], fg=COLORS["fg"], insertbackground="white")
        self.ent_work.insert(0, str(CONFIG.pomo_work))
        self.ent_work.grid(row=1, column=0, padx=5)
        
        self.ent_break = tk.Entry(frame_timer, width=5, bg=COLORS["input"], fg=COLORS["fg"], insertbackground="white")
        self.ent_break.insert(0, str(CONFIG.pomo_break))
        self.ent_break.grid(row=1, column=1, padx=5)

        # Stats Display
        tk.Label(self, text="--- ROI STATS ---", bg=COLORS["bg"], fg="#555", font=FONTS["small"]).pack(pady=(15, 5))
        stats_frame = tk.Frame(self, bg=COLORS["panel"], padx=10, pady=10)
        stats_frame.pack(fill="x", padx=pad)
        
        s_files = CONFIG.stats.get("files_moved", 0)
        s_mins = CONFIG.stats.get("minutes_focused", 0)
        
        tk.Label(stats_frame, text=f"📂 Files Organized: {s_files}", bg=COLORS["panel"], fg=COLORS["fg"], font=FONTS["small"]).pack(anchor="w")
        tk.Label(stats_frame, text=f"🧠 Focus Minutes: {s_mins}", bg=COLORS["panel"], fg=COLORS["fg"], font=FONTS["small"]).pack(anchor="w")

        # Save
        self.btn_save = tk.Button(self, text="APPLY CHANGES", bg=COLORS["accent"], fg="black", font=FONTS["bold"], command=self.save_config)
        self.btn_save.pack(side="bottom", fill="x", padx=pad, pady=pad)

    def save_config(self):
        CONFIG.watch_paths = [p.strip() for p in self.ent_paths.get().split(";") if p.strip()]
        CONFIG.monk_urls = [u.strip() for u in self.ent_urls.get().split(";") if u.strip()]
        try:
            CONFIG.pomo_work = int(self.ent_work.get())
            CONFIG.pomo_break = int(self.ent_break.get())
        except ValueError: pass
        
        CONFIG.save()
        self.automator.start_watching()
        self.refresh_callback()
        self.destroy()

# --- NOTIFICATION ---
class CustomNotification(tk.Toplevel):
    def __init__(self, parent, message, color=COLORS["accent"]):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=COLORS["panel"])
        
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        w, h = 320, 50
        x = ws - w - 20
        y = hs - h - 60
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        # Border strip
        tk.Frame(self, bg=color, width=5).pack(side="left", fill="y")
        
        tk.Label(self, text=message, bg=COLORS["panel"], fg=COLORS["fg"], 
                 font=FONTS["small"], wraplength=300, justify="left").pack(side="left", padx=12)
        
        # Auto fade out
        self.after(4000, self.destroy)

# --- MAIN HUD ---
class KaizenHUD(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        
        # Queue for thread-safe GUI updates
        self.gui_queue = queue.Queue()
        self.automator = AutomationService(self.gui_queue)
        
        self.pomo_active = False
        self.pomo_state = "WORK" # WORK or BREAK
        self.pomo_seconds_left = CONFIG.pomo_work * 60
        self.settings_window_ref = None

        self._setup_window()
        self._setup_dashboard()
        
        # Start Automation
        self.automator.start_watching()
        
        # Start Queue Checker
        self.check_queue()
        
        self.deiconify()
        self.show_notification("Kaizen Systems Online.", COLORS["success"])

    def _setup_window(self):
        self.overrideredirect(True)
        self.geometry("260x180")
        self.configure(bg=COLORS["bg"], highlightthickness=1, highlightbackground=COLORS["panel"])
        self.attributes("-topmost", True)
        
        # Center on screen
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = (ws - 260) // 2
        y = (hs - 180) // 2
        self.geometry(f"+{x}+{y}")

        # Dragging logic
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)

    def _setup_dashboard(self):
        # Header / Title Bar
        header = tk.Frame(self, bg=COLORS["panel"], height=25)
        header.pack(fill="x")
        
        tk.Label(header, text=" KAIZEN", bg=COLORS["panel"], fg=COLORS["accent"], font=FONTS["bold"]).pack(side="left")
        
        # Window Controls
        btn_close = tk.Label(header, text=" × ", bg=COLORS["panel"], fg="#666", font=FONTS["bold"], cursor="hand2")
        btn_close.pack(side="right")
        btn_close.bind("<Button-1>", lambda e: self.quit_app())
        
        btn_min = tk.Label(header, text=" - ", bg=COLORS["panel"], fg="#666", font=FONTS["bold"], cursor="hand2")
        btn_min.pack(side="right")
        btn_min.bind("<Button-1>", lambda e: self.minimize_app())

        # Main Content
        self.content = tk.Frame(self, bg=COLORS["bg"])
        self.content.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.lbl_status = tk.Label(self.content, text="READY", font=FONTS["bold"], bg=COLORS["bg"], fg="#555")
        self.lbl_status.pack()
        
        self.lbl_timer = tk.Label(self.content, text="00:00", font=FONTS["timer"], bg=COLORS["bg"], fg=COLORS["fg"])
        self.lbl_timer.pack(pady=2)
        
        self.btn_action = tk.Button(self.content, text="INITIATE MONK MODE", 
                                  bg=COLORS["panel"], fg=COLORS["accent"], 
                                  activebackground=COLORS["accent"], activeforeground="black",
                                  bd=0, font=FONTS["bold"], cursor="hand2",
                                  command=self.toggle_monk_mode, pady=5)
        self.btn_action.pack(fill="x", pady=10)
        
        # Footer
        footer = tk.Label(self, text="[SETTINGS]", bg=COLORS["bg"], fg="#444", font=FONTS["small"], cursor="hand2")
        footer.pack(side="bottom", pady=5)
        footer.bind("<Button-1>", lambda e: self.open_settings())

    # --- LOGIC ---
    def check_queue(self):
        try:
            while True:
                msg_type, content = self.gui_queue.get_nowait()
                if msg_type == "notify":
                    self.show_notification(content)
        except queue.Empty:
            pass
        self.after(100, self.check_queue)

    def toggle_monk_mode(self):
        if not self.pomo_active:
            self.start_monk_mode()
        else:
            self.stop_monk_mode()

    def start_monk_mode(self):
        self.pomo_active = True
        self.pomo_state = "WORK"
        self.pomo_seconds_left = CONFIG.pomo_work * 60
        self.update_timer_display()
        
        # Kaizen Actions
        quote = random.choice(QUOTES)
        self.show_notification(quote, COLORS["accent"])
        
        # Launch tools
        for url in CONFIG.monk_urls:
            webbrowser.open(url)
        
        # Smart VS Code Launch
        if shutil.which("code"):
            subprocess.Popen(["code"], shell=True)
        else:
            print("VS Code not found in PATH")

        self.btn_action.configure(text="STOP SESSION", fg=COLORS["alert"])
        self.tick_timer()

    def stop_monk_mode(self):
        self.pomo_active = False
        self.btn_action.configure(text="INITIATE MONK MODE", fg=COLORS["accent"])
        self.lbl_status.configure(text="READY", fg="#555")
        self.lbl_timer.configure(text="00:00", fg=COLORS["fg"])

    def tick_timer(self):
        if self.pomo_active:
            if self.pomo_seconds_left > 0:
                self.pomo_seconds_left -= 1
                
                # ROI Tracking: Every minute of work counts
                if self.pomo_state == "WORK" and self.pomo_seconds_left % 60 == 0:
                    CONFIG.increment_stat("minutes_focused")
                
                self.update_timer_display()
                self.after(1000, self.tick_timer)
            else:
                self.switch_state()

    def switch_state(self):
        self.bell() # System sound
        if self.pomo_state == "WORK":
            CONFIG.increment_stat("sessions_completed")
            self.show_notification("Focus Complete. Recover.", COLORS["success"])
            self.pomo_state = "BREAK"
            self.pomo_seconds_left = CONFIG.pomo_break * 60
        else:
            self.show_notification("Break Over. Engage.", COLORS["alert"])
            self.pomo_state = "WORK"
            self.pomo_seconds_left = CONFIG.pomo_work * 60
        self.tick_timer()

    def update_timer_display(self):
        mins, secs = divmod(self.pomo_seconds_left, 60)
        self.lbl_timer.configure(text=f"{mins:02}:{secs:02}")
        if self.pomo_state == "WORK":
            self.lbl_status.configure(text="/// DEEP WORK ///", fg=COLORS["accent"])
            self.lbl_timer.configure(fg=COLORS["accent"])
        else:
            self.lbl_status.configure(text="/// RECOVERY ///", fg=COLORS["break"])
            self.lbl_timer.configure(fg=COLORS["break"])

    def show_notification(self, msg, color=COLORS["accent"]):
        CustomNotification(self, msg, color)

    def open_settings(self):
        if not self.settings_window_ref or not self.settings_window_ref.winfo_exists():
            self.settings_window_ref = SettingsWindow(self, self.automator, lambda: None)

    # --- WINDOW OPS ---
    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        x = self.winfo_x() + (event.x - self.x)
        y = self.winfo_y() + (event.y - self.y)
        self.geometry(f"+{x}+{y}")

    def minimize_app(self):
        # Reliable minimization for borderless windows
        self.overrideredirect(False) 
        self.iconify()
        self.bind("<Map>", self.on_restore)

    def on_restore(self, event):
        if self.state() == "normal":
            self.overrideredirect(True)
            self.unbind("<Map>")

    def quit_app(self):
        self.automator.stop_watching()
        self.destroy()

if __name__ == "__main__":
    app = KaizenHUD()
    app.mainloop()