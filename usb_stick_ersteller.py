import ctypes
import json
import os
import shutil
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


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


class UsbStickApp:
    def __init__(self, root):
        self.root = root
        self.root.title("USB-Stick-Ersteller")
        self.root.geometry("560x330")
        self.root.resizable(False, False)
        self.source_file = None
        self.monitoring = False
        self.monitor_thread = None
        self.known_drives = set(removable_drives())

        frame = ttk.Frame(root, padding=18)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="USB-Stick vorbereiten", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Wähle eine ausführbare EXE und einen angeschlossenen USB-Stick.").pack(anchor="w", pady=(4, 18))

        file_row = ttk.Frame(frame)
        file_row.pack(fill="x", pady=4)
        self.file_label = ttk.Label(file_row, text="Keine Datei ausgewählt", width=48)
        self.file_label.pack(side="left", fill="x", expand=True)
        ttk.Button(file_row, text="EXE auswählen...", command=self.choose_file).pack(side="right")

        drive_row = ttk.Frame(frame)
        drive_row.pack(fill="x", pady=4)
        ttk.Label(drive_row, text="USB-Stick:").pack(side="left")
        self.drive_box = ttk.Combobox(drive_row, state="readonly", width=12)
        self.drive_box.pack(side="left", padx=8)
        ttk.Button(drive_row, text="Aktualisieren", command=self.refresh_drives).pack(side="left")

        action_row = ttk.Frame(frame)
        action_row.pack(fill="x", pady=(18, 4))
        ttk.Button(action_row, text="Stick erstellen", command=self.create_stick).pack(side="left")
        self.monitor_button = ttk.Button(action_row, text="Überwachung starten", command=self.toggle_monitoring)
        self.monitor_button.pack(side="left", padx=8)

        self.status = tk.Text(frame, height=7, state="disabled", wrap="word")
        self.status.pack(fill="both", expand=True, pady=(12, 0))
        self.refresh_drives()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def log(self, text):
        self.status.configure(state="normal")
        self.status.insert("end", text + "\n")
        self.status.see("end")
        self.status.configure(state="disabled")

    def choose_file(self):
        selected = filedialog.askopenfilename(
            title="Auszuführende Datei auswählen",
            filetypes=[("Ausführbare Dateien", "*.exe"), ("Alle Dateien", "*.*")],
        )
        if selected:
            self.source_file = Path(selected)
            self.file_label.configure(text=str(self.source_file))

    def refresh_drives(self):
        drives = removable_drives()
        self.drive_box["values"] = drives
        if drives and self.drive_box.get() not in drives:
            self.drive_box.set(drives[0])
        elif not drives:
            self.drive_box.set("")

    def create_stick(self):
        if self.source_file is None:
            messagebox.showwarning("Datei fehlt", "Bitte zuerst eine EXE-Datei auswählen.")
            return

        drive = self.drive_box.get()
        if not drive:
            messagebox.showwarning("USB-Stick fehlt", "Bitte einen USB-Stick auswählen.")
            return

        target = Path(drive) / self.source_file.name
        config = Path(drive) / CONFIG_NAME
        launcher = Path(drive) / LAUNCHER_NAME
        try:
            if self.source_file.resolve() == target.resolve():
                messagebox.showerror("Ungültige Auswahl", "Quelle und Ziel sind identisch.")
                return
            shutil.copy2(self.source_file, target)
            config.write_text(
                json.dumps({"datei": self.source_file.name}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            launcher.write_text(
                '@echo off\nstart "" "%~dp0' + self.source_file.name + '"\n',
                encoding="ascii",
            )
        except OSError as error:
            messagebox.showerror("USB-Stick konnte nicht erstellt werden", str(error))
            return

        self.log(f"Stick erstellt: {drive} -> {self.source_file.name}")
        messagebox.showinfo("Fertig", f"Die Datei wurde nach {drive} kopiert.")

    def toggle_monitoring(self):
        if self.monitoring:
            self.monitoring = False
            self.monitor_button.configure(text="Überwachung starten")
            self.log("Überwachung beendet.")
            return

        self.monitoring = True
        self.monitor_button.configure(text="Überwachung beenden")
        self.log("Überwachung aktiv. Neue vorbereitete USB-Sticks werden geöffnet.")
        self.monitor_thread = threading.Thread(target=self.monitor_drives, daemon=True)
        self.monitor_thread.start()

    def monitor_drives(self):
        while self.monitoring:
            current_drives = set(removable_drives())
            inserted_drives = current_drives - self.known_drives
            self.known_drives = current_drives

            for drive in inserted_drives:
                self.root.after(0, self.open_configured_file, drive)

            time.sleep(1)

    def open_configured_file(self, drive):
        config_path = Path(drive) / CONFIG_NAME
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            file_name = config["datei"]
            file_path = (Path(drive) / file_name).resolve()
            drive_path = Path(drive).resolve()
            if drive_path not in file_path.parents or not file_path.is_file():
                raise ValueError("Die konfigurierte Datei liegt nicht auf dem USB-Stick.")
            subprocess.Popen([os.fspath(file_path)], cwd=os.fspath(drive_path))
            self.log(f"Geöffnet: {file_path}")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            self.log(f"USB-Stick {drive} übersprungen: {error}")

    def close(self):
        self.monitoring = False
        self.root.destroy()


if __name__ == "__main__":
    application = tk.Tk()
    UsbStickApp(application)
    application.mainloop()