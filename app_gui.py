"""
Industrial Touchscreen GUI: Condenser Coil Bending Poka-Yoke System
Real-time integration with Mitsubishi PLC (MC Protocol 3E Binary)
"""

import os
import sys
import json
import csv
import time
import winsound
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pymcprotocol

# Optional dotenv loader with safe fallback
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── Configuration (Environment variables with safe defaults) ──
PLC_IP = os.getenv("PLC_IP", "192.168.19.206")
PLC_PORT = int(os.getenv("PLC_PORT", 8500))
REG_READ_PROG = os.getenv("REG_READ_PROG", "D1017")      # Reads Active Program number from machine
REG_WRITE_PERMIT = os.getenv("REG_WRITE_PERMIT", "D5000")   # Writes 1 (Allow) or 0 (Lock)
AUTO_RELOCK_DELAY_SEC = int(os.getenv("AUTO_RELOCK_DELAY_SEC", 20))

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "recipe_config.json"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_recipes():
    """Load recipe definitions from JSON."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return {}


class PokaYokeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Condenser Coil Bending — Poka-Yoke System")
        self.geometry("1150x780")
        self.configure(bg="#0F172A")  # Dark slate industrial background
        
        # State variables
        self.recipes = load_recipes()
        self.plc_connected = False
        self.current_program = 0
        self.last_program = 0
        self.is_fullscreen = False
        self.total_count = 0
        self.ok_count = 0
        self.ng_count = 0
        self.relock_timer_id = None
        
        # Fullscreen bindings
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)
        
        self.create_widgets()
        
        # Safety on startup: lock machine (D5000 = 0)
        threading.Thread(target=self.write_plc_permit, args=(0,), daemon=True).start()
        
        # Start background PLC monitoring thread
        self.poll_thread = threading.Thread(target=self.poll_plc_loop, daemon=True)
        self.poll_thread.start()
        
        # Keep scan input focused
        self.after(500, self.refocus_scan_input)
        
        # Protocol on window close: lock machine
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def exit_fullscreen(self, event=None):
        self.is_fullscreen = False
        self.attributes("-fullscreen", False)

    def on_close(self):
        # Guarantee machine is locked on app exit
        try:
            self.write_plc_permit(0)
        except Exception:
            pass
        self.destroy()

    def create_widgets(self):
        # ── Header ───────────────────────────────────────────
        header = tk.Frame(self, bg="#1E293B", height=70)
        header.pack(fill="x", padx=10, pady=5)
        
        title = tk.Label(
            header,
            text="PG ELECTROPLAST — CONDENSER BENDING POKA-YOKE",
            font=("Segoe UI", 16, "bold"),
            fg="#F8FAFC",
            bg="#1E293B"
        )
        title.pack(side="left", padx=15, pady=12)
        
        self.lbl_status = tk.Label(
            header,
            text="CONNECTING TO PLC...",
            font=("Segoe UI", 11, "bold"),
            fg="#F59E0B",
            bg="#1E293B"
        )
        self.lbl_status.pack(side="right", padx=15, pady=12)
        
        # ── Active Recipe Bar ─────────────────────────────────
        recipe_frame = tk.Frame(self, bg="#334155")
        recipe_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_active_prog = tk.Label(
            recipe_frame,
            text="MACHINE ACTIVE PROGRAM: READING...",
            font=("Segoe UI", 14, "bold"),
            fg="#38BDF8",
            bg="#334155"
        )
        self.lbl_active_prog.pack(side="left", padx=15, pady=8)
        
        self.lbl_prog_details = tk.Label(
            recipe_frame,
            text="",
            font=("Segoe UI", 12),
            fg="#E2E8F0",
            bg="#334155"
        )
        self.lbl_prog_details.pack(side="right", padx=15, pady=8)
        
        # ── Giant Result Banner ───────────────────────────────
        self.card_result = tk.Frame(self, bg="#1E293B", height=200)
        self.card_result.pack(fill="x", padx=10, pady=8)
        self.card_result.pack_propagate(False)
        
        self.lbl_main_status = tk.Label(
            self.card_result,
            text="READY — PLEASE SCAN COIL",
            font=("Segoe UI", 26, "bold"),
            fg="#94A3B8",
            bg="#1E293B"
        )
        self.lbl_main_status.pack(expand=True)
        
        self.lbl_sub_status = tk.Label(
            self.card_result,
            text="Machine is LOCKED (D5000 = 0)",
            font=("Segoe UI", 13),
            fg="#94A3B8",
            bg="#1E293B"
        )
        self.lbl_sub_status.pack(pady=5)
        
        # ── Scan Input Bar ────────────────────────────────────
        scan_bar = tk.Frame(self, bg="#1E293B")
        scan_bar.pack(fill="x", padx=10, pady=5)
        
        lbl_scan = tk.Label(
            scan_bar,
            text="📷 SCAN COIL QR:",
            font=("Segoe UI", 12, "bold"),
            fg="#F8FAFC",
            bg="#1E293B"
        )
        lbl_scan.pack(side="left", padx=10, pady=10)
        
        self.ent_scan = tk.Entry(
            scan_bar,
            font=("Consolas", 15, "bold"),
            bg="#0F172A",
            fg="#38BDF8",
            insertbackground="white",
            relief="solid",
            bd=1
        )
        self.ent_scan.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        self.ent_scan.bind("<Return>", self.on_qr_scanned)
        
        btn_relock = tk.Button(
            scan_bar,
            text="🔒 LOCK / NEXT PIECE",
            font=("Segoe UI", 11, "bold"),
            bg="#DC2626",
            fg="white",
            relief="flat",
            command=self.lock_machine,
            padx=15,
            pady=5,
            cursor="hand2"
        )
        btn_relock.pack(side="right", padx=10, pady=10)
        
        # ── Production Counters ───────────────────────────────
        stats_frame = tk.Frame(self, bg="#0F172A")
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_total_badge = tk.Label(
            stats_frame,
            text="TOTAL SCANS: 0",
            font=("Segoe UI", 11, "bold"),
            fg="#38BDF8",
            bg="#1E293B",
            padx=15,
            pady=6
        )
        self.lbl_total_badge.pack(side="left", padx=5)

        self.lbl_ok_badge = tk.Label(
            stats_frame,
            text="CORRECT (OK): 0",
            font=("Segoe UI", 11, "bold"),
            fg="#10B981",
            bg="#1E293B",
            padx=15,
            pady=6
        )
        self.lbl_ok_badge.pack(side="left", padx=5)
        
        self.lbl_ng_badge = tk.Label(
            stats_frame,
            text="WRONG COUNT (NG): 0",
            font=("Segoe UI", 11, "bold"),
            fg="#EF4444",
            bg="#1E293B",
            padx=15,
            pady=6
        )
        self.lbl_ng_badge.pack(side="left", padx=5)
        
        # ── Recent Scans History Table ────────────────────────
        tbl_frame = tk.Frame(self, bg="#1E293B")
        tbl_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("time", "prog", "scanned_qr", "status", "action")
        self.tree = ttk.Treeview(tbl_frame, columns=columns, show="headings", height=8)
        self.tree.heading("time", text="Timestamp")
        self.tree.heading("prog", text="Machine Program")
        self.tree.heading("scanned_qr", text="Scanned Barcode / Serial")
        self.tree.heading("status", text="Result")
        self.tree.heading("action", text="Machine State")
        
        self.tree.column("time", width=140)
        self.tree.column("prog", width=120)
        self.tree.column("scanned_qr", width=260)
        self.tree.column("status", width=100)
        self.tree.column("action", width=160)
        
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

    def refocus_scan_input(self):
        """Keep focus on scanner input so operator never has to click."""
        try:
            self.ent_scan.focus_set()
        except Exception:
            pass
        self.after(1500, self.refocus_scan_input)

    def poll_plc_loop(self):
        """Background loop to continuously read D1017 from PLC."""
        while True:
            try:
                plc = pymcprotocol.Type3E(plctype="Q")
                plc.setaccessopt(commtype="binary")
                plc.connect(PLC_IP, PLC_PORT)
                
                # Read active program
                val = plc.batchread_wordunits(headdevice=REG_READ_PROG, readsize=1)[0]
                plc.close()
                
                self.plc_connected = True
                
                # If operator changed program on HMI, auto-relock for safety!
                if self.last_program != 0 and val != self.last_program:
                    threading.Thread(target=self.write_plc_permit, args=(0,), daemon=True).start()
                
                self.last_program = val
                self.current_program = val
                
                # Update GUI
                self.after(0, self.update_plc_status, True, val)
                
            except Exception as e:
                self.plc_connected = False
                self.after(0, self.update_plc_status, False, 0)
                
            time.sleep(1.5)

    def update_plc_status(self, is_online: bool, prog_no: int):
        if is_online:
            self.lbl_status.config(text=f"🟢 PLC CONNECTED ({PLC_IP})", fg="#10B981")
            recipe = self.recipes.get(str(prog_no), {})
            name = recipe.get("name", f"Model #{prog_no}")
            angle = recipe.get("angle", "-")
            length = recipe.get("coil_length", "-")
            
            self.lbl_active_prog.config(text=f"ACTIVE PROGRAM: {prog_no} — {name}")
            self.lbl_prog_details.config(text=f"Angle: {angle}° | Length: {length} mm")
        else:
            self.lbl_status.config(text=f"🔴 PLC OFFLINE", fg="#EF4444")
            self.lbl_active_prog.config(text="PLC DISCONNECTED — CHECK NETWORK")

    def on_qr_scanned(self, event=None):
        raw_text = self.ent_scan.get().strip()
        self.ent_scan.delete(0, tk.END)
        
        if not raw_text:
            return
            
        # Dynamically reload recipes from file so edits reflect immediately
        self.recipes = load_recipes()
            
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prog_str = str(self.current_program)
        recipe = self.recipes.get(prog_str, {})
        allowed = recipe.get("allowed_codes", [])
        
        # Check match (prefix matching or exact match)
        is_match = False
        upper_scan = raw_text.upper()
        
        if allowed:
            for code in allowed:
                clean_code = code.strip().upper()
                if clean_code and clean_code in upper_scan:
                    is_match = True
                    break
        else:
            # If no codes configured yet for this program, block for safety
            is_match = False
            
        if is_match:
            self.handle_match(raw_text, timestamp)
        else:
            self.handle_mismatch(raw_text, timestamp, allowed)

    def handle_match(self, scanned_code: str, timestamp: str):
        self.total_count += 1
        self.ok_count += 1
        self.lbl_total_badge.config(text=f"TOTAL SCANS: {self.total_count}")
        self.lbl_ok_badge.config(text=f"CORRECT (OK): {self.ok_count}")
        
        # Cancel any previous auto-relock timer
        if self.relock_timer_id:
            self.after_cancel(self.relock_timer_id)
            self.relock_timer_id = None
        
        # Write 1 to D5000 (Allow Bending)
        threading.Thread(target=self.write_plc_permit, args=(1,), daemon=True).start()
        
        # Update Visuals
        self.card_result.config(bg="#065F46")  # Emerald Dark
        self.lbl_main_status.config(
            text="✅ MATCH OK — BENDING ALLOWED",
            fg="#34D399",
            bg="#065F46"
        )
        self.lbl_sub_status.config(
            text=f"Coil: {scanned_code} | Machine UNLOCKED (D5000 = 1)",
            fg="#A7F3D0",
            bg="#065F46"
        )
        
        # Success sound
        try:
            winsound.Beep(1200, 200)
        except Exception:
            pass
            
        self.add_log_record(timestamp, self.current_program, scanned_code, "PASS", "UNLOCKED (1)")
        
        # Auto-relock after N seconds for safety (prevents running 2nd piece without scan)
        self.relock_timer_id = self.after(AUTO_RELOCK_DELAY_SEC * 1000, self.auto_relock)

    def handle_mismatch(self, scanned_code: str, timestamp: str, expected_codes: list):
        self.total_count += 1
        self.ng_count += 1
        self.lbl_total_badge.config(text=f"TOTAL SCANS: {self.total_count}")
        self.lbl_ng_badge.config(text=f"WRONG COUNT (NG): {self.ng_count}")
        
        # Cancel any previous auto-relock timer
        if self.relock_timer_id:
            self.after_cancel(self.relock_timer_id)
            self.relock_timer_id = None
            
        # Write 0 to D5000 (Hard Lock)
        threading.Thread(target=self.write_plc_permit, args=(0,), daemon=True).start()
        
        # Update Visuals
        self.card_result.config(bg="#7F1D1D")  # Dark Crimson
        self.lbl_main_status.config(
            text="⛔ WRONG COIL! BENDING BLOCKED!",
            fg="#FCA5A5",
            bg="#7F1D1D"
        )
        exp_text = ", ".join(expected_codes) if expected_codes else "NO CODES CONFIGURED"
        self.lbl_sub_status.config(
            text=f"Scanned: {scanned_code} | Expected: {exp_text} | Machine LOCKED (D5000 = 0)",
            fg="#FECACA",
            bg="#7F1D1D"
        )
        
        # Warning Siren (non-blocking)
        def siren():
            for _ in range(3):
                try:
                    winsound.Beep(800, 150)
                    time.sleep(0.05)
                except Exception:
                    pass
        threading.Thread(target=siren, daemon=True).start()
        
        self.add_log_record(timestamp, self.current_program, scanned_code, "FAIL (NG)", "LOCKED (0)")

    def auto_relock(self):
        """Auto lock machine after bending permit timeout."""
        threading.Thread(target=self.write_plc_permit, args=(0,), daemon=True).start()
        self.card_result.config(bg="#1E293B")
        self.lbl_main_status.config(
            text="READY — PLEASE SCAN COIL",
            fg="#94A3B8",
            bg="#1E293B"
        )
        self.lbl_sub_status.config(
            text="Cycle finished | Machine LOCKED (D5000 = 0)",
            fg="#94A3B8",
            bg="#1E293B"
        )

    def write_plc_permit(self, value: int):
        try:
            plc = pymcprotocol.Type3E(plctype="Q")
            plc.setaccessopt(commtype="binary")
            plc.connect(PLC_IP, PLC_PORT)
            plc.batchwrite_wordunits(headdevice=REG_WRITE_PERMIT, values=[value])
            plc.close()
        except Exception as e:
            print(f"Error writing to {REG_WRITE_PERMIT}: {e}")

    def lock_machine(self):
        """Manual / Next coil lock button."""
        if self.relock_timer_id:
            self.after_cancel(self.relock_timer_id)
            self.relock_timer_id = None
            
        threading.Thread(target=self.write_plc_permit, args=(0,), daemon=True).start()
        self.card_result.config(bg="#1E293B")
        self.lbl_main_status.config(
            text="READY — PLEASE SCAN COIL",
            fg="#94A3B8",
            bg="#1E293B"
        )
        self.lbl_sub_status.config(
            text="Machine is LOCKED (D5000 = 0)",
            fg="#94A3B8",
            bg="#1E293B"
        )

    def add_log_record(self, timestamp: str, prog: int, scanned: str, status: str, action: str):
        # Insert in UI table
        self.tree.insert("", 0, values=(timestamp, f"Program {prog}", scanned, status, action))
        
        # Append to CSV
        log_file = LOG_DIR / f"bending_log_{datetime.now().strftime('%Y%m%d')}.csv"
        file_exists = log_file.exists()
        try:
            with open(log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Program", "Scanned_Code", "Status", "Machine_State"])
                writer.writerow([timestamp, prog, scanned, status, action])
        except Exception as e:
            print(f"Error writing CSV log: {e}")


if __name__ == "__main__":
    app = PokaYokeApp()
    app.mainloop()
