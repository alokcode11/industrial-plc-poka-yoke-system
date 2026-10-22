"""
Quick Tool: Set D5000 register value (0 or 1)
Usage:
    python set_d5000.py 0
    python set_d5000.py 1
"""
import sys
import pymcprotocol

PLC_IP = "192.168.19.206"
PLC_PORT = 8500

if len(sys.argv) < 2:
    val = input("Enter value to write into D5000 (0 or 1): ").strip()
else:
    val = sys.argv[1].strip()

if val not in ('0', '1'):
    print("[ERROR] Invalid input! Only 0 or 1 is allowed.")
    sys.exit(1)

value_to_write = int(val)

try:
    plc = pymcprotocol.Type3E(plctype="Q")
    plc.setaccessopt(commtype="binary")
    plc.connect(PLC_IP, PLC_PORT)
    
    # Write to D5000
    plc.batchwrite_wordunits(headdevice="D5000", values=[value_to_write])
    
    # Readback verify
    readback = plc.batchread_wordunits(headdevice="D5000", readsize=1)[0]
    plc.close()
    
    print("=" * 45)
    print(f"[SUCCESS] Wrote {value_to_write} to D5000")
    print(f"[VERIFIED] Readback from PLC: {readback}")
    if readback == 0:
        print("[STATUS] Machine State: LOCKED (D5000 = 0)")
    else:
        print("[STATUS] Machine State: UNLOCKED (D5000 = 1)")
    print("=" * 45)

except Exception as e:
    print(f"[ERROR] Communication with PLC failed: {e}")
