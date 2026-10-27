"""
CLI Application: Condenser Bending Poka-Yoke Terminal System
=============================================================
Provides console-based automated error-proofing:
  1. Queries active recipe from PLC (D1017) via MC Protocol 3E Binary.
  2. Acquires barcode/QR scan from USB industrial imager.
  3. Validates scanned serial prefix against authorized recipe codes.
  4. Transmits permit signal to D5000 (1 = Allow, 0 = Inhibit).
  5. Records all transactions to local audit log.

Execution: python main_app.py
"""

import os
import sys
import csv
from datetime import datetime
from pathlib import Path

# Optional dotenv loader with safe fallback
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── PLC Configuration (Environment with safe defaults) ───────
PLC_IP = os.getenv("PLC_IP", "192.168.19.206")
PLC_PORT = int(os.getenv("PLC_PORT", 8500))
REGISTER_READ = os.getenv("REG_READ_PROG", "D1017")      # Active Machine Recipe
REGISTER_WRITE = os.getenv("REG_WRITE_PERMIT", "D5000")   # Interlock Control: 1 = Allow, 0 = Lock

# ─── Program ↔ QR Code Mapping ───────────────────────────────
PROGRAM_QR_MAP = {
    1: ["AJK0001728"],
    2: [],
    3: [],
    4: ["FAM26FG0484", "AM26FG0484"],
    5: [],
    6: [],
    7: [],
    8: [],
    9: [],
    10: [],
    17: ["FAM26FG0484", "AM26FG0484", "7020003556"],
}

# ─── CSV Log Configuration ────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / f"bending_log_{datetime.now().strftime('%Y%m')}.csv"


# ═══════════════════════════════════════════════════════════════
# PLC COMMUNICATION CLIENT
# ═══════════════════════════════════════════════════════════════

