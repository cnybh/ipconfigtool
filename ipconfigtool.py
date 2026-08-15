#!/usr/bin/env python3
"""
Commissioning Engineer IP Quick Config Tool V1.0（CHN VERSION） by bohangyang 2026.07
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


def get_console_encoding():
    """Get the encoding used by Windows console commands (netsh/powershell)."""
    try:
        cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        if cp:
            return f"cp{cp}"
    except Exception:
        pass
    return "gbk"


def run_cmd(cmd, capture=True, shell=True):
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=capture,
            text=True,
            encoding=get_console_encoding(),
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
        print("（无可用配置信息）")


def set_static_ip(adapter, ip, mask):
    """Set static IP address on the adapter."""
    print("正在应用静态 IP 配置...")
    print()

    cmd = (
        f'netsh interface ipv4 set address name="{adapter}" '
        f"source=static addr={ip} mask={mask} gateway=none"
    )
    rc, stdout, stderr = run_cmd(cmd)

    if rc == 0:
        print("静态 IP 配置成功！")
    else:
        print(f"配置失败！（返回码：{rc}）")
        if stdout.strip():
            print(stdout.strip())
        if stderr.strip():
            print(stderr.strip())
        print("请检查 IP 格式及管理员权限。")


def set_dhcp(adapter):
    """Restore DHCP on the adapter."""
    print("正在启用 DHCP 自动获取...")
    print()

    # Step 1: Remove all manually configured (static) IPv4 addresses
    print("[1/4] 正在移除静态 IP 地址...")
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
    print("[2/4] 正在通过 PowerShell 设置 DHCP 模式...")
    ps_cmd = f"Set-NetIPInterface -InterfaceAlias '{adapter}' -Dhcp Enabled"
    rc, _, _ = run_cmd(f'powershell -NoProfile -Command "{ps_cmd}"')
    if rc != 0:
        print("PowerShell 方式失败，回退到 netsh...")
        run_cmd(f'netsh interface ipv4 set address name="{adapter}" source=dhcp')

    # Step 3: Also run netsh as backup (mode flag)
    run_cmd(f'netsh interface ipv4 set address name="{adapter}" source=dhcp')

    # Step 4: Reset DNS servers to DHCP
    print("[3/4] 正在重置 DNS 服务器...")
    ps_cmd = (
        f"Set-DnsClientServerAddress -InterfaceAlias '{adapter}' "
        "-ResetServerAddresses -ErrorAction SilentlyContinue"
    )
    run_cmd(f'powershell -NoProfile -Command "{ps_cmd}"')
    run_cmd(f'netsh interface ipv4 set dnsservers name="{adapter}" source=dhcp')

    # Wait for DHCP service to process the mode change (~3 seconds)
    print("[4/4] 正在等待 DHCP 响应...")
    time.sleep(0.5)

    # Release old lease and request new one
    run_cmd(f'ipconfig /release "{adapter}"')
    time.sleep(0.5)
    run_cmd(f'ipconfig /renew "{adapter}"')

    # Verification
    print()
    print("DHCP 状态验证...")
    ps_cmd = (
        f"Get-NetIPInterface -InterfaceAlias '{adapter}' -AddressFamily IPv4 "
        "| Select-Object InterfaceAlias, Dhcp, ConnectionState | Format-List"
    )
    rc, stdout, _ = run_cmd(f'powershell -NoProfile -Command "{ps_cmd}"')
    if stdout.strip():
        print(stdout.strip())
    else:
        print("（无法获取 DHCP 状态）")


def main():
    os.system("cls" if os.name == "nt" else "clear")
    ctypes.windll.kernel32.SetConsoleTitleW("调试工程师 IP 快速配置工具 V1.0  by bohangyang 2026.07")
    print("=================================================")
    print("        调试工程师 IP 快速配置工具 V1.0")
    print("=================================================")
    print()
    # Scan network adapters
    print("正在扫描网络适配器...")
    print()

    adapters = get_adapters()

    if not adapters:
        print("未检测到网络适配器。")
        input("按回车键退出...")
        sys.exit(1)

    for i, name in enumerate(adapters, 1):
        print(f"  [{i}] {name}")

    print()

    # Select adapter
    try:
        choice = int(input(f"请选择网络适配器编号 (1-{len(adapters)})："))
    except ValueError:
        print("选择无效。")
        input("按回车键退出...")
        sys.exit(1)

    if choice < 1 or choice > len(adapters):
        print("选择无效。")
        input("按回车键退出...")
        sys.exit(1)

    adapter = adapters[choice - 1]
    print()
    print("=================================================")
    print()
    print(f"已选择网络适配器：{adapter}")
    print()
    print("请选择操作：")
    print("  [1] 设置静态 IP")
    print("  [2] 恢复 DHCP")
    print()

    op = input("请输入选项 (1 或 2)：").strip()
    print()
    print("=================================================")
    print()
    if op == "1":
        ip = input("请输入目标 IP 地址 (例如 192.168.1.100)：").strip()
        print()
        mask = input("请输入子网掩码 (例如 255.255.255.0)：").strip()
        print()

        if not ip:
            print("错误：IP 地址不能为空。")
            input("按回车键退出...")
            sys.exit(1)
        if not mask:
            print("错误：子网掩码不能为空。")
            input("按回车键退出...")
            sys.exit(1)

        set_static_ip(adapter, ip, mask)

    elif op == "2":
        set_dhcp(adapter)
    else:
        print("选项无效。")
        input("按回车键退出...")
        sys.exit(1)

    print()
    print("按回车键退出...")
    input()


if __name__ == "__main__":
    if not is_admin():
        run_as_admin()
        sys.exit(0)
    main()
