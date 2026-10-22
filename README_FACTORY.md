# PG Electroplast — Condenser Bending Poka-Yoke System
## Factory Operations & Technical Deployment Guide

---

## 1. System Overview

This application provides automated error-proofing (Poka-Yoke) for the industrial condenser coil bending line. It establishes a real-time communication bridge between a 2D Barcode/QR Scanner and the machine's Mitsubishi PLC via the MELSEC MC Protocol (SLMP 3E Binary over TCP).

The system continuously verifies that the physical coil loaded by the operator matches the active machine recipe selected on the HMI. If a mismatch is detected, the machine's operational circuit is locked via PLC register interlock, preventing scrap parts and eliminating potential production losses.

---

## 2. Quick Start Guide

No command-line interaction or development tools are required:
1. Double-click **`Start_Bending_PokaYoke.bat`** on the station desktop.
2. The application will launch and establish a live session with the PLC.
3. Press **`F11`** at any time to toggle fullscreen kiosk mode (Press **`Esc`** to exit fullscreen).

---

## 3. Operational Workflow

```
[ Operator Shift Starts ]
      │
      ▼
1. Operator selects target program on the machine HMI (e.g., Program 4)
      │
      ▼
2. Application automatically detects the selection from register D1017:
   "ACTIVE PROGRAM: 4 — 1.5R-5MM 806MM 20\" CHESSIS"
      │
      ▼
3. Operator scans the QR code label on the coil using the Honeywell scanner gun
      │
      ├───────────────────────────────┬───────────────────────────────┐
      ▼                                                               ▼
   [ VALID MATCH (PASS) ]                                          [ MISMATCH DETECTED (FAIL) ]
   • Banner: Emerald Green (MATCH OK)                              • Banner: Crimson Red (WRONG COIL)
   • D5000 = 1 (Machine Cycle Permitted)                           • D5000 = 0 (Machine Hard Locked)
   • Foot pedal operates normally                                  • Foot pedal disabled; machine idle
   • Auto-relocks after 20 seconds                                 • Audible alarm alerts operator
   • Transaction logged to CSV                                     • Incident logged with scrap saved counter
```

---

## 4. Master Recipe Configuration (`recipe_config.json`)

To add or update authorized part numbers and QR codes for any of the 19 programs:
1. Open **`recipe_config.json`** in Notepad or any text editor.
2. Locate the corresponding program key and insert the authorized Part Number or barcode prefix inside `allowed_codes: []`.

### Example:
```json
  "4": {
    "name": "1.5R-5MM 806MM 20\" CHESSIS",
    "coil_length": 806,
    "angle": 113,
    "allowed_codes": ["AM26FG0484", "7020003556"]
  }
```

> **Hot Reload:** The application reloads `recipe_config.json` dynamically on each scan. No software restart is required after saving recipe modifications.

---

## 5. Automated Windows Startup (Kiosk Configuration)

To ensure the application starts automatically when the industrial workstation boots:
1. Press `Win + R`, enter `shell:startup`, and press Enter.
2. Create a shortcut to **`Start_Bending_PokaYoke.bat`** and place it in the opened Startup folder.
3. Upon system power-on, the Poka-Yoke interface will launch automatically.

---

## 6. Technical Specifications & Verified Hardware Interface

| Parameter | Specification |
| :--- | :--- |
| **PLC Controller** | Mitsubishi iQ-F / FX5U Series |
| **Programming Environment** | GX Works 3 |
| **PLC IP Address** | `192.168.19.206` |
| **Communication Port** | `8500` (MC Protocol 3E Binary Frame) |
| **Active Recipe Register** | `D1017` (Live telemetry read) |
| **Safety Interlock Register** | `D5000` (`1` = Permit, `0` = Inhibit/Lock) |
| **2D Scanner Interface** | Honeywell 2D Industrial Imager (USB HID Keyboard Emulation) |
| **Audit Logging** | Local CSV records stored in `logs/bending_log_YYYYMMDD.csv` |