class PLCConnection:
    """Manages MC Protocol 3E Binary sessions with the Mitsubishi PLC."""

    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        self.pymc3e = None
        self.connected = False

    def connect(self) -> bool:
        """Establish connection to PLC."""
        try:
            import pymcprotocol
            self.pymc3e = pymcprotocol.Type3E(plctype="Q")
            self.pymc3e.setaccessopt(commtype="binary")
            self.pymc3e.connect(self.ip, self.port)
            self.connected = True
            return True
        except Exception as e:
            print(f"[ERROR] PLC Connection Failed: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Terminate connection cleanly."""
        if self.pymc3e and self.connected:
            try:
                self.pymc3e.close()
            except Exception:
                pass
            self.connected = False

    def read_register(self, register: str) -> int | None:
        """Query a single word register."""
        if not self.connected:
            if not self.connect():
                return None

        try:
            values = self.pymc3e.batchread_wordunits(
                headdevice=register, readsize=1
            )
            return values[0]
        except Exception as e:
            print(f"[ERROR] Read failure ({register}): {e}")
            self.connected = False
            return None

    def write_register(self, register: str, value: int) -> bool:
        """Transmit an integer value to a target register."""
        if not self.connected:
            if not self.connect():
                return False

        try:
            self.pymc3e.batchwrite_wordunits(
                headdevice=register, values=[value]
            )
            return True
        except Exception as e:
            print(f"[ERROR] Write failure ({register}={value}): {e}")
            self.connected = False
            return False


# ═══════════════════════════════════════════════════════════════
# CSV AUDIT LOGGING
# ═══════════════════════════════════════════════════════════════

def init_log():
    """Ensure log directory exists and write CSV header if new."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Timestamp",
                "Operator_Name",
                "PLC_Program_Number",
                "Scanned_QR_Code",
                "Expected_QR_Codes",
                "Status",
                "Action_Taken",
            ])


def log_scan(operator: str, program_no: int, qr_code: str,
             expected: list, status: str, action: str):
    """Append a record to the operational audit log."""
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            operator,
            program_no,
            qr_code,
            "; ".join(expected) if expected else "NONE",
            status,
            action,
        ])


# ═══════════════════════════════════════════════════════════════
# USER INTERFACE & DISPATCH LOOP
# ═══════════════════════════════════════════════════════════════

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def display_header(operator: str):
    print("=" * 65)
    print("  PG ELECTROPLAST — CONDENSER BENDING POKA-YOKE")
    print(f"  Station Operator: {operator}")
    print(f"  Target PLC: {PLC_IP}:{PLC_PORT}")
    print(f"  Session Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)


def display_match(program_no: int, qr_code: str):
    print()
    print("  +-------------------------------------------------------------+")
    print("  |                [PASS] MATCH VERIFIED (OK)                   |")
    print(f"  |  Program: {program_no:<5}       Barcode: {qr_code:<27} |")
    print("  |          MACHINE UNLOCKED -- BENDING PERMITTED              |")
    print("  +-------------------------------------------------------------+")
    print()


def display_mismatch(program_no: int, qr_code: str, expected: list):
    print()
    print("  +-------------------------------------------------------------+")
    print("  |             [FAIL] MISMATCH DETECTED (NG)                   |")
    print(f"  |  Active Program : {program_no:<42} |")
    print(f"  |  Scanned Code   : {qr_code:<42} |")
    print(f"  |  Expected Code  : {', '.join(expected) if expected else 'NOT CONFIGURED':<42} |")
    print("  |         MACHINE HARD LOCKED -- BENDING INHIBITED            |")
    print("  +-------------------------------------------------------------+")
    print()


def main():
    clear_screen()
    print("=" * 65)
    print("  CONDENSER BENDING — POKA-YOKE CONSOLE INTERFACE")
    print("=" * 65)
    print()

    operator = input("  Enter Operator Identifier: ").strip()
    if not operator:
        operator = "Operator_Line1"

    init_log()
    plc = PLCConnection(PLC_IP, PLC_PORT)

    print()
    print("  Establishing connection with Mitsubishi PLC...")
    if not plc.connect():
        print("  [FAILURE] Unable to connect to PLC endpoint.")
        input("  Press Enter to exit...")
        sys.exit(1)

    print("  [SUCCESS] Connected to PLC.")
    scan_count = 0

    while True:
        clear_screen()
        display_header(operator)
        print()
        print(f"  Total Validated Cycles: {scan_count}")
        print("  Ready for imager input. Scan barcode label (type 'exit' to quit):")
        print()

        qr_input = input("  [SCAN INPUT] > ").strip()
        if qr_input.lower() == "exit":
            break

        if not qr_input:
            continue

        scan_count += 1
        program_no = plc.read_register(REGISTER_READ)

        if program_no is None:
            print("  [ERROR] Failed to query active program from PLC.")
            plc.connect()
            input("  Press Enter to retry...")
            continue

        expected_qr_list = PROGRAM_QR_MAP.get(program_no, [])
        qr_upper = qr_input.upper()

        is_match = False
        if expected_qr_list:
            for exp in expected_qr_list:
                if exp.upper() in qr_upper:
                    is_match = True
                    break

        if is_match:
            plc.write_register(REGISTER_WRITE, 1)  # Unlock machine
            display_match(program_no, qr_input)
            log_scan(operator, program_no, qr_input, expected_qr_list, "PASS", "UNLOCKED (1)")
        else:
            plc.write_register(REGISTER_WRITE, 0)  # Lock machine
            display_mismatch(program_no, qr_input, expected_qr_list)
            log_scan(operator, program_no, qr_input, expected_qr_list, "FAIL", "LOCKED (0)")

        input("  Press Enter for next cycle...")

    plc.write_register(REGISTER_WRITE, 0)
    plc.disconnect()
    print(f"\nSession terminated. {scan_count} transactions logged to: {LOG_FILE}")


if __name__ == "__main__":
    main()
