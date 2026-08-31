# -*- coding: utf-8 -*-
"""
今日头条文章采集大师 - 开发者专用激活码签发工具 (License Issuer)
===================================================================
仅供开发者/管理员在安全环境下使用，包含 Ed25519 私钥签名。
支持绑定指定机器码、设置授权天数或永久终身 VIP。
"""

import os
import sys
import json
import base64
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

LICENSE_PREFIX = "TTS1"
LICENSE_PRODUCT = "ToutiaoSpiderStudio"

PRIVATE_KEY_PATH = Path(__file__).parent / "license_private_key.pem"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def load_private_key() -> Ed25519PrivateKey:
    if not PRIVATE_KEY_PATH.exists():
        raise FileNotFoundError(f"未找到私钥文件: {PRIVATE_KEY_PATH}")
    with open(PRIVATE_KEY_PATH, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("私钥类型不是 Ed25519PrivateKey")
    return key


def format_machine_code(raw: str) -> str:
    """清理并格式化机器码为 XXXX-XXXX-XXXX 或 *"""
    raw = raw.strip().upper().replace(" ", "").replace("-", "")
    if raw == "*" or raw == "ALL":
        return "*"
    if len(raw) == 12:
        return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"
    return raw


def issue_license(
    machine_code: str,
    days: Optional[int] = None,
    tier: str = "vip",
    tier_name: str = "VIP 尊享会员",
    max_articles: int = 99999,
    remarks: str = ""
) -> str:
    """
    签发激活码
    days: None 表示永久终身有效，正整数表示有效天数
    """
    private_key = load_private_key()
    now = datetime.now(timezone.utc)
    issued_at_ts = int(now.timestamp())

    expires_at_ts = None
    if days is not None and days > 0:
        expires_at_dt = now + timedelta(days=days)
        expires_at_ts = int(expires_at_dt.timestamp())

    payload = {
        "product": LICENSE_PRODUCT,
        "machine_code": format_machine_code(machine_code),
        "tier": tier,
        "tier_name": tier_name,
        "max_articles": max_articles,
        "issued_at": issued_at_ts,
        "expires_at": expires_at_ts,
        "remarks": remarks
    }

    payload_bytes = _canonical_payload_bytes(payload)
    signature = private_key.sign(payload_bytes)

    license_str = f"{LICENSE_PREFIX}.{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"
    return license_str


def interactive_mode():
    print("=" * 60)
    print("      今日头条文章采集大师 - 激活码一键签发工具")
    print("=" * 60)

    # 1. 输入机器码
    while True:
        raw_mc = input("\n[1] 请输入客户机器码 (如 A1B2-C3D4-E5F6，输入 * 为通用无绑定码): ").strip()
        if raw_mc:
            machine_code = format_machine_code(raw_mc)
            break
        print("错误: 机器码不能为空！")

    # 2. 选择授权时长档位
    print("\n[2] 请选择授权会员档位 (闲鱼定价标准):")
    print("    1. [7天体验周卡 (¥9.9)]   - 适合短期低门槛尝鲜试用")
    print("    2. [30天月度 VIP (¥19.9)]  - 自媒体创作者按月订阅首选")
    print("    3. [永久终身 VIP (¥59.9)]  - 终身买断尊享会员 (无时间限制 · 推荐)")
    print("    4. [自定义天数]            - 输入任意有效天数")

    choice = input("请输入选项编号 (默认 3): ").strip() or "3"

    days = None
    tier_name = "永久终身 VIP"
    if choice == "1":
        days = 7
        tier_name = "7天体验 VIP"
    elif choice == "2":
        days = 30
        tier_name = "月度尊享 VIP"
    elif choice == "3":
        days = None
        tier_name = "永久终身 VIP"
    elif choice == "4":
        while True:
            try:
                days_input = input("请输入自定义天数: ").strip()
                days = int(days_input)
                tier_name = f"{days}天定制 VIP"
                break
            except ValueError:
                print("请输入有效正整数！")

    remarks = input("\n[3] 备注信息 (可选，如买家昵称/订单号): ").strip()

    # 签发激活码
    try:
        license_key = issue_license(
            machine_code=machine_code,
            days=days,
            tier_name=tier_name,
            remarks=remarks
        )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        exp_str = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S") if days else "永久有效"

        print("\n" + "=" * 60)
        print(" [√] 激活码签发成功！")
        print("=" * 60)
        print(f" 目标机器: {machine_code}")
        print(f" 授权类型: {tier_name}")
        print(f" 到期时间: {exp_str}")
        print(f" 签发时间: {now_str}")
        print(f" 备    注: {remarks or '无'}")
        print("-" * 60)
        print("【激活码密文】(请完整复制发送给客户):")
        print(f"\n{license_key}\n")
        print("-" * 60)

        # 保存签发记录到日志文件
        log_file = Path(__file__).parent / "issued_licenses.txt"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{now_str}] 机器: {machine_code} | 类型: {tier_name} | 到期: {exp_str} | 备注: {remarks}\n")
            f.write(f"激活码: {license_key}\n\n")

        print(f"签发记录已追加保存至: {log_file.resolve()}")

    except Exception as e:
        print(f"\n[×] 签发失败: {str(e)}")

    print("\n按 Enter 键退出...")
    input()


def main():
    if len(sys.argv) == 1:
        interactive_mode()
        return

    parser = argparse.ArgumentParser(description="今日头条采集大师 - 激活码签发工具")
    parser.add_argument("--machine", "-m", type=str, required=True, help="目标机器码 (例如: A1B2-C3D4-E5F6 或 * )")
    parser.add_argument("--days", "-d", type=int, default=None, help="授权天数 (默认: 永久有效)")
    parser.add_argument("--tier-name", "-t", type=str, default="VIP 尊享会员", help="会员等级名称")
    parser.add_argument("--remarks", "-r", type=str, default="", help="订单或用户备注")

    args = parser.parse_args()
    key = issue_license(
        machine_code=args.machine,
        days=args.days,
        tier_name=args.tier_name,
        remarks=args.remarks
    )
    print(key)


if __name__ == "__main__":
    main()
