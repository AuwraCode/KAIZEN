import tkinter as tk
from tkinter import messagebox
import shutil
import os
import time
import threading
import subprocess
import webbrowser
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- CONFIGURATION & CONSTANTS ---
COLORS = {
    "bg": "#121212",
    "fg": "#E0E0E0",
    "accent": "#00E676",    # Cyberpunk Green
    "alert": "#FF5252",     # Red
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

class Config:
    def __init__(self):
        self.watch_paths = [str(Path.home() / "Downloads"), str(Path.home() / "Desktop")]
        self.monk_urls = [
            "https://www.kaggle.com",
            "https://gemini.google.com",
            "https://renshuu.org"
        ]
        self.extensions = {
            "Images": [".jpg", ".jpeg", ".png", ".webp", ".svg"],
            "Documents": [".pdf", ".docx", ".txt", ".xlsx", ".csv"],
            "Installers": [".exe", ".msi", ".zip", ".rar", ".7z"],
            "Code": [".py", ".ipynb", ".js", ".cpp", ".html"]
        }

CONFIG = Config()

# --- BACKEND: AUTOMATION SERVICE ---

class FileHandler(FileSystemEventHandler):
    def __init__(self, callback_notify):
        self.callback_notify = callback_notify

    def on_created(self, event):
        if event.is_directory: return
        threading.Thread(target=self.process_file, args=(Path(event.src_path),)).start()

    def process_file(self, file_path: Path):
        time.sleep(1.5) # Wait for download to finish
        if not file_path.exists(): return

        for category, exts in CONFIG.extensions.items():
            if file_path.suffix.lower() in exts:
                try:
                    dest_dir = file_path.parent / category
                    dest_dir.mkdir(exist_ok=True)
                    final_path = dest_dir / file_path.name
                    
                    counter = 1
                    while final_path.exists():
                        final_path = dest_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                        counter += 1
                        
                    shutil.move(str(file_path), str(final_path))
                    self.callback_notify(f"Moved: {file_path.name} -> [{category}]")
                    return
                except Exception as e:
                    print(f"Error: {e}")

class AutomationService:
    def __init__(self, notify_callback):
        self.handler = FileHandler(notify_callback)
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

# --- GUI COMPONENTS ---

class CustomNotification(tk.Toplevel):
    def __init__(self, parent, message):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=COLORS["panel"])
        
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        # Bottom Right
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

# --- MAIN APP (CONTROLLER) ---

