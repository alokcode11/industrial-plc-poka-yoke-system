"""
Step 5: Register Discovery Diagnostic Utility
==============================================
Purpose: Perform range scans across PLC data registers (D-area) to detect
         active operational parameters, recipe index shifts, and machine state.
Execution: python step5_register_discovery.py
"""

import sys
from datetime import datetime

PLC_IP = "192.168.19.206"
PLC_PORT = 8500


def discover_registers():
    """Scan candidate register ranges and display all non-zero operational values."""
    try:
        import pymcprotocol
    except ImportError:
        print("[ERROR] Required library missing. Execute: pip install pymcprotocol")
        sys.exit(1)

    print("=" * 70)
    print("  STEP 5: PLC Register Discovery & Telemetry Scan")
    print(f"  Target Endpoint: {PLC_IP}:{PLC_PORT}")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    scan_ranges = [
        (0, 30, "D0 - D29 (Machine Mode & Axis Status)"),
        (1000, 1030, "D1000 - D1029 (Recipe & Primary Control Area)"),
        (2000, 2030, "D2000 - D2029 (Auxiliary Parameter Block)"),
        (5000, 5010, "D5000 - D5009 (Safety Interlock & Handshake)"),
        (7000, 7030, "D7000 - D7029 (Recipe Backup & Mirror Block)"),
    ]

    try:
        pymc3e = pymcprotocol.Type3E(plctype="Q")
        pymc3e.setaccessopt(commtype="binary")
        pymc3e.connect(PLC_IP, PLC_PORT)
        print("[CONNECTED] Scanning target address ranges...")
        print()

        all_values = {}

        for start, end, description in scan_ranges:
            count = end - start
            print(f"Scanning: {description}...")

            try:
                values = pymc3e.batchread_wordunits(
                    headdevice=f"D{start}", readsize=count
                )
                for i, val in enumerate(values):
                    reg = f"D{start + i}"
                    all_values[reg] = val

                    if val != 0:
                        signed_val = val if val < 32768 else val - 65536
                        print(
                            f"  * {reg:8s} = {val:6d} "
                            f"(Signed: {signed_val:6d}, Hex: 0x{val:04X})"
                        )

            except Exception as e:
                print(f"  [WARNING] Scan error on {description}: {e}")

            print()

        pymc3e.close()

        non_zero = {k: v for k, v in all_values.items() if v != 0}
        print("=" * 70)
        print(f"  SCAN COMPLETE: {len(non_zero)} active non-zero registers detected "
              f"out of {len(all_values)} inspected.")
        print("=" * 70)

        if non_zero:
            for reg in sorted(non_zero.keys(), key=lambda x: int(x[1:])):
                val = non_zero[reg]
                signed_val = val if val < 32768 else val - 65536
                print(f"  {reg:8s} = {val:6d}  (0x{val:04X})")

        return all_values

    except Exception as e:
        print(f"[ERROR] Communication failure: {e}")
        return None


if __name__ == "__main__":
    discover_registers()
