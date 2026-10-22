"""
Step 4: Write to PLC Data Register via MC Protocol (SLMP 3E Binary)
===================================================================
Purpose: Transmit an interlock control command (0 or 1) to the designated
         safety register (D5000) on the Mitsubishi PLC.
         - 1 = Authorize / Permit Machine Bending Cycle
         - 0 = Interlock / Inhibit Machine Bending Cycle

Protocol: MELSEC MC Protocol (Type 3E Binary Frame over TCP)
PLC Endpoint: 192.168.19.206:8500
Target Register: D5000 (Safety Permit Bit)
Execution: python step4_write_register.py
"""

import struct
import socket
import sys
from datetime import datetime

# ─── PLC Configuration ───────────────────────────────────────
PLC_IP = "192.168.19.206"
PLC_PORT = 8500
TIMEOUT_SECONDS = 5
WRITE_REGISTER = "D5000"  # Dedicated interlock register


# ═══════════════════════════════════════════════════════════════
# METHOD 1: Using pymcprotocol library (Standard Implementation)
# ═══════════════════════════════════════════════════════════════

def write_with_pymcprotocol(register: str, value: int) -> bool:
    """Write an integer value to the target D-register using pymcprotocol."""
    try:
        import pymcprotocol
    except ImportError:
        print("[ERROR] pymcprotocol library is not installed.")
        return False

    try:
        pymc3e = pymcprotocol.Type3E(plctype="Q")
        pymc3e.setaccessopt(commtype="binary")

        print(f"Connecting to PLC at {PLC_IP}:{PLC_PORT}...")
        pymc3e.connect(PLC_IP, PLC_PORT)
        print("[CONNECTED] Session established.")

        print(f"Writing value {value} to {register}...")
        pymc3e.batchwrite_wordunits(headdevice=register, values=[value])
        print(f"[SUCCESS] Command transmitted to {register}.")

        # Perform verification read-back
        readback = pymc3e.batchread_wordunits(headdevice=register, readsize=1)[0]
        print(f"[VERIFIED] Readback verification: {register} = {readback}")

        if readback == value:
            print("[CONFIRMED] Target register reflects written state.")
        else:
            print(f"[WARNING] Readback value ({readback}) differs from written value ({value}).")
            print("          PLC ladder scan may be overwriting this register.")

        pymc3e.close()
        return True

    except Exception as e:
        print(f"[ERROR] Communication failure: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# METHOD 2: Raw Socket 3E Binary Construction (Fallback)
# ═══════════════════════════════════════════════════════════════

def build_mc3e_write_request(register_number: int, value: int) -> bytes:
    """Build MC Protocol 3E Binary batch write frame (Command 1401h)."""
    subheader = b"\x50\x00"
    network_no = b"\x00"
    pc_no = b"\xFF"
    dest_io = b"\xFF\x03"
    dest_station = b"\x00"

    monitor_timer = struct.pack("<H", 0x000A)   # 2.5s Timeout
    command = struct.pack("<H", 0x1401)          # 1401h = Batch Write
    subcommand = struct.pack("<H", 0x0000)       # Word Access Units

    device_number = struct.pack("<I", register_number)[:3]
    device_code = b"\xA8"                        # Device Code for D-Register
    num_points = struct.pack("<H", 1)
    write_data = struct.pack("<H", value & 0xFFFF)

    data_body = (
        monitor_timer
        + command
        + subcommand
        + device_number
        + device_code
        + num_points
        + write_data
    )
    data_length = struct.pack("<H", len(data_body))

    return (
        subheader
        + network_no
        + pc_no
        + dest_io
        + dest_station
        + data_length
        + data_body
    )


def write_with_raw_socket(register: str, value: int) -> bool:
    """Direct TCP socket batch write for MC Protocol 3E Binary."""
    reg_num = int(register[1:])

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT_SECONDS)
        sock.connect((PLC_IP, PLC_PORT))

        request = build_mc3e_write_request(reg_num, value)
        sock.sendall(request)

        response = sock.recv(1024)
        if len(response) >= 11:
            resp_sub = response[0:2]
            end_code = struct.unpack("<H", response[9:11])[0]

            if resp_sub == b"\xD0\x00" and end_code == 0x0000:
                print(f"[SUCCESS] Written {value} to {register} via raw socket.")
                sock.close()
                return True
            else:
                print(f"[FAILURE] PLC returned error End Code: 0x{end_code:04X}")
        else:
            print("[FAILURE] Truncated response received.")

        sock.close()
        return False

    except Exception as e:
        print(f"[ERROR] Socket execution failure: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  STEP 4: PLC Safety Interlock Control")
    print(f"  Target: {PLC_IP}:{PLC_PORT}")
    print(f"  Destination Register: {WRITE_REGISTER}")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    value_input = input("Enter control value to transmit (0 = Lock, 1 = Allow): ").strip()
    if value_input not in ("0", "1"):
        print("[ERROR] Invalid argument. Only binary states '0' or '1' are accepted.")
        sys.exit(1)

    value = int(value_input)
    confirm = input(f"Confirm transmission of value [{value}] to {WRITE_REGISTER}? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("[CANCELLED] Operation aborted by user.")
        sys.exit(0)

    print("-" * 60)
    success = write_with_pymcprotocol(WRITE_REGISTER, value)
    if not success:
        print("Switching to fallback socket driver...")
        success = write_with_raw_socket(WRITE_REGISTER, value)

    print()
    if success:
        print("=" * 60)
        state_str = "UNLOCKED / RUN PERMITTED (1)" if value == 1 else "LOCKED / CYCLE INHIBITED (0)"
        print(f"  MACHINE OPERATIONAL STATE: {state_str}")
        print("=" * 60)
    else:
        print("[FAILURE] Control transmission failed. Verify network and PLC connection.")


if __name__ == "__main__":
    main()