class KaizenHUD(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        
        self.automator = AutomationService(self.show_notification)
        self.monk_mode_active = False
        self.timer_start = None
        
        # Preload & Setup
        self.run_preload()
        self._setup_window()
        self._setup_titlebar()
        
        self.container = tk.Frame(self, bg=COLORS["bg"])
        self.container.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.dashboard_frame = None
        self.settings_frame = None
        
        self.automator.start_watching()
        self.show_dashboard()
        self.deiconify()

        # FIX: Bind event to handle minimize/restore logic
        self.bind("<Map>", self.on_restore_window)

    def run_preload(self):
        splash = SplashScreen(self)
        steps = [(0.2, "Loading Core..."), (0.5, "Starting Watchdog..."), (0.8, "Applying Preferences..."), (1.0, "Ready.")]
        for p, t in steps:
            time.sleep(0.3)
            splash.update_progress(p, t)
        splash.destroy()

    def _setup_window(self):
        self.overrideredirect(True)
        self.geometry("280x200")
        self.configure(bg=COLORS["bg"], highlightthickness=1, highlightbackground=COLORS["panel"])
        self.attributes("-topmost", True)
        
        # Center Window
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
        
        # Close Button
        btn_close = tk.Label(self.title_bar, text=" X ", bg=COLORS["panel"], fg=COLORS["alert"], font=FONTS["icon"], cursor="hand2")
        btn_close.pack(side="right")
        btn_close.bind("<Button-1>", lambda e: self.quit_app())
        
        # Minimize Button
        btn_min = tk.Label(self.title_bar, text=" _ ", bg=COLORS["panel"], fg=COLORS["fg"], font=FONTS["icon"], cursor="hand2")
        btn_min.pack(side="right")
        # FIX: Use custom minimize method
        btn_min.bind("<Button-1>", lambda e: self.minimize_app())

    # --- MINIMIZE LOGIC FIX ---
    
    def minimize_app(self):
        # 1. Disable override to give control back to OS
        self.overrideredirect(False)
        # 2. Minimize using standard call
        self.iconify()
    
    def on_restore_window(self, event):
        # 3. Detect when window comes back (Mapped)
        # We check if it's the main window and if state is normal
        if self.state() == "normal":
            self.overrideredirect(True)

    # --- VIEW SWITCHING ---

    def show_dashboard(self):
        if self.settings_frame: self.settings_frame.pack_forget()
        
        if not self.dashboard_frame:
            self.dashboard_frame = tk.Frame(self.container, bg=COLORS["bg"])
            
            self.lbl_timer = tk.Label(self.dashboard_frame, text="00:00:00", font=FONTS["timer"], bg=COLORS["bg"], fg=COLORS["fg"])
            self.lbl_timer.pack(pady=(10, 5))
            
            self.btn_monk = tk.Button(self.dashboard_frame, text="ACTIVATE MONK MODE", 
                                      bg=COLORS["bg"], fg=COLORS["accent"], 
                                      activebackground=COLORS["accent"], activeforeground="black",
                                      bd=1, relief="solid", font=FONTS["bold"], cursor="hand2",
                                      command=self.toggle_monk_mode)
            self.btn_monk.pack(fill="x", pady=15)
            
            footer = tk.Frame(self.dashboard_frame, bg=COLORS["bg"])
            footer.pack(side="bottom", fill="x", pady=5)
            self.lbl_status = tk.Label(footer, text="System Active", font=FONTS["small"], bg=COLORS["bg"], fg="#444")
            self.lbl_status.pack(side="left")
            
            btn_set = tk.Label(footer, text="[SETTINGS]", bg=COLORS["bg"], fg=COLORS["accent"], font=FONTS["small"], cursor="hand2")
            btn_set.pack(side="right")
            btn_set.bind("<Button-1>", lambda e: self.show_settings())

        self.update_dashboard_ui()
        self.dashboard_frame.pack(fill="both", expand=True)

    def show_settings(self):
        if self.dashboard_frame: self.dashboard_frame.pack_forget()
        
        if not self.settings_frame:
            self.settings_frame = tk.Frame(self.container, bg=COLORS["bg"])
            
            tk.Label(self.settings_frame, text="WATCH PATHS (;)", bg=COLORS["bg"], fg="#666", font=FONTS["small"]).pack(anchor="w")
            self.ent_paths = tk.Entry(self.settings_frame, bg=COLORS["input"], fg=COLORS["fg"], borderwidth=0, insertbackground="white")
            self.ent_paths.insert(0, ";".join(CONFIG.watch_paths))
            self.ent_paths.pack(fill="x", pady=(0, 10))

            tk.Label(self.settings_frame, text="MONK URLS (;)", bg=COLORS["bg"], fg="#666", font=FONTS["small"]).pack(anchor="w")
            self.ent_urls = tk.Entry(self.settings_frame, bg=COLORS["input"], fg=COLORS["fg"], borderwidth=0, insertbackground="white")
            self.ent_urls.insert(0, ";".join(CONFIG.monk_urls))
            self.ent_urls.pack(fill="x", pady=(0, 15))

            btn_box = tk.Frame(self.settings_frame, bg=COLORS["bg"])
            btn_box.pack(fill="x")
            
            tk.Button(btn_box, text="SAVE", bg=COLORS["accent"], fg="black", font=FONTS["bold"], bd=0, 
                      command=self.save_settings).pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            tk.Button(btn_box, text="BACK", bg=COLORS["panel"], fg=COLORS["fg"], font=FONTS["bold"], bd=0, 
                      command=self.show_dashboard).pack(side="right", fill="x", expand=True, padx=(5, 0))

        self.settings_frame.pack(fill="both", expand=True)

    def save_settings(self):
        raw_paths = self.ent_paths.get().split(";")
        CONFIG.watch_paths = [p.strip() for p in raw_paths if p.strip()]
        
        raw_urls = self.ent_urls.get().split(";")
        CONFIG.monk_urls = [u.strip() for u in raw_urls if u.strip()]
        
        self.automator.start_watching()
        messagebox.showinfo("KAIZEN", "Settings Saved.")
        self.show_dashboard()

    def toggle_monk_mode(self):
        if not self.monk_mode_active:
            self.monk_mode_active = True
            self.timer_start = time.time()
            self.run_monk_sequence()
            self.update_timer_loop()
        else:
            self.monk_mode_active = False
            self.timer_start = None
            
        self.update_dashboard_ui()

    def run_monk_sequence(self):
        for url in CONFIG.monk_urls: webbrowser.open(url)
        try: subprocess.Popen(["code"], shell=True) 
        except: pass

    def update_dashboard_ui(self):
        if self.dashboard_frame and self.dashboard_frame.winfo_ismapped():
            if self.monk_mode_active:
                self.btn_monk.configure(text="STOP FOCUS", fg=COLORS["alert"])
            else:
                self.btn_monk.configure(text="ACTIVATE MONK MODE", fg=COLORS["accent"])
                self.lbl_timer.configure(text="00:00:00", fg=COLORS["fg"])

    def update_timer_loop(self):
        if self.monk_mode_active:
            elapsed = time.time() - self.timer_start
            hours, rem = divmod(elapsed, 3600)
            minutes, seconds = divmod(rem, 60)
            time_str = "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))
            
            if self.dashboard_frame and self.dashboard_frame.winfo_ismapped():
                self.lbl_timer.configure(text=time_str, fg=COLORS["alert"])
            
            self.after(1000, self.update_timer_loop)

    def show_notification(self, msg):
        self.after(0, lambda: CustomNotification(self, msg))

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