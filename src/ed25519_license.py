"""
Ed25519 签名授权系统
- 开发者持有【私钥】→ 生成授权码
- 软件内置【公钥】→ 验证授权码
- 即使公钥泄露也无法伪造授权码（数学保证）
"""

import os
import sys
import json
import hashlib
import struct
import base64
import time
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey
)
from cryptography.hazmat.primitives import serialization


# ═══════════════════════════════════════════════════════════════
# 密钥管理
# ═══════════════════════════════════════════════════════════════

# 密钥文件位置：开发时在 config/，打包后在 exe 同目录
if getattr(sys, 'frozen', False):
    # 打包后：exe 同目录
    KEYS_FILE = os.path.join(os.path.dirname(sys.executable), '.keys')
else:
    # 开发时：项目 config/ 目录
    KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', '.keys')

# ── 打包时替换此处（客户端用）──
# 运行 `python ed25519_license.py init` 后，把公钥 hex 填在这里
EMBEDDED_PUBLIC_KEY_HEX = ""


def _get_or_create_keypair() -> tuple[Ed25519PrivateKey, bytes]:
    """获取或生成密钥对"""
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, 'r') as f:
            data = json.load(f)
        sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(data['private']))
        return sk, bytes.fromhex(data['public'])

    # 首次生成
    sk = Ed25519PrivateKey.generate()
    pk_bytes = sk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    sk_bytes = sk.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )

    os.makedirs(os.path.dirname(KEYS_FILE) or '.', exist_ok=True)
    with open(KEYS_FILE, 'w') as f:
        json.dump({'private': sk_bytes.hex(), 'public': pk_bytes.hex()}, f)
    print(f"[init] 密钥对已生成: {KEYS_FILE}")

    return sk, pk_bytes


def load_public_key() -> Ed25519PublicKey | None:
    """加载公钥（客户端用）"""
    # 方法1：内置公钥（打包后用这个）
    if EMBEDDED_PUBLIC_KEY_HEX:
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(EMBEDDED_PUBLIC_KEY_HEX))

    # 方法2：从本地密钥文件读取
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, 'r') as f:
            data = json.load(f)
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(data['public']))

    return None


# ═══════════════════════════════════════════════════════════════
# 机器码
# ═══════════════════════════════════════════════════════════════

def get_machine_id() -> str:
    """硬件指纹：主板序列号 + CPU ID + 磁盘序列号 + 主机名"""
    import platform
    parts = [platform.node(), platform.processor()]

    if sys.platform == 'win32':
        import subprocess
        for cmd in [
            ['wmic', 'baseboard', 'get', 'SerialNumber'],
            ['wmic', 'cpu', 'get', 'ProcessorId'],
            ['wmic', 'diskdrive', 'get', 'SerialNumber'],
        ]:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                for line in r.stdout.strip().split('\n'):
                    s = line.strip()
                    if s and not s[0].isalpha():
                        parts.append(s)
                        break
            except:
                pass

    raw = '|'.join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


# ═══════════════════════════════════════════════════════════════
# 授权码格式
# ═══════════════════════════════════════════════════════════════
#
#   Base64URL 编码的字节流：
#
#   ┌─────────┬───────────┬─────────┬─────────────┬──────────────┬───────────┐
#   │ version │ timestamp │ credits │ expire_days │  machine_id  │ signature │
#   │  1 byte │  4 bytes  │ 4 bytes │   4 bytes   │   16 bytes   │  64 bytes │
#   └─────────┴───────────┴─────────┴─────────────┴──────────────┴───────────┘
#   签名范围: version + timestamp + credits + expire_days + machine_id (前29字节)
#
#   Base64 后约 124 字符，以 "VFP-" 为前缀
#

def generate_license(machine_id: str, private_key: Ed25519PrivateKey = None,
                     credits: int = 100, expire_days: int = 0) -> str:
    """
    生成授权码（开发者端 - 用私钥签名）

    参数:
        machine_id:   目标机器码 (16位hex)
        private_key:  Ed25519 私钥
        credits:      授权额度（0=无限制）
        expire_days:  有效天数（0=永久）
    """
    if private_key is None:
        private_key, _ = _get_or_create_keypair()

    mid_bytes = bytes.fromhex(machine_id.upper())
    assert len(mid_bytes) == 8, f"machine_id must be 8 bytes (16 hex chars), got {len(mid_bytes)}"
    ts = int(time.time())

    # 构造 payload: version(1) + timestamp(4) + credits(4) + expire_days(4) + machine_id(8) = 21 bytes
    payload = struct.pack('>B', 0x01)           # version: 1
    payload += struct.pack('>I', ts)             # timestamp
    payload += struct.pack('>I', credits)        # credits
    payload += struct.pack('>I', expire_days)    # expire_days
    payload += mid_bytes                         # machine_id (8 bytes)

    # Ed25519 签名
    sig = private_key.sign(payload)

    # payload + signature = 授权码字节 (21 + 64 = 85 bytes)
    license_bytes = payload + sig

    # Base64URL 编码
    return "VFP-" + base64.urlsafe_b64encode(license_bytes).decode().rstrip('=')


