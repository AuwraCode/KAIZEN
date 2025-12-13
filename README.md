# KAIZEN HUD

> "Efficiency is doing things right; effectiveness is doing the right things."

**KAIZEN HUD** is a minimalist, Always-On-Top desktop dashboard designed for software engineers and data scientists. It combines background file automation (Seiri) with a deep work focus timer (Monk Mode) in a non-intrusive, cyberpunk-styled interface.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Key Features

* **🕵️ Background Automation:** Automatically watches your `Downloads` and `Desktop` folders. Moves files to organized subfolders (Images, Documents, Code, Installers) instantly upon creation.
* **🧘 Monk Mode:** One-click activation of your "Deep Work" environment. Launches VS Code, documentation, and specific URLs while starting a focus timer.
* **🎨 Minimalist HUD:** A tiny, borderless window that sits on your desktop. Custom-drawn title bar and dark mode aesthetic.
* **⚙️ Live Configuration:** Configure watch paths and URLs directly within the app without restarting.
* **🚀 Zero Bloat:** Built with pure Python `tkinter` and `watchdog`. No heavy frameworks.

## 🛠️ Tech Stack

* **Language:** Python 3
* **GUI:** Tkinter (Custom drawn components, no OS borders)
* **Concurrency:** `threading` for non-blocking I/O operations
* **File System:** `watchdog` library for real-time file monitoring
* **Architecture:** Event-Driven, OOP

## 📦 Installation

1.  Clone the repository:
    ```bash
    git clone [https://github.com/your-username/kaizen-hud.git](https://github.com/your-username/kaizen-hud.git)
    cd kaizen-hud
    ```

2.  Install dependencies:
    ```bash
    pip install watchdog
    ```
    *(Note: Tkinter is usually pre-installed with Python. On Fedora/Ubuntu: `sudo dnf install python3-tkinter`)*

3.  Run the HUD:
    ```bash
    python kaizen.py
    ```

## 🎮 Usage

* **Move:** Drag the window by clicking anywhere on the top bar.
* **Minimize:** Click `_` to send to taskbar.
* **Settings:** Click `[SETTINGS]` to configure folders and URLs.
* **Monk Mode:** Click `ACTIVATE MONK MODE` to start the session. The timer runs even if you switch to settings.

## 🗺️ Roadmap

* [x] Integration with Pomodoro technique
* [ ] Daily stats visualization (matplotlib)
* [ ] Cross-platform "blocker" for distracting apps

---
*Built with discipline by Grzegorz Handzel (Auwra).*
