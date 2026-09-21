# hexa_launcher.py
"""
HEXA Desktop Launcher — one double-click to start everything.

What this does:
1. Shows a splash screen immediately (no blank wait)
2. Starts Ollama if not running
3. Starts the HEXA FastAPI server on port 7000
4. Opens http://localhost:7000 in the browser automatically
5. Puts a green HEXA icon in the system tray
6. Right-click tray → Open HEXA / Stop Server / Exit

Run: pythonw hexa_launcher.py   (no terminal window)
  or: python  hexa_launcher.py   (with terminal for debugging)
"""
import os
import sys
import subprocess
import threading
import time
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 7000
URL = f"http://localhost:{PORT}"

# ── Silence GUI mode stream errors ───────────────────────────────────────────
class _NullWriter:
    def write(self, t): pass
    def flush(self): pass
    def isatty(self): return False

if sys.stdout is None: sys.stdout = _NullWriter()
if sys.stderr is None: sys.stderr = _NullWriter()


# ── Splash screen (shows instantly before server starts) ─────────────────────
_splash = None

def _show_splash():
    global _splash
    try:
        import tkinter as tk
        _splash = tk.Tk()
        _splash.title("HEXA")
        _splash.overrideredirect(True)
        _splash.configure(bg="#0d9488")

        w, h = 380, 180
        sw = _splash.winfo_screenwidth()
        sh = _splash.winfo_screenheight()
        _splash.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        tk.Label(_splash, text="HEXA", font=("Segoe UI", 32, "bold"),
                 bg="#0d9488", fg="#ffffff").pack(pady=(28, 2))
        tk.Label(_splash, text="Sovereign Industrial AI Workbench",
                 font=("Segoe UI", 11), bg="#0d9488", fg="#ccfbf1").pack()
        tk.Label(_splash, text="Starting server, please wait...",
                 font=("Segoe UI", 9, "italic"), bg="#0d9488", fg="#99f6e4").pack(pady=(14, 0))

        _splash.attributes("-topmost", True)
        _splash.mainloop()
    except Exception:
        pass

def _close_splash():
    global _splash
    try:
        if _splash:
            _splash.after(0, _splash.destroy)
    except Exception:
        pass


# ── Check if server is already running ───────────────────────────────────────
def _server_running() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{URL}/api/health", timeout=2)
        return True
    except Exception:
        return False


# ── Start Ollama if not running ───────────────────────────────────────────────
def _ensure_ollama():
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return  # already running
    except Exception:
        pass
    try:
        # Try starting Ollama silently
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        time.sleep(3)  # give it a moment
    except FileNotFoundError:
        pass  # Ollama not installed — server will still work with manual setup


# ── Start HEXA server ─────────────────────────────────────────────────────────
_server_proc = None

def _start_server():
    global _server_proc
    if _server_running():
        return  # already up

    _ensure_ollama()

    env = os.environ.copy()
    env["PYTHONPATH"] = BASE_DIR

    _server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=BASE_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

    # Wait until server responds (max 60s)
    for _ in range(60):
        time.sleep(1)
        if _server_running():
            return

    raise RuntimeError("HEXA server did not start within 60 seconds")


# ── Open browser ──────────────────────────────────────────────────────────────
def _open_browser():
    time.sleep(1)  # small delay so page loads properly
    webbrowser.open(URL)


# ── Build tray icon image ─────────────────────────────────────────────────────
def _make_tray_icon():
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Teal circle background
    d.ellipse([2, 2, 62, 62], fill=(13, 148, 136, 255))

    # White "H" letter
    try:
        # Try to use a bold font
        font = ImageFont.truetype("arialbd.ttf", 36)
    except Exception:
        font = ImageFont.load_default()

    # Draw H centered
    d.text((18, 12), "H", fill=(255, 255, 255, 255), font=font)

    return img


# ── System tray ───────────────────────────────────────────────────────────────
def _stop_server():
    global _server_proc
    if _server_proc:
        try:
            _server_proc.terminate()
            _server_proc.wait(timeout=5)
        except Exception:
            try: _server_proc.kill()
            except Exception: pass
        _server_proc = None


def _run_tray():
    try:
        import pystray
        from pystray import MenuItem, Menu

        icon_img = _make_tray_icon()

        def open_browser(icon, item):
            webbrowser.open(URL)

        def restart_server(icon, item):
            icon.notify("Restarting HEXA...", "HEXA")
            _stop_server()
            time.sleep(1)
            threading.Thread(target=_start_server, daemon=True).start()
            time.sleep(3)
            webbrowser.open(URL)

        def exit_app(icon, item):
            icon.notify("Stopping HEXA...", "HEXA")
            time.sleep(0.5)
            _stop_server()
            icon.stop()
            os._exit(0)

        menu = Menu(
            MenuItem("🌐  Open HEXA", open_browser, default=True),
            Menu.SEPARATOR,
            MenuItem("🔄  Restart Server", restart_server),
            Menu.SEPARATOR,
            MenuItem("⏹  Stop & Exit", exit_app),
        )

        icon = pystray.Icon(
            "HEXA",
            icon_img,
            "HEXA — Sovereign AI Workbench",
            menu,
        )
        icon.run()

    except Exception as e:
        # Fallback: just keep the process alive
        print(f"Tray icon error: {e}")
        while True:
            time.sleep(60)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # 1. Show splash immediately
    splash_thread = threading.Thread(target=_show_splash, daemon=True)
    splash_thread.start()

    # 2. Start server (blocks until ready or fails)
    try:
        _start_server()
    except Exception as e:
        _close_splash()
        # Show error in a simple dialog
        try:
            import tkinter.messagebox as mb
            mb.showerror("HEXA Launch Error", str(e))
        except Exception:
            print(f"Launch failed: {e}")
        sys.exit(1)

    # 3. Close splash
    _close_splash()

    # 4. Open browser
    threading.Thread(target=_open_browser, daemon=True).start()

    # 5. Run system tray (blocks until user exits)
    _run_tray()


if __name__ == "__main__":
    main()