def verify_license(license_key: str, current_machine_id: str,
                   public_key: Ed25519PublicKey = None) -> tuple[bool, dict]:
    """
    验证授权码（客户端 - 用公钥验证）

    返回: (是否合法, { credits, expire_days, timestamp, machine_id, message })
    """
    if public_key is None:
        public_key = load_public_key()

    if public_key is None:
        return False, {'message': '公钥未配置，无法验证授权码'}

    # 1. 去前缀 + Base64 解码
    key = license_key.strip()
    if key.startswith('VFP-'):
        key = key[4:]

    # 补齐 padding
    pad = 4 - len(key) % 4
    if pad != 4:
        key += '=' * pad

    try:
        data = base64.urlsafe_b64decode(key)
    except Exception:
        return False, {'message': '授权码格式错误（Base64解码失败）'}

    # 2. 拆分 payload + signature
    if len(data) < 85:
        return False, {'message': '授权码数据不完整'}

    payload = data[:21]
    sig = data[21:85]

    # 3. 解析 payload
    try:
        version = struct.unpack('>B', payload[0:1])[0]
        if version != 1:
            return False, {'message': f'不支持的授权码版本: {version}'}

        ts = struct.unpack('>I', payload[1:5])[0]
        credits = struct.unpack('>I', payload[5:9])[0]
        expire_days = struct.unpack('>I', payload[9:13])[0]
        mid_bytes = payload[13:21]
        machine_id = mid_bytes.hex().upper()
    except Exception as e:
        return False, {'message': f'授权码解析失败: {e}'}

    # 4. ★ 核心：Ed25519 签名验证 ★
    try:
        public_key.verify(sig, payload)
    except Exception:
        return False, {'message': '授权码签名验证失败（可能被篡改或伪造）'}

    # 5. 验证机器码
    if machine_id != current_machine_id.upper():
        return False, {
            'message': f'授权码不适用于当前机器\n'
                       f'授权目标: {machine_id}\n'
                       f'当前机器: {current_machine_id}'
        }

    # 6. 验证过期时间
    if expire_days > 0:
        expire_ts = ts + expire_days * 86400
        if time.time() > expire_ts:
            return False, {'message': '授权码已过期'}

    return True, {
        'message': '授权验证通过',
        'credits': credits,
        'expire_days': expire_days,
        'timestamp': datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M'),
        'machine_id': machine_id,
    }


# ═══════════════════════════════════════════════════════════════
# CLI 工具
# ═══════════════════════════════════════════════════════════════

def cli_main():
    import argparse
    from pricing import PLANS

    parser = argparse.ArgumentParser(description='视频指纹工具 - Ed25519 签名授权系统')
    sub = parser.add_subparsers(dest='cmd')

    sub.add_parser('init', help='首次运行：生成密钥对')
    sub.add_parser('machine-id', help='显示当前机器码')
    sub.add_parser('pubkey', help='显示公钥（填入客户端代码）')
    sub.add_parser('plans', help='显示套餐列表')

    p_gen = sub.add_parser('gen', help='生成授权码')
    p_gen.add_argument('mid', help='目标机器码 (16位hex)')
    p_gen.add_argument('--plan', help='套餐名: basic/standard/pro/lifetime')
    p_gen.add_argument('--credits', type=int, default=100, help='额度（0=无限制，默认100）')
    p_gen.add_argument('--days', type=int, default=0, help='有效天数（0=永久）')

    p_verify = sub.add_parser('verify', help='验证授权码')
    p_verify.add_argument('key', help='授权码')

    p_batch = sub.add_parser('batch', help='批量生成授权码')
    p_batch.add_argument('count', type=int, help='数量')
    p_batch.add_argument('--plan', help='套餐名')
    p_batch.add_argument('--credits', type=int, default=100)
    p_batch.add_argument('--days', type=int, default=0)

    args = parser.parse_args()

    if args.cmd == 'init':
        sk, pk = _get_or_create_keypair()
        sk_bytes = sk.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
        )
        print(f"密钥对已生成!")
        print(f"私钥 (hex): {sk_bytes.hex()}")
        print(f"公钥 (hex): {pk.hex()}")
        print()
        print("重要：请将以下公钥填入 ed25519_license.py 的 EMBEDDED_PUBLIC_KEY_HEX:")
        print(f'EMBEDDED_PUBLIC_KEY_HEX = "{pk.hex()}"')

    elif args.cmd == 'machine-id':
        print(f"当前机器码: {get_machine_id()}")

    elif args.cmd == 'pubkey':
        if os.path.exists(KEYS_FILE):
            with open(KEYS_FILE) as f:
                data = json.load(f)
            print(f"公钥 (hex): {data['public']}")
            print()
            print(f'EMBEDDED_PUBLIC_KEY_HEX = "{data["public"]}"')
        else:
            print("密钥对未初始化，请先运行: python ed25519_license.py init")

    elif args.cmd == 'plans':
        print("\n可用套餐:")
        print("-" * 60)
        for key, p in PLANS.items():
            if p['price'] == 0:
                continue
            credits_txt = '不限量' if p['credits'] == 0 else f"{p['credits']}条"
            unit = f"  (RMB {p['price']/p['credits']:.2f}/条)" if p['credits'] > 0 else ''
            tag = ''
            if key == 'standard':
                tag = '  [热销]'
            elif key == 'pro':
                tag = '  [超值]'
            elif key == 'lifetime':
                tag = '  [永久]'
            print(f"  {key:10s}  {p['name']}{tag}  {credits_txt}  RMB {p['price']}{unit}")
        print()
        print("用法: python ed25519_license.py gen <机器码> --plan standard")

    elif args.cmd == 'gen':
        mid = args.mid.upper().strip()
        if len(mid) != 16:
            print(f"错误：机器码应为 16 位 hex，当前 {len(mid)} 位")
            return
        try:
            bytes.fromhex(mid)
        except ValueError:
            print("错误：机器码包含非十六进制字符")
            return

        credits = args.credits
        days = args.days
        plan_name = ''
        if hasattr(args, 'plan') and args.plan:
            p = PLANS.get(args.plan)
            if not p:
                print(f"错误：未知套餐 '{args.plan}'，可用: {', '.join(PLANS.keys())}")
                return
            credits = p['credits']
            plan_name = p['name']

        lic = generate_license(mid, credits=credits, expire_days=days)
        days_txt = '永久' if days == 0 else str(days) + '天'
        cr_txt = '无限制' if credits == 0 else str(credits)
        print(f"机器码:   {mid}")
        if plan_name:
            print(f"套餐:     {plan_name}")
        print(f"额度:     {cr_txt}")
        print(f"有效期:   {days_txt}")
        print(f"授权码:   {lic}")

    elif args.cmd == 'verify':
        mid = get_machine_id()
        ok, info = verify_license(args.key, mid)
        print(f"机器码:   {mid}")
        print(f"结果:     {'通过' if ok else '失败'}")
        print(f"消息:     {info['message']}")
        if ok:
            cr_txt = '无限制' if info['credits'] == 0 else str(info['credits'])
            exp = info['expire_days']
            print(f"额度:     {cr_txt}")
            print(f"有效期:   {'永久' if exp == 0 else str(exp) + '天'}")
            print(f"生成时间: {info['timestamp']}")

    elif args.cmd == 'batch':
        credits = args.credits
        days = args.days
        plan_name = ''
        if hasattr(args, 'plan') and args.plan:
            p = PLANS.get(args.plan)
            if not p:
                print(f"错误：未知套餐 '{args.plan}'")
                return
            credits = p['credits']
            plan_name = p['name']
        days_txt = '永久' if days == 0 else str(days) + '天'
        cr_txt = '无限制' if credits == 0 else str(credits)
        label = f"{plan_name} " if plan_name else ''
        print(f"批量生成 {args.count} 个授权码 ({label}额度={cr_txt}, 有效期={days_txt}):")
        print("-" * 85)
        for i in range(args.count):
            fake_mid = hashlib.sha256(os.urandom(16)).hexdigest()[:16].upper()
            lic = generate_license(fake_mid, credits=credits, expire_days=days)
            print(f"{i+1:3d}. {fake_mid}  {lic}")

    else:
        parser.print_help()


if __name__ == '__main__':
    cli_main()
