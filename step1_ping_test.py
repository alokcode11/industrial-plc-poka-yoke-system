"""
Step 1: PLC Network Ping Test
==============================
Purpose: Verify network reachability to the Mitsubishi PLC (192.168.19.206).
Execution: python step1_ping_test.py

Prerequisites: The host PC must reside on the same network subnet (192.168.19.x)
               via an Ethernet cable or authenticated Wi-Fi connection.
"""

import subprocess
import sys

PLC_IP = "192.168.19.206"


def ping_test(ip_address: str, count: int = 4) -> bool:
    """Perform ICMP ping to check basic network connectivity to the target PLC."""
    print("=" * 60)
    print("  STEP 1: PLC Network Reachability Test")
    print(f"  Target Host: {ip_address}")
    print("=" * 60)
    print()

    try:
        # Determine platform-specific ping parameter
        param = "-n" if sys.platform == "win32" else "-c"
        result = subprocess.run(
            ["ping", param, str(count), ip_address],
            capture_output=True,
            text=True,
            timeout=30,
        )

        print(result.stdout)

        if result.returncode == 0:
            print("-" * 60)
            print("[SUCCESS] Target PLC is REACHABLE.")
            print(f"          Host {ip_address} responded to ICMP echo requests.")
            print("          Next Recommended Action: Run step2_tcp_connect_test.py")
            print("-" * 60)
            return True
        else:
            print("-" * 60)
            print("[FAILURE] Target PLC is NOT reachable.")
            print()
            print("Troubleshooting Checklist:")
            print("1. Verify the host PC is configured on the target subnet (192.168.19.x).")
            print("2. Ensure the PLC main power supply is active.")
            print("3. Verify physical Ethernet cable connectivity or Wi-Fi association.")
            print("4. Check corporate firewall and router routing rules.")
            print("-" * 60)
            return False

    except subprocess.TimeoutExpired:
        print("[ERROR] Ping execution timed out after 30 seconds.")
        return False
    except Exception as e:
        print(f"[ERROR] Execution failed: {e}")
        return False


if __name__ == "__main__":
    ping_test(PLC_IP)
