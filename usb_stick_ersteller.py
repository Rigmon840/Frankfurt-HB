import ctypes
import json
import os
import shutil
import subprocess
import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    pystray = None
    Image = None
    ImageDraw = None


CONFIG_NAME = "usb_auto_start.json"
LAUNCHER_NAME = "START_USB.bat"
DRIVE_REMOVABLE = 2


def removable_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()

    for number in range(26):
        if bitmask & (1 << number):
            drive = f"{chr(65 + number)}:\\"
            if ctypes.windll.kernel32.GetDriveTypeW(drive) == DRIVE_REMOVABLE:
                drives.append(drive)

    return drives


def build_launcher_content(file_name):
    safe_name = Path(file_name).name
    return f'@echo off\r\nstart "" "%~dp0\\{safe_name}"\r\n'


def write_usb_config(target_dir, file_name):
    target_dir = Path(target_dir)
    config = {
        "datei": Path(file_name).name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": 2,
    }
    config_path = target_dir / CONFIG_NAME
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config


class UsbStickApp:
    def __init__(self, root):
        self.root = root
        self.root.title("USB-Stick-Ersteller Pro")
        self.root.geometry("720x430")
        self.root.minsize(620, 360)
        self.root.configure(bg="#0b1020")
        self.source_file = None
        self.monitoring = False
        self.monitor_thread = None
        self.known_drives = set(removable_drives())
        self.tray_icon = None

        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#0b1020")
        self.style.configure("TLabel", background="#0b1020", foreground="#e5edf9")
        self.style.configure("TButton", background="#1f2937", foreground="#e5edf9", padding=(10, 6))
        self.style.map("TButton", background=[("active", "#2b3d59")])
        self.style.configure("TCombobox", fieldbackground="#111827", background="#111827", foreground="#e5edf9")
        self.style.map("TCombobox", fieldbackground=[("readonly", "#111827")])

        main = ttk.Frame(root, padding=18)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="USB-Stick vorbereiten", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            main,
            text="Wähle eine EXE-Datei und einen angeschlossenen USB-Stick. Danach wird die Datei automatisch als Startpunkt eingerichtet.",
            wraplength=650,
            justify="left",
        ).pack(anchor="w", pady=(4, 14))

        file_row = ttk.Frame(main)
        file_row.pack(fill="x", pady=4)
        self.file_label = tk.Label(file_row, text="Keine Datei ausgewählt", width=58, anchor="w", bg="#111827", fg="#e5edf9", relief="flat", padx=10, pady=8)
        self.file_label.pack(side="left", fill="x", expand=True)
        ttk.Button(file_row, text="EXE auswählen...", command=self.choose_file).pack(side="right")

        drive_row = ttk.Frame(main)
        drive_row.pack(fill="x", pady=6)
        ttk.Label(drive_row, text="USB-Stick:", width=12, anchor="w").pack(side="left")
        self.drive_box = ttk.Combobox(drive_row, state="readonly", width=12)
        self.drive_box.pack(side="left", padx=8)
        ttk.Button(drive_row, text="Aktualisieren", command=self.refresh_drives).pack(side="left")

        action_row = ttk.Frame(main)
        action_row.pack(fill="x", pady=(18, 6))
        ttk.Button(action_row, text="Stick erstellen", command=self.create_stick).pack(side="left")
        self.monitor_button = ttk.Button(action_row, text="Überwachung starten", command=self.toggle_monitoring)
        self.monitor_button.pack(side="left", padx=8)
        ttk.Button(action_row, text="USB-Stick öffnen", command=self.open_selected_drive).pack(side="left")

        self.status = tk.Text(main, height=9, state="disabled", wrap="word", padx=8, pady=8, bg="#111827", fg="#dfe7f6", insertbackground="#ffffff", relief="flat")
        self.status.pack(fill="both", expand=True, pady=(10, 0))

        self.status_var = tk.StringVar(value="Bereit.")
        ttk.Label(main, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

        self.refresh_drives()
        self.log("App bereit. Wähle eine EXE-Datei und einen USB-Stick aus.")
        self._setup_tray()
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

    def log(self, text):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status.configure(state="normal")
        self.status.insert("end", f"[{timestamp}] {text}\n")
        self.status.see("end")
        self.status.configure(state="disabled")
        self.status_var.set(text)

    def choose_file(self):
        selected = filedialog.askopenfilename(
            title="Auszuführende Datei auswählen",
            filetypes=[("Ausführbare Dateien", "*.exe"), ("Windows-Dateien", "*.bat;*.cmd;*.com"), ("Alle Dateien", "*.*")],
        )
        if selected:
            self.source_file = Path(selected)
            self.file_label.configure(text=str(self.source_file))
            self.log(f"Datei ausgewählt: {self.source_file.name}")

    def refresh_drives(self):
        drives = removable_drives()
        self.drive_box["values"] = drives
        if drives:
            if self.drive_box.get() not in drives:
                self.drive_box.set(drives[0])
        else:
            self.drive_box.set("")
        self.log(f"USB-Laufwerke gefunden: {len(drives)}")

    def _get_selected_drive_path(self):
        drive = self.drive_box.get().strip()
        if not drive:
            return None
        drive_path = Path(drive)
        if not drive_path.exists() or not drive_path.is_dir():
            return None
        return drive_path

    def create_stick(self):
        if self.source_file is None:
            messagebox.showwarning("Datei fehlt", "Bitte zuerst eine ausführbare Datei auswählen.")
            return

        if not self.source_file.is_file():
            messagebox.showwarning("Datei ungültig", "Die ausgewählte Datei existiert nicht oder ist nicht lesbar.")
            return

        drive_path = self._get_selected_drive_path()
        if drive_path is None:
            messagebox.showwarning("USB-Stick fehlt", "Bitte einen angeschlossenen USB-Stick auswählen.")
            return

        target = drive_path / self.source_file.name
        launcher = drive_path / LAUNCHER_NAME
        try:
            if self.source_file.resolve() == target.resolve():
                messagebox.showerror("Ungültige Auswahl", "Quelle und Ziel sind identisch.")
                return
            shutil.copy2(self.source_file, target)
            write_usb_config(drive_path, self.source_file.name)
            launcher.write_text(build_launcher_content(self.source_file.name), encoding="utf-8")
        except OSError as error:
            messagebox.showerror("USB-Stick konnte nicht vorbereitet werden", str(error))
            return

        self.log(f"USB-Stick vorbereitet: {drive_path} -> {self.source_file.name}")
        messagebox.showinfo("Erfolgreich", f"Die Datei wurde nach {drive_path} kopiert und die Auto-Start-Konfiguration wurde eingerichtet.")

    def toggle_monitoring(self, _icon=None, _item=None):
        if self.monitoring:
            self.monitoring = False
            self.monitor_button.configure(text="Überwachung starten")
            self.log("Überwachung beendet.")
            return

        self.monitoring = True
        self.monitor_button.configure(text="Überwachung beenden")
        self.log("Überwachung aktiv. Neue vorbereitete USB-Sticks werden automatisch geöffnet.")
        self.monitor_thread = threading.Thread(target=self.monitor_drives, daemon=True)
        self.monitor_thread.start()

    def monitor_drives(self):
        while self.monitoring:
            current_drives = set(removable_drives())
            inserted_drives = current_drives - self.known_drives
            self.known_drives = current_drives

            for drive in sorted(inserted_drives):
                self.root.after(0, self.open_configured_file, drive)

            time.sleep(1)

    def open_configured_file(self, drive):
        drive_path = Path(drive)
        config_path = drive_path / CONFIG_NAME
        try:
            if not config_path.exists():
                self.log(f"USB-Stick {drive} übersprungen: keine Konfiguration gefunden.")
                return

            config = json.loads(config_path.read_text(encoding="utf-8"))
            file_name = config.get("datei")
            if not file_name:
                raise ValueError("Konfigurationsdatei enthält keinen Dateinamen.")

            file_path = (drive_path / file_name).resolve()
            if drive_path.resolve() not in file_path.parents or not file_path.is_file():
                raise ValueError("Die konfigurierte Datei liegt nicht auf dem USB-Stick.")

            subprocess.Popen([os.fspath(file_path)], cwd=os.fspath(drive_path.resolve()))
            self.log(f"Geöffnet: {file_path}")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            self.log(f"USB-Stick {drive} übersprungen: {error}")

    def open_selected_drive(self):
        drive_path = self._get_selected_drive_path()
        if drive_path is None:
            messagebox.showwarning("USB-Stick fehlt", "Bitte einen USB-Stick wählen.")
            return
        try:
            os.startfile(os.fspath(drive_path))
            self.log(f"USB-Stick geöffnet: {drive_path}")
        except OSError as error:
            messagebox.showerror("USB-Stick konnte nicht geöffnet werden", str(error))

    def _create_tray_icon(self):
        if Image is None or ImageDraw is None:
            return None

        image = Image.new("RGBA", (64, 64), (8, 15, 31, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 56), radius=12, fill=(26, 101, 231, 255))
        draw.rounded_rectangle((18, 18, 46, 46), radius=7, fill=(10, 17, 28, 255))
        draw.line((22, 24, 42, 24), fill=(255, 255, 255, 255), width=4)
        draw.line((22, 32, 42, 32), fill=(255, 255, 255, 255), width=4)
        draw.line((22, 40, 42, 40), fill=(255, 255, 255, 255), width=4)
        return image

    def _setup_tray(self):
        if pystray is None:
            self.log("Tray-Icon nicht verfügbar: pystray fehlt.")
            return

        tray_icon_image = self._create_tray_icon()
        if tray_icon_image is None:
            self.log("Tray-Icon nicht verfügbar: Bild nicht erzeugt.")
            return

        self.tray_icon = pystray.Icon(
            "USB-Stick-Ersteller-Pro",
            tray_icon_image,
            "USB-Stick-Ersteller Pro",
            menu=pystray.Menu(
                pystray.MenuItem("Fenster anzeigen", self.show_window),
                pystray.MenuItem("Überwachung umschalten", self.toggle_monitoring),
                pystray.MenuItem("Beenden", self.close),
            ),
        )
        self.tray_icon.run_detached()

    def show_window(self, _icon=None, _item=None):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def minimize_to_tray(self):
        self.root.withdraw()
        self.log("App in die Taskleiste minimiert.")

    def close(self, _icon=None, _item=None):
        self.monitoring = False
        if self.tray_icon is not None:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.destroy()


if __name__ == "__main__":
    application = tk.Tk()
    UsbStickApp(application)
    application.mainloop()