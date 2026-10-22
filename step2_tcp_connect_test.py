"""
Step 2: PLC TCP Port Connection Test
======================================
Purpose: Validate whether the PLC's MELSEC Communication (MC Protocol / SLMP)
         port (TCP 8500) is open and actively accepting incoming TCP connections.
Execution: python step2_tcp_connect_test.py
"""

import socket
import time

PLC_IP = "192.168.19.206"
PLC_PORT = 8500
TIMEOUT_SECONDS = 5


def tcp_connect_test(ip: str, port: int, timeout: float = 5.0) -> bool:
    """Test TCP socket handshake against the target PLC port."""
    print("=" * 60)
    print("  STEP 2: TCP Socket Connection Test")
    print(f"  Target Endpoint: {ip}:{port}")
    print(f"  Connection Timeout: {timeout}s")
    print("=" * 60)
    print()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        print(f"Initiating TCP handshake to {ip}:{port}...")
        start_time = time.time()
        sock.connect((ip, port))
        elapsed = time.time() - start_time

        print(f"TCP socket established in {elapsed:.3f} seconds.")
        print()
        print("-" * 60)
        print("[SUCCESS] Port 8500 is OPEN and accepting connections.")
        print("          MELSEC MC Protocol (SLMP) communication channel is operational.")
        print("          Next Recommended Action: Run step3_read_registers.py")
        print("-" * 60)
        return True

    except socket.timeout:
        print()
        print("-" * 60)
        print(f"[FAILURE] Connection TIMED OUT after {timeout} seconds.")
        print()
        print("Potential Root Causes:")
        print(f"1. Port {port} is not listening on the target device.")
        print("2. Internal PLC firewall or network Access Control List (ACL) is dropping packets.")
        print("3. MC Protocol / SLMP connection parameters not enabled in PLC project settings.")
        print("-" * 60)
        return False

    except ConnectionRefusedError:
        print()
        print("-" * 60)
        print("[FAILURE] Connection actively REFUSED by host.")
        print(f"          Target {ip} is online, but port {port} has no active listening service.")
        print("          Action: Verify SLMP connection settings in GX Works3.")
        print("-" * 60)
        return False

    except OSError as e:
        print()
        print("-" * 60)
        print(f"[FAILURE] Socket error: {e}")
        print("          Execute step1_ping_test.py to verify IP-level connectivity first.")
        print("-" * 60)
        return False

    finally:
        sock.close()


def test_alternative_ports(ip: str) -> None:
    """Scan auxiliary industrial automation ports for diagnostics."""
    print()
    print("=" * 60)
    print("  Diagnostic: Evaluating common industrial communication ports...")
    print("=" * 60)

    common_ports = {
        502: "Modbus TCP (Standard)",
        5000: "MC Protocol (Auxiliary Port 1)",
        5001: "MC Protocol (Auxiliary Port 2)",
        5002: "MC Protocol (Auxiliary Port 3)",
        8500: "MC Protocol (Dedicated Station Port)",
    }

    for port, description in common_ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        try:
            sock.connect((ip, port))
            status = "[OPEN]"
        except (socket.timeout, ConnectionRefusedError, OSError):
            status = "[CLOSED / UNREACHABLE]"
        finally:
            sock.close()

        print(f"  Port {port:5d} ({description:35s}) -> {status}")


if __name__ == "__main__":
    success = tcp_connect_test(PLC_IP, PLC_PORT, TIMEOUT_SECONDS)
    if not success:
        test_alternative_ports(PLC_IP)
