"""
create_shortcut.py — Run this ONCE to create the HEXA desktop icon.

Usage:
    python create_shortcut.py

This creates:
  - A desktop shortcut "HEXA.lnk" that launches HEXA with one double-click
  - No terminal window appears when you use the shortcut
  - The shortcut uses the HEXA teal icon
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_icon():
    """Generate a HEXA .ico file for the desktop shortcut."""
    from PIL import Image, ImageDraw, ImageFont

    sizes = [16, 32,48, 64, 128, 256]
    frames = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Teal circle
        pad = max(1, size // 16)
        d.ellipse([pad, pad, size-pad, size-pad], fill=(13, 148, 136, 255))

        # White H text
        text_size = int(size * 0.55)
        try:
            font = ImageFont.truetype("arialbd.ttf", text_size)
        except Exception:
            try:
                font = ImageFont.truetype("arial.ttf", text_size)
            except Exception:
                font = ImageFont.load_default()

        # Center the H
        try:
            bbox = d.textbbox((0, 0), "H", font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = text_size * 0.6, text_size

        x = (size - tw) // 2
        y = (size - th) // 2 - max(1, size//20)
        d.text((x, y), "H", fill=(255, 255, 255, 255), font=font)
        frames.append(img)

    ico_path = os.path.join(BASE_DIR, "hexa.ico")
    frames[0].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes],
                   append_images=frames[1:])
    print(f"Icon created: {ico_path}")
    return ico_path


def create_desktop_shortcut(ico_path):
    """Create a .lnk shortcut on the Windows desktop."""
    try:
        import winshell
        from win32com.client import Dispatch
    except ImportError:
        # winshell not available — use PowerShell instead
        return create_shortcut_powershell(ico_path)

    desktop = winshell.desktop()
    shortcut_path = os.path.join(desktop, "HEXA.lnk")
    vbs_path = os.path.join(BASE_DIR, "HEXA.vbs")

    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = "wscript.exe"
    shortcut.Arguments = f'"{vbs_path}"'
    shortcut.WorkingDirectory = BASE_DIR
    shortcut.IconLocation = ico_path
    shortcut.Description = "HEXA — Sovereign Industrial AI Workbench"
    shortcut.save()

    print(f"Desktop shortcut created: {shortcut_path}")
    return shortcut_path


def create_shortcut_powershell(ico_path):
    """Create desktop shortcut using PowerShell (no extra deps needed)."""
    import subprocess

    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    shortcut_path = os.path.join(desktop, "HEXA.lnk")
    vbs_path = os.path.join(BASE_DIR, "HEXA.vbs")

    ps_script = f"""
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = '"{vbs_path}"'
$Shortcut.WorkingDirectory = "{BASE_DIR}"
$Shortcut.IconLocation = "{ico_path}"
$Shortcut.Description = "HEXA - Sovereign Industrial AI Workbench"
$Shortcut.Save()
Write-Host "Shortcut created: {shortcut_path}"
"""

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"Desktop shortcut created: {shortcut_path}")
        return shortcut_path
    else:
        print(f"PowerShell error: {result.stderr}")
        return None


def main():
    print("=" * 50)
    print("  HEXA Desktop Launcher Setup")
    print("=" * 50)
    print()

    # Step 1: Create icon
    print("Step 1: Creating HEXA icon...")
    try:
        ico_path = create_icon()
    except Exception as e:
        print(f"  Icon creation failed: {e}")
        ico_path = os.path.join(BASE_DIR, "hexa.ico")

    # Step 2: Create desktop shortcut
    print("Step 2: Creating desktop shortcut...")
    shortcut = create_desktop_shortcut(ico_path)

    print()
    print("=" * 50)
    if shortcut:
        print("  DONE! Find 'HEXA' on your desktop.")
        print("  Double-click it to launch HEXA anytime.")
    else:
        print("  Shortcut could not be created automatically.")
        print(f"  Manually create a shortcut to: {os.path.join(BASE_DIR, 'HEXA.vbs')}")
    print()
    print("  To start HEXA manually (alternative):")
    print(f"  Double-click: {os.path.join(BASE_DIR, 'HEXA.vbs')}")
    print("=" * 50)

    input("\nPress Enter to close...")


if __name__ == "__main__":
    main()
