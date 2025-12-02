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
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- CONFIGURATION & CONSTANTS ---
COLORS = {
    "bg": "#121212",
    "fg": "#E0E0E0",
    "accent": "#8A56CC",    # PURPLE
    "alert": "#FF5252",     # Red
    "break": "#29B6F6",     # Blue
    "panel": "#1E1E1E",
    "hover": "#333333",
    "input": "#2C2C2C"
}

FONTS = {
    "main": ("Arial", 9),
    "bold": ("Arial", 9, "bold"),
    "timer": ("Courier New", 16, "bold"),
    "small": ("Arial", 8),
    "icon": ("Arial", 11, "bold")
}

CONFIG_FILE = Path.home() / ".kaizen_hud_config.json"

class Config:
    def __init__(self):
        # Default values
        self.watch_paths = [str(Path.home() / "Downloads")]
        self.monk_urls = [
            "https://www.kaggle.com",
            "https://gemini.google.com",
            "https://renshuu.org"
        ]
        self.extensions = {
            "Images": [".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif"],
            "Documents": [".pdf", ".docx", ".txt", ".xlsx", ".csv", ".pptx", ".md"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".iso"],
            "Code": [".py", ".ipynb", ".js", ".cpp", ".html", ".css", ".json", ".sql"],
            "Media": [".mp3", ".wav", ".mp4", ".mkv", ".mov", ".avi"],
            "Executables": [".exe", ".msi", ".AppImage", ".deb", ".rpm"]
        }
        self.pomo_work = 25
        self.pomo_break = 5
        self.autostart = False
        
        # Load from file on init
        self.load()

    def to_dict(self):
        return {
            "watch_paths": self.watch_paths,
            "monk_urls": self.monk_urls,
            "pomo_work": self.pomo_work,
            "pomo_break": self.pomo_break,
            "autostart": self.autostart
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
                    # Update only existing keys to keep defaults safe
                    if "watch_paths" in data: self.watch_paths = data["watch_paths"]
                    if "monk_urls" in data: self.monk_urls = data["monk_urls"]
                    if "pomo_work" in data: self.pomo_work = data.get("pomo_work", 25)
                    if "pomo_break" in data: self.pomo_break = data.get("pomo_break", 5)
                    if "autostart" in data: self.autostart = data.get("autostart", False)
            except Exception as e:
                print(f"Config Load Error: {e}")

CONFIG = Config()

# --- UTILS ---
class AutoStartManager:
    @staticmethod
    def set_autostart(enable: bool):
        app_path = os.path.abspath(sys.argv[0])
        system = sys.platform
        try:
            if system == "win32":
                startup_folder = os.path.join(os.getenv("APPDATA"), r"Microsoft\Windows\Start Menu\Programs\Startup")
                link_path = os.path.join(startup_folder, "KaizenHUD.bat")
                if enable:
                    with open(link_path, "w") as f:
                        f.write(f'@echo off\nstart "" pythonw "{app_path}"')
                else:
                    if os.path.exists(link_path): os.remove(link_path)
            elif system.startswith("linux"):
                autostart_dir = Path.home() / ".config" / "autostart"
                autostart_dir.mkdir(parents=True, exist_ok=True)
                desktop_file = autostart_dir / "kaizen_hud.desktop"
                if enable:
                    content = f"""[Desktop Entry]
Type=Application
Name=KaizenHUD
Exec=/usr/bin/python3 "{app_path}"
X-GNOME-Autostart-enabled=true
NoDisplay=false
Hidden=false
"""
                    with open(desktop_file, "w") as f:
                        f.write(content)
                else:
                    if desktop_file.exists(): desktop_file.unlink()
            CONFIG.autostart = enable
        except Exception as e:
            print(f"Autostart Error: {e}")

# --- BACKEND ---
class BatchNotifier:
    def __init__(self, callback):
        self.callback = callback
        self.files = []
        self.timer = None
        self.lock = threading.Lock()

    def add_file(self, filename, category):
        with self.lock:
            self.files.append((filename, category))
            if self.timer: self.timer.cancel()
            self.timer = threading.Timer(1.5, self._flush)
            self.timer.start()

    def _flush(self):
        with self.lock:
            if not self.files: return
            count = len(self.files)
            first_file, cat = self.files[0]
            msg = f"Moved: {first_file} -> [{cat}]" if count == 1 else f"Moved: {first_file} + {count-1} others -> [{cat}]"
            self.callback(msg)
            self.files = []

class FileHandler(FileSystemEventHandler):
    def __init__(self, batch_notifier):
        self.notifier = batch_notifier

    def on_created(self, event):
        if event.is_directory: return
        threading.Thread(target=self.process_file, args=(Path(event.src_path),)).start()

    def process_file(self, file_path: Path):
        time.sleep(1.0)
        if not file_path.exists(): return
        for category, exts in CONFIG.extensions.items():
            if file_path.suffix.lower() in exts:
                try:
                    dest_dir = Path.home() / "Desktop" / category
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    final_path = dest_dir / file_path.name
                    counter = 1
                    while final_path.exists():
                        final_path = dest_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                        counter += 1
                    shutil.move(str(file_path), str(final_path))
                    self.notifier.add_file(file_path.name, category)
                    return
                except Exception: pass

class AutomationService:
    def __init__(self, notify_callback):
        self.batcher = BatchNotifier(notify_callback)
        self.handler = FileHandler(self.batcher)
        self.observer = None
        self._is_running = False

    def start_watching(self):
        if self._is_running: self.stop_watching()
        self.observer = Observer()
        valid_paths = 0
        for path_str in CONFIG.watch_paths:
            path = Path(path_str)
            if path.exists() and path.is_dir():
                self.observer.schedule(self.handler, str(path), recursive=False)
                valid_paths += 1
        if valid_paths > 0:
            self.observer.start()
            self._is_running = True

    def stop_watching(self):
        if self._is_running and self.observer:
            self.observer.stop()
            self.observer.join()
            self._is_running = False

# --- SETTINGS WINDOW (NON-BLOCKING + PERSISTENCE) ---
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, automator, refresh_callback):
        super().__init__(parent)
        self.automator = automator
        self.refresh_callback = refresh_callback
        
        self.title("Config")
        self.geometry("300x340") 
        self.configure(bg=COLORS["bg"])
        self.attributes("-topmost", True)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self._build_ui()

    def _build_ui(self):
        pad = 15
        
        tk.Label(self, text="PATHS (;)", bg=COLORS["bg"], fg="#888", font=FONTS["small"]).pack(anchor="w", padx=pad, pady=(pad, 2))
        self.ent_paths = tk.Entry(self, bg=COLORS["input"], fg=COLORS["fg"], bd=1, relief="solid", insertbackground="white")
        self.ent_paths.insert(0, ";".join(CONFIG.watch_paths))
        self.ent_paths.pack(fill="x", padx=pad)

        tk.Label(self, text="URLS (;)", bg=COLORS["bg"], fg="#888", font=FONTS["small"]).pack(anchor="w", padx=pad, pady=(10, 2))
        self.ent_urls = tk.Entry(self, bg=COLORS["input"], fg=COLORS["fg"], bd=1, relief="solid", insertbackground="white")
        self.ent_urls.insert(0, ";".join(CONFIG.monk_urls))
        self.ent_urls.pack(fill="x", padx=pad)

        pomo_frame = tk.Frame(self, bg=COLORS["bg"])
        pomo_frame.pack(fill="x", padx=pad, pady=10)
        
        tk.Label(pomo_frame, text="WORK:", bg=COLORS["bg"], fg="#888", font=FONTS["small"]).pack(side="left")
        self.ent_work = tk.Entry(pomo_frame, width=4, bg=COLORS["input"], fg=COLORS["fg"], bd=1, relief="solid", insertbackground="white")
        self.ent_work.insert(0, str(CONFIG.pomo_work))
        self.ent_work.pack(side="left", padx=5)

        tk.Label(pomo_frame, text="BREAK:", bg=COLORS["bg"], fg="#888", font=FONTS["small"]).pack(side="left", padx=(10, 0))
        self.ent_break = tk.Entry(pomo_frame, width=4, bg=COLORS["input"], fg=COLORS["fg"], bd=1, relief="solid", insertbackground="white")
        self.ent_break.insert(0, str(CONFIG.pomo_break))
        self.ent_break.pack(side="left", padx=5)

        self.var_autostart = tk.BooleanVar(value=CONFIG.autostart)
        cb = tk.Checkbutton(self, text="RUN ON STARTUP", variable=self.var_autostart, 
                            bg=COLORS["bg"], fg=COLORS["accent"], selectcolor=COLORS["bg"], 
                            activebackground=COLORS["bg"], activeforeground=COLORS["accent"],
                            font=FONTS["small"])
        cb.pack(anchor="w", padx=pad)

        self.btn_save = tk.Button(self, text="SAVE", bg=COLORS["accent"], fg="black", font=FONTS["bold"], 
                  command=self.save_async)
        self.btn_save.pack(side="bottom", fill="x", padx=pad, pady=pad)

    def save_async(self):
        self.btn_save.configure(text="SAVING...", state="disabled")
        threading.Thread(target=self._save_logic, daemon=True).start()

    def _save_logic(self):
        CONFIG.watch_paths = [p.strip() for p in self.ent_paths.get().split(";") if p.strip()]
        CONFIG.monk_urls = [u.strip() for u in self.ent_urls.get().split(";") if u.strip()]
        try:
            CONFIG.pomo_work = int(self.ent_work.get())
            CONFIG.pomo_break = int(self.ent_break.get())
        except ValueError: pass
        
        CONFIG.autostart = self.var_autostart.get()
        AutoStartManager.set_autostart(CONFIG.autostart)
        
        # Save to JSON file
        CONFIG.save()
        
        self.automator.start_watching()
        self.after(0, self._finish_save)

    def _finish_save(self):
        self.refresh_callback()
        self.master.show_notification("Settings Saved & Stored.")
        self.on_close()

    def on_close(self):
        self.master.settings_window_ref = None
        self.destroy()

