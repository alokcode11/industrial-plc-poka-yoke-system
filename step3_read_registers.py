"""
Step 3: Read PLC Data Registers via MC Protocol (SLMP 3E Binary)
================================================================
Purpose: Query operational D-registers from the Mitsubishi PLC to inspect
         the currently loaded bending recipe and operational parameters.

Key Registers:
  - D1017: Active Machine Program Index (Validated via HMI selection)
  - D1022: Machine Bending Parameter Register
  - D5000: Operational Interlock Register (0 = Locked, 1 = Permitted)

Protocol: MELSEC MC Protocol (Type 3E Binary Frame over TCP)
PLC Endpoint: 192.168.19.206:8500
Execution: python step3_read_registers.py
"""

import sys
import struct
import socket
from datetime import datetime

# ─── PLC Configuration ───────────────────────────────────────
PLC_IP = "192.168.19.206"
PLC_PORT = 8500
TIMEOUT_SECONDS = 5

# ─── Target Registers ─────────────────────────────────────────
REGISTERS_TO_READ = [
    ("D1000", 6, "D1000-D1005 (Header / Mode Parameters)"),
    ("D1017", 1, "D1017 (Active Machine Recipe / Program No.)"),
    ("D1020", 1, "D1020 (Position / Feedback Encoder Count)"),
    ("D1022", 1, "D1022 (Machine Parameter / Angle Setting)"),
    ("D1024", 1, "D1024 (Speed / Stroke Configuration)"),
    ("D1026", 1, "D1026 (Auxiliary Register)"),
    ("D5000", 1, "D5000 (Safety Interlock Status: 0=Lock, 1=Allow)"),
    ("D7001", 1, "D7001 (Auxiliary Storage Register)"),
]


# ═══════════════════════════════════════════════════════════════
# METHOD 1: Using pymcprotocol library (Standard Implementation)
# ═══════════════════════════════════════════════════════════════

def read_with_pymcprotocol():
    """Batch-read target registers using the native pymcprotocol driver."""
    try:
        import pymcprotocol
    except ImportError:
        print("[ERROR] pymcprotocol library is not installed.")
        print("        Install via: pip install pymcprotocol")
        print("        Falling back to raw socket implementation...")
        return None

    print("Executing Driver: pymcprotocol (Method 1)")
    print("-" * 60)

    results = {}

    try:
        # Initialize MC Protocol 3E Binary communication (plctype Q/L/iQ)
        pymc3e = pymcprotocol.Type3E(plctype="Q")
        pymc3e.setaccessopt(commtype="binary")

        print(f"Connecting to PLC at {PLC_IP}:{PLC_PORT}...")
        pymc3e.connect(PLC_IP, PLC_PORT)
        print("[CONNECTED] Successfully established MC Protocol session.")
        print()

        for head_device, count, description in REGISTERS_TO_READ:
            try:
                values = pymc3e.batchread_wordunits(
                    headdevice=head_device, readsize=count
                )
                reg_num = int(head_device[1:])
                print(f"  Reading: {description}")
                for i, val in enumerate(values):
                    reg_name = f"D{reg_num + i}"
                    signed_val = val if val < 32768 else val - 65536
                    results[reg_name] = signed_val
                    print(f"     {reg_name} = {signed_val:6d} (0x{val:04X})")
                print()
            except Exception as e:
                print(f"  [WARNING] Read error on {description}: {e}")
                print()

        pymc3e.close()
        print("Session closed cleanly.")
        return results

    except Exception as e:
        print(f"[ERROR] Communication exception encountered: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# METHOD 2: Raw Socket 3E Binary Frame Construction (Fallback)
# ═══════════════════════════════════════════════════════════════

def build_mc3e_read_request(start_register: int, count: int) -> bytes:
    """Construct an MC Protocol 3E Binary batch read frame for word units."""
    subheader = b"\x50\x00"           # 3E Binary Request subheader
    network_no = b"\x00"              # Network Station 0
    pc_no = b"\xFF"                   # Host PLC Station (0xFF)
    dest_io = b"\xFF\x03"             # Destination I/O (0x03FF)
    dest_station = b"\x00"            # Multi-drop Station 0

    monitor_timer = struct.pack("<H", 0x000A)  # 2.5s Timeout
    command = struct.pack("<H", 0x0401)        # 0401h = Batch Read
    subcommand = struct.pack("<H", 0x0000)     # 0000h = Word Access Units

    # Head device: 24-bit integer (little-endian) + 1-byte Device Code (0xA8 for D)
    device_number = struct.pack("<I", start_register)[:3]
    device_code = b"\xA8"
    num_points = struct.pack("<H", count)

    data_body = (
        monitor_timer
        + command
        + subcommand
        + device_number
        + device_code
        + num_points
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


def parse_mc3e_read_response(response: bytes, expected_count: int):
    """Decode MC Protocol 3E Binary response payload and parse 16-bit word values."""
    if len(response) < 11:
        return None, f"Response payload truncated ({len(response)} bytes received)."

    if response[0:2] != b"\xD0\x00":
        return None, f"Unexpected response subheader: {response[0:2].hex()}"

    end_code = struct.unpack("<H", response[9:11])[0]
    if end_code != 0x0000:
        return None, f"PLC reported error End Code: 0x{end_code:04X}"

    raw_data = response[11:]
    expected_bytes = expected_count * 2
    if len(raw_data) < expected_bytes:
        return None, f"Insufficient payload data: expected {expected_bytes} bytes, received {len(raw_data)}."

    values = []
    for i in range(expected_count):
        raw_val = struct.unpack("<H", raw_data[i * 2 : i * 2 + 2])[0]
        signed_val = raw_val if raw_val < 32768 else raw_val - 65536
        values.append(signed_val)

    return values, None


def read_with_raw_socket():
    """Direct TCP socket implementation for MC Protocol 3E binary reading."""
    print("Executing Driver: Raw Socket MC 3E Binary (Method 2)")
    print("-" * 60)

    results = {}

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT_SECONDS)
        sock.connect((PLC_IP, PLC_PORT))
        print("[CONNECTED] Direct socket established.")
        print()

        for head_device, count, description in REGISTERS_TO_READ:
            reg_num = int(head_device[1:])
            request = build_mc3e_read_request(reg_num, count)
            sock.sendall(request)

            response = sock.recv(1024)
            values, error = parse_mc3e_read_response(response, count)

            if error:
                print(f"  [ERROR] {description}: {error}")
            else:
                for i, val in enumerate(values):
                    reg_name = f"D{reg_num + i}"
                    results[reg_name] = val
                    print(f"     {reg_name} = {val:6d}")

            print()

        sock.close()
        return results

    except Exception as e:
        print(f"[ERROR] Socket communication failure: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  STEP 3: PLC Register Telemetry Inspection")
    print(f"  Target: {PLC_IP}:{PLC_PORT}")
    print("  Protocol: Mitsubishi MC Protocol 3E Binary (SLMP)")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    results = read_with_pymcprotocol()
    if results is None:
        results = read_with_raw_socket()

    if results:
        print("=" * 60)
        print("  SUMMARY: Current Register State")
        print("=" * 60)
        for reg, val in sorted(results.items(), key=lambda x: int(x[0][1:])):
            print(f"  {reg:8s} = {val:8d}")
        print()
    else:
        print("[FAILURE] Unable to retrieve register data from PLC.")


if __name__ == "__main__":
    main()
