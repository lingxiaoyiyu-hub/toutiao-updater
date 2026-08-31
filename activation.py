# -*- coding: utf-8 -*-
"""
今日头条文章采集大师 - 客户端授权与会员激活模块 (Activation & Licensing)
========================================================================
- 使用 Ed25519 非对称数字签名算法。
- 客户端仅内置公钥，可验证激活码合法性但无法逆向伪造激活码。
- 绑定硬件机器码，支持体验版限制与 VIP 会员权益判定。
"""

import os
import sys
import json
import base64
import hashlib
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

LICENSE_PREFIX = "TTS1"  # Toutiao Studio License v1
LICENSE_PRODUCT = "ToutiaoSpiderStudio"
MAX_LICENSE_LENGTH = 4096

# 客户端内置验签公钥
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAJPeP9ty8Hyw7kbpjklxjEiU1KjvQCNuN0d1NsarQN84=
-----END PUBLIC KEY-----
"""

try:
    from modules.app_config import get_app_data_dir
except ImportError:
    from app_config import get_app_data_dir

PERSISTENT_LICENSE_PATH = get_app_data_dir() / "license.dat"
LOCAL_LICENSE_PATH = Path(__file__).parent / "license.dat"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _read_windows_machine_guid() -> str:
    """从 Windows 注册表读取原生唯一 MachineGuid"""
    if os.name != "nt":
        return ""
    try:
        import winreg  # type: ignore
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return _safe_text(value)
    except Exception:
        return ""


def get_machine_uuid() -> str:
    """获取本机唯一的稳定机器标识符"""
    env_value = _safe_text(os.getenv("TOUTIAO_MACHINE_UUID"))
    if env_value:
        return env_value

    machine_guid = _read_windows_machine_guid()
    if machine_guid:
        return machine_guid

    fallback_seed = "|".join([
        _safe_text(platform.system()),
        _safe_text(platform.release()),
        _safe_text(platform.machine()),
        _safe_text(platform.node()),
        _safe_text(hex(uuid.getnode())),
    ])
    return hashlib.sha256(fallback_seed.encode("utf-8")).hexdigest()


from modules import security_guard


def get_display_machine_code(machine_uuid: Optional[str] = None) -> str:
    """获取通过 CPU+主板+BIOS+硬盘 多维物理熔炼的不可伪造机器码"""
    if machine_uuid:
        digest = hashlib.sha256(_safe_text(machine_uuid).encode("utf-8")).hexdigest().upper()
        short = digest[:12]
        return f"{short[0:4]}-{short[4:8]}-{short[8:12]}"
    return security_guard.get_deep_hardware_fingerprint()



def _b64url_decode(value: str) -> bytes:
    value = _safe_text(value)
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def verify_license(license_str: str) -> Dict[str, Any]:
    """
    验证激活码合法性并解析权益
    返回字典: {"valid": bool, "message": str, "payload": dict}
    """
    cleaned = _safe_text(license_str)
    if not cleaned:
        return {"valid": False, "message": "激活码不能为空", "payload": None}

    if len(cleaned) > MAX_LICENSE_LENGTH:
        return {"valid": False, "message": "激活码长度超出限制", "payload": None}

    parts = cleaned.split(".")
    if len(parts) != 3 or parts[0] != LICENSE_PREFIX:
        return {"valid": False, "message": "激活码格式无效 (需以 TTS1 开头)", "payload": None}

    try:
        payload_bytes = _b64url_decode(parts[1])
        signature = _b64url_decode(parts[2])
    except Exception:
        return {"valid": False, "message": "激活码编码解析失败", "payload": None}

    # 校验公钥签名
    try:
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        if not isinstance(public_key, Ed25519PublicKey):
            return {"valid": False, "message": "公钥格式错误", "payload": None}
        public_key.verify(signature, payload_bytes)
    except InvalidSignature:
        return {"valid": False, "message": "激活码签名无效或已被篡改", "payload": None}
    except Exception as e:
        return {"valid": False, "message": f"验签异常: {str(e)}", "payload": None}

    # 解析载荷
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return {"valid": False, "message": "载荷 JSON 解析失败", "payload": None}

    if not isinstance(payload, dict):
        return {"valid": False, "message": "载荷结构非法", "payload": None}

    # 验证产品名称
    if payload.get("product") != LICENSE_PRODUCT:
        return {"valid": False, "message": f"激活码非本产品专用 (目标: {payload.get('product')})", "payload": None}

    # 验证机器码
    target_machine = payload.get("machine_code", "")
    current_machine = get_display_machine_code()
    if target_machine != "*" and target_machine != current_machine:
        return {
            "valid": False,
            "message": f"该激活码已绑定机器 [{target_machine}]，当前机器为 [{current_machine}]",
            "payload": payload
        }

    # 验证到期时间 (采用双轨防篡改时钟引擎)
    expires_at_ts = payload.get("expires_at")
    if expires_at_ts is not None:
        time_valid, now_ts, err_msg = security_guard.verify_system_time_validity()
        if not time_valid:
            return {
                "valid": False,
                "message": f"授权校验失败: {err_msg}",
                "payload": payload,
                "tampered": True
            }

        if now_ts > expires_at_ts:
            exp_date = datetime.fromtimestamp(expires_at_ts).strftime('%Y-%m-%d %H:%M:%S')
            return {
                "valid": False,
                "message": f"激活码已于 {exp_date} 过期",
                "payload": payload,
                "expired": True
            }

    return {"valid": True, "message": "激活成功", "payload": payload}


def save_license(license_str: str) -> bool:
    """持久化保存激活码至 AppData 全局持久化目录，并尝试备份至本地目录"""
    saved_any = False
    cleaned_key = license_str.strip()

    # 1. 优先保存至用户 AppData 全局目录 (单文件 EXE / 重启 / 升级永久生效)
    try:
        PERSISTENT_LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PERSISTENT_LICENSE_PATH, "w", encoding="utf-8") as f:
            f.write(cleaned_key)
        saved_any = True
    except Exception as e:
        print(f"[License Save Error] AppData 写入失败: {e}")

    # 2. 尝试同步保存到本地目录 (兼容便携模式)
    try:
        with open(LOCAL_LICENSE_PATH, "w", encoding="utf-8") as f:
            f.write(cleaned_key)
        saved_any = True
    except Exception:
        pass

    # 3. 若打包运行，尝试保存至 exe 同级目录
    if getattr(sys, "frozen", False):
        try:
            exe_lic = Path(sys.executable).parent / "license.dat"
            with open(exe_lic, "w", encoding="utf-8") as f:
                f.write(cleaned_key)
        except Exception:
            pass

    return saved_any


def load_license() -> Optional[str]:
    """读取已保存的激活码 (多路径容错探测)"""
    candidate_paths = [
        PERSISTENT_LICENSE_PATH,
        LOCAL_LICENSE_PATH,
        Path.cwd() / "license.dat"
    ]
    if getattr(sys, "frozen", False):
        candidate_paths.append(Path(sys.executable).parent / "license.dat")

    for p in candidate_paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        # 若在本地找到但 AppData 缺失，自动同步到 AppData
                        if p != PERSISTENT_LICENSE_PATH and not PERSISTENT_LICENSE_PATH.exists():
                            try:
                                PERSISTENT_LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)
                                with open(PERSISTENT_LICENSE_PATH, "w", encoding="utf-8") as out_f:
                                    out_f.write(content)
                            except Exception:
                                pass
                        return content
            except Exception:
                continue
    return None


def get_license_status() -> Dict[str, Any]:
    """
    获取当前客户端的综合授权状态、功能权限与商业定价
    """
    machine_code = get_display_machine_code()

    # 商业定价方案
    pricing_plans = [
        {"id": "7d", "name": "7天体验周卡", "price": "9.9", "desc": "短期体验 · 快速上手", "tag": "尝鲜"},
        {"id": "30d", "name": "30天月度 VIP", "price": "19.9", "desc": "自媒体创作者日常首选", "tag": "推荐"},
        {"id": "lifetime", "name": "永久终身 VIP", "price": "59.9", "desc": "一次买断 · 终身免费升级", "tag": "超值买断"}
    ]

    # 二次开发环境调试模式 (设置环境变量 TOUTIAO_DEV_MODE=1 可免激活调试)
    if os.getenv("TOUTIAO_DEV_MODE") == "1" or os.getenv("TOUTIAO_BYPASS_LICENSE") == "1":
        return {
            "is_vip": True,
            "status": "active",
            "tier": "developer",
            "tier_name": "开发者尊享模式 (DEV)",
            "tier_badge": "DEV 开发版",
            "machine_code": machine_code,
            "expires_at": None,
            "expires_text": "永久有效 (二次开发调试模式)",
            "max_articles_per_crawl": 99999,
            "allow_image_download": True,
            "allow_batch_export": True,
            "allow_ai_full_article": True,
            "max_ai_words": 5000,
            "allow_advanced_remix": True,
            "max_topics": 15,
            "allow_docx_export": True,
            "plans": pricing_plans,
            "license_key": "DEV_MODE_ENABLED",
            "message": "二次开发调试模式已开启，所有高级功能无限制放开！"
        }

    saved_key = load_license()

    # 默认免费体验版权限 (严格限制以促进付费转化)
    trial_status = {
        "is_vip": False,
        "status": "trial",
        "tier_name": "免费体验版",
        "tier_badge": "体验版",
        "machine_code": machine_code,
        "expires_at": None,
        "expires_text": "免费试用中",
        "max_articles_per_crawl": 3,
        "allow_image_download": False,
        "allow_batch_export": False,
        "allow_ai_full_article": False,
        "max_ai_words": 400,
        "allow_advanced_remix": False,
        "max_topics": 3,
        "allow_docx_export": False,
        "plans": pricing_plans,
        "message": "当前处于免费体验模式 (限采集 3 篇，AI 生成限 400 字小样，禁用高清图下载与 Word 导出)。"
    }

    if not saved_key:
        return trial_status

    res = verify_license(saved_key)
    if not res["valid"]:
        trial_status["message"] = f"授权失效: {res['message']}"
        trial_status["status"] = "expired" if res.get("expired") else "invalid"
        return trial_status

    payload = res["payload"]
    tier = payload.get("tier", "vip")
    tier_name = payload.get("tier_name", "VIP 尊享会员")
    expires_at_ts = payload.get("expires_at")

    if expires_at_ts is None:
        expires_text = "永久有效 (终身尊享)"
    else:
        expires_text = datetime.fromtimestamp(expires_at_ts).strftime('%Y-%m-%d %H:%M:%S')

    return {
        "is_vip": True,
        "status": "active",
        "tier": tier,
        "tier_name": tier_name,
        "tier_badge": "VIP 会员",
        "machine_code": machine_code,
        "expires_at": expires_at_ts,
        "expires_text": expires_text,
        "max_articles_per_crawl": payload.get("max_articles", 99999),
        "allow_image_download": True,
        "allow_batch_export": True,
        "allow_ai_full_article": True,
        "max_ai_words": 5000,
        "allow_advanced_remix": True,
        "max_topics": 15,
        "allow_docx_export": True,
        "plans": pricing_plans,
        "license_key": saved_key,
        "message": f"尊贵的 {tier_name}，所有功能已全面解锁！"
    }