# --- NOTIFICATION & SPLASH ---
class CustomNotification(tk.Toplevel):
    def __init__(self, parent, message):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=COLORS["panel"])
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        self.geometry(f"320x60+{ws-340}+{hs-80}")
        tk.Frame(self, bg=COLORS["accent"], width=4).pack(side="left", fill="y")
        tk.Label(self, text=message, bg=COLORS["panel"], fg=COLORS["fg"], 
                 font=FONTS["small"], wraplength=300, justify="left").pack(side="left", padx=10)
        self.after(4000, self.destroy)

class SplashScreen(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=COLORS["bg"])
        w, h = 400, 150
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = (ws - w) // 2
        y = (hs - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        tk.Label(self, text="KAIZEN SYSTEM", font=("Courier New", 20, "bold"), 
                 bg=COLORS["bg"], fg=COLORS["fg"]).pack(pady=(30, 10))
        self.status_lbl = tk.Label(self, text="Initializing...", font=FONTS["small"], bg=COLORS["bg"], fg="#888")
        self.status_lbl.pack()
        self.progress_frame = tk.Frame(self, height=3, bg="#333", width=300)
        self.progress_frame.pack(pady=20)
        self.progress_fill = tk.Frame(self.progress_frame, height=3, bg=COLORS["accent"], width=0)
        self.progress_fill.place(x=0, y=0)

    def update_progress(self, percent, text):
        self.progress_fill.configure(width=300 * percent)
        self.status_lbl.configure(text=text)
        self.update()

# --- MAIN CONTROLLER ---
class KaizenHUD(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.automator = AutomationService(self.show_notification)
        self.pomo_active = False
        self.pomo_state = "WORK"
        self.pomo_seconds_left = CONFIG.pomo_work * 60
        
        self.settings_window_ref = None
        
        self.run_preload()
        self._setup_window()
        self._setup_titlebar()
        self._setup_dashboard()
        
        self.automator.start_watching()
        self.deiconify()
        self.focus_force()

    def run_preload(self):
        splash = SplashScreen(self)
        steps = [(0.3, "Loading Config..."), (0.6, "System Check..."), (1.0, "Ready")]
        for p, t in steps:
            time.sleep(0.3)
            splash.update_progress(p, t)
        splash.destroy()

    def _setup_window(self):
        self.overrideredirect(True)
        self.geometry("280x200")
        self.configure(bg=COLORS["bg"], highlightthickness=1, highlightbackground=COLORS["panel"])
        self.attributes("-topmost", True)
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = (ws - 280) // 2
        y = (hs - 200) // 2
        self.geometry(f"+{x}+{y}")

    def _setup_titlebar(self):
        self.title_bar = tk.Frame(self, bg=COLORS["panel"], height=24)
        self.title_bar.pack(fill="x", side="top")
        self.title_bar.bind("<ButtonPress-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)
        tk.Label(self.title_bar, text=" KAIZEN :: HUD", bg=COLORS["panel"], fg="#666", font=FONTS["small"]).pack(side="left")
        btn_close = tk.Label(self.title_bar, text=" X ", bg=COLORS["panel"], fg=COLORS["alert"], font=FONTS["icon"], cursor="hand2")
        btn_close.pack(side="right")
        btn_close.bind("<Button-1>", lambda e: self.quit_app())
        btn_min = tk.Label(self.title_bar, text=" _ ", bg=COLORS["panel"], fg=COLORS["fg"], font=FONTS["icon"], cursor="hand2")
        btn_min.pack(side="right")
        btn_min.bind("<Button-1>", lambda e: self.minimize_app())

    def _setup_dashboard(self):
        self.content = tk.Frame(self, bg=COLORS["bg"])
        self.content.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.lbl_pomo_mode = tk.Label(self.content, text="READY", font=FONTS["bold"], bg=COLORS["bg"], fg="#666")
        self.lbl_pomo_mode.pack(pady=(5,0))
        
        self.lbl_timer = tk.Label(self.content, text="00:00", font=FONTS["timer"], bg=COLORS["bg"], fg=COLORS["fg"])
        self.lbl_timer.pack(pady=(0, 5))
        
        self.btn_monk = tk.Button(self.content, text="START MONK MODE", 
                                  bg=COLORS["bg"], fg=COLORS["accent"], 
                                  activebackground=COLORS["accent"], activeforeground="black",
                                  bd=1, relief="solid", font=FONTS["bold"], cursor="hand2",
                                  command=self.toggle_monk_mode)
        self.btn_monk.pack(fill="x", pady=15)
        
        footer = tk.Frame(self.content, bg=COLORS["bg"])
        footer.pack(side="bottom", fill="x", pady=5)
        tk.Label(footer, text="System Active", font=FONTS["small"], bg=COLORS["bg"], fg="#444").pack(side="left")
        btn_set = tk.Label(footer, text="[SETTINGS]", bg=COLORS["bg"], fg=COLORS["accent"], font=FONTS["small"], cursor="hand2")
        btn_set.pack(side="right")
        btn_set.bind("<Button-1>", lambda e: self.open_settings())

    def open_settings(self):
        if self.settings_window_ref is None or not self.settings_window_ref.winfo_exists():
            self.settings_window_ref = SettingsWindow(self, self.automator, self.reset_timer_config)
        else:
            self.settings_window_ref.lift()

    def reset_timer_config(self):
        self.pomo_active = False 
        self.pomo_state = "WORK"
        self.pomo_seconds_left = CONFIG.pomo_work * 60
        self.update_ui_idle()

    def toggle_monk_mode(self):
        if not self.pomo_active:
            self.pomo_active = True
            self.pomo_state = "WORK"
            self.pomo_seconds_left = CONFIG.pomo_work * 60
            self.run_monk_sequence()
            self.pomo_tick()
        else:
            self.pomo_active = False
            self.update_ui_idle()

    def run_monk_sequence(self):
        for url in CONFIG.monk_urls: webbrowser.open(url)
        try: subprocess.Popen(["code"], shell=True) 
        except: pass

    def pomo_tick(self):
        if self.pomo_active:
            if self.pomo_seconds_left > 0:
                self.pomo_seconds_left -= 1
                self.update_ui_timer()
                self.after(1000, self.pomo_tick)
            else:
                self.switch_pomo_state()

    def switch_pomo_state(self):
        self.bell()
        if self.pomo_state == "WORK":
            self.show_notification("Focus complete! Take a break.")
            self.pomo_state = "BREAK"
            self.pomo_seconds_left = CONFIG.pomo_break * 60
        else:
            self.show_notification("Break over. Back to work!")
            self.pomo_state = "WORK"
            self.pomo_seconds_left = CONFIG.pomo_work * 60
        self.pomo_tick()

    def update_ui_timer(self):
        mins, secs = divmod(self.pomo_seconds_left, 60)
        time_str = "{:02}:{:02}".format(mins, secs)
        self.lbl_timer.configure(text=time_str)
        if self.pomo_state == "WORK":
            self.lbl_pomo_mode.configure(text="[ WORK FOCUS ]", fg=COLORS["accent"])
            self.lbl_timer.configure(fg=COLORS["accent"])
            self.btn_monk.configure(text="STOP SESSION", fg=COLORS["alert"])
        else:
            self.lbl_pomo_mode.configure(text="[ BREAK TIME ]", fg=COLORS["break"])
            self.lbl_timer.configure(fg=COLORS["break"])

    def update_ui_idle(self):
        self.lbl_pomo_mode.configure(text="READY", fg="#666")
        self.lbl_timer.configure(text="00:00", fg=COLORS["fg"])
        self.btn_monk.configure(text="START MONK MODE", fg=COLORS["accent"])

    def show_notification(self, msg):
        self.after(0, lambda: CustomNotification(self, msg))

    # --- MINIMIZATION FIX FOR LINUX ---
    def minimize_app(self):
        # Unbind first to prevent conflict
        self.unbind("<Map>")
        self.overrideredirect(False)
        self.iconify()
        # Bind restore event ONLY after minimizing
        self.bind("<Map>", self.on_restore_from_min)

    def on_restore_from_min(self, event):
        # Check if state is normal (restored) and it's the root window
        if self.state() == "normal":
            self.overrideredirect(True)
            self.unbind("<Map>")

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        x = self.winfo_x() + (event.x - self.x)
        y = self.winfo_y() + (event.y - self.y)
        self.geometry(f"+{x}+{y}")

    def quit_app(self):
        self.automator.stop_watching()
        self.destroy()

if __name__ == "__main__":
    app = KaizenHUD()
    app.mainloop()