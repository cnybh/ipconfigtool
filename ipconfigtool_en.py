#!/usr/bin/env python3
"""
Commissioning Engineer IP Quick Config Tool V1.0 by bohangyang 2026.07
"""

import ctypes
import os
import subprocess
import sys
import time


def is_admin():
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """Re-launch the script with admin privileges via UAC."""
    params = " ".join([f'"{arg}"' for arg in sys.argv])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


def run_cmd(cmd, capture=True, shell=True):
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except Exception as e:
        return -1, "", str(e)


def get_adapters():
    """Get list of network adapters via netsh."""
    rc, stdout, _ = run_cmd("netsh interface show interface")
    adapters = []
    if rc != 0:
        return adapters
    lines = stdout.strip().splitlines()
    # Skip header lines (first 2 lines)
    for line in lines[2:]:
        parts = line.split(None, 3)
        if len(parts) >= 4:
            name = parts[3].strip()
            if name:
                adapters.append(name)
    return adapters


def show_adapter_config(adapter):
    """Show current IPv4 configuration of the adapter."""
    rc, stdout, _ = run_cmd(f'netsh interface ipv4 show addresses "{adapter}"')
    if stdout.strip():
        print(stdout.strip())
    else:
        print("(no configuration info available)")


def set_static_ip(adapter, ip, mask):
    """Set static IP address on the adapter."""
    print("Applying static IP configuration...")
    print()

    cmd = (
        f'netsh interface ipv4 set address name="{adapter}" '
        f"source=static addr={ip} mask={mask} gateway=none"
    )
    rc, stdout, stderr = run_cmd(cmd)

    if rc == 0:
        print("Static IP configured successfully!")
    else:
        print(f"Configuration failed! (return code: {rc})")
        if stdout.strip():
            print(stdout.strip())
        if stderr.strip():
            print(stderr.strip())
        print("Please check IP format and administrator privileges.")


def set_dhcp(adapter):
    """Restore DHCP on the adapter."""
    print("Enabling DHCP auto-obtain...")
    print()

    # Step 1: Remove all manually configured (static) IPv4 addresses
    print("[1/4] Removing static IP addresses...")
    ps_cmd = (
        f"Get-NetIPAddress -InterfaceAlias '{adapter}' -AddressFamily IPv4 "
        "-ErrorAction SilentlyContinue | "
        "Where-Object {$_.PrefixOrigin -eq 'Manual'} | "
        "Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue"
    )
    run_cmd(f'powershell -NoProfile -Command "{ps_cmd}"')
    # Also try netsh delete as fallback
    run_cmd(f'netsh interface ipv4 delete address name="{adapter}" addr=all')

    # Step 2: Set interface to DHCP mode via PowerShell
    print("[2/4] Setting DHCP mode via PowerShell...")
    ps_cmd = f"Set-NetIPInterface -InterfaceAlias '{adapter}' -Dhcp Enabled"
    rc, _, _ = run_cmd(f'powershell -NoProfile -Command "{ps_cmd}"')
    if rc != 0:
        print("PowerShell method failed, falling back to netsh...")
        run_cmd(f'netsh interface ipv4 set address name="{adapter}" source=dhcp')

    # Step 3: Also run netsh as backup (mode flag)
    run_cmd(f'netsh interface ipv4 set address name="{adapter}" source=dhcp')

    # Step 4: Reset DNS servers to DHCP
    print("[3/4] Resetting DNS servers...")
    ps_cmd = (
        f"Set-DnsClientServerAddress -InterfaceAlias '{adapter}' "
        "-ResetServerAddresses -ErrorAction SilentlyContinue"
    )
    run_cmd(f'powershell -NoProfile -Command "{ps_cmd}"')
    run_cmd(f'netsh interface ipv4 set dnsservers name="{adapter}" source=dhcp')

    # Wait for DHCP service to process the mode change (~3 seconds)
    print("[4/4] Waiting for DHCP response...")
    time.sleep(0.5)

    # Release old lease and request new one
    run_cmd(f'ipconfig /release "{adapter}"')
    time.sleep(0.5)
    run_cmd(f'ipconfig /renew "{adapter}"')

    # Verification
    print()
    print("DHCP Status Verification...")
    ps_cmd = (
        f"Get-NetIPInterface -InterfaceAlias '{adapter}' -AddressFamily IPv4 "
        "| Select-Object InterfaceAlias, Dhcp, ConnectionState | Format-List"
    )
    rc, stdout, _ = run_cmd(f'powershell -NoProfile -Command "{ps_cmd}"')
    if stdout.strip():
        print(stdout.strip())
    else:
        print("(unable to retrieve DHCP status)")


def main():
    os.system("cls" if os.name == "nt" else "clear")
    ctypes.windll.kernel32.SetConsoleTitleW("Commissioning Engineer IP Quick Config Tool V1.0 by bohangyang 2026.07")
    print("=================================================")
    print("Commissioning Engineer IP Quick Config Tool V1.0")
    print("=================================================")
    print()
    # Scan network adapters
    print("Scanning for network adapters...")
    print()

    adapters = get_adapters()

    if not adapters:
        print("No network adapters detected.")
        input("Press Enter to exit...")
        sys.exit(1)

    for i, name in enumerate(adapters, 1):
        print(f"  [{i}] {name}")

    print()

    # Select adapter
    try:
        choice = int(input(f"Select adapter number (1-{len(adapters)}): "))
    except ValueError:
        print("Invalid selection.")
        input("Press Enter to exit...")
        sys.exit(1)

    if choice < 1 or choice > len(adapters):
        print("Invalid selection.")
        input("Press Enter to exit...")
        sys.exit(1)

    adapter = adapters[choice - 1]
    print()
    print("=================================================")
    print()
    print(f"Selected adapter: {adapter}")
    print()
    print("Choose an operation:")
    print("  [1] Set static IP")
    print("  [2] Restore DHCP")
    print()

    op = input("Enter option (1 or 2): ").strip()
    print()
    print("=================================================")
    print()
    if op == "1":
        ip = input("Enter target IP address (e.g. 192.168.1.100): ").strip()
        print()
        mask = input("Enter subnet mask (e.g. 255.255.255.0): ").strip()
        print()

        if not ip:
            print("Error: IP address cannot be empty.")
            input("Press Enter to exit...")
            sys.exit(1)
        if not mask:
            print("Error: Subnet mask cannot be empty.")
            input("Press Enter to exit...")
            sys.exit(1)

        set_static_ip(adapter, ip, mask)

    elif op == "2":
        set_dhcp(adapter)
    else:
        print("Invalid option.")
        input("Press Enter to exit...")
        sys.exit(1)

    print()
    print("Press Enter to exit...")
    input()


if __name__ == "__main__":
    if not is_admin():
        run_as_admin()
        sys.exit(0)
    main()
