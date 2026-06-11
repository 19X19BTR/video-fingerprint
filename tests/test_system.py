"""完整系统测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from license_core import (
    get_machine_id, generate_license, verify_license, verify_license_format,
    CreditManager, TRIAL_CREDITS
)

print("=" * 60)
print("  视频指纹工具 V2.0 - 系统测试")
print("=" * 60)

# 1. 机器码
mid = get_machine_id()
print(f"\n[1] 机器码: {mid}")

# 2. 授权码生成
lic = generate_license(mid)
print(f"[2] 授权码: {lic}")

# 3. 格式验证
assert verify_license_format(lic), "格式验证失败"
assert not verify_license_format("BAD-FORMAT"), "格式验证应拒绝无效格式"
print("[3] 格式验证: PASS")

# 4. 授权码验证
ok, msg = verify_license(lic, mid)
assert ok, f"授权验证失败: {msg}"
print(f"[4] 授权验证: PASS - {msg}")

# 错误的授权码应拒绝
ok2, msg2 = verify_license("XM-0000-0000-0000-0000-0000", mid)
assert not ok2, "错误授权码不应通过"
print(f"[5] 错误码拒绝: PASS - {msg2}")

# 5. 额度系统
print("\n--- 额度系统测试 ---")
cm = CreditManager()
state = cm.get_credits()
print(f"  总额度:   {state['total']}")
print(f"  已使用:   {state['used']}")
print(f"  剩余额度: {state['credits']}")
print(f"  已授权:   {state['is_licensed']}")
print(f"  首次使用: {state['first_seen']}")

# 使用一个额度
ok, msg = cm.use_credit()
print(f"  使用额度: {ok} - {msg}")

# 再读取确认
state2 = cm.get_credits()
print(f"  使用后剩余: {state2['credits']}")
assert state2['credits'] == state['credits'] - 1, "额度扣减不正确！"
print("[6] 额度扣减: PASS")

# 6. 激活授权
print("\n--- 授权激活测试 ---")
ok, msg = cm.activate_license(lic)
print(f"  激活结果: {ok} - {msg}")
assert ok, "激活失败"

state3 = cm.get_credits()
print(f"  激活后 - 已授权: {state3['is_licensed']}")
assert state3['is_licensed'], "激活后应为已授权状态"
print("[7] 授权激活: PASS")

# 激活后使用额度应无限制
ok, msg = cm.use_credit()
print(f"  授权后使用额度: {ok} - {msg}")
assert ok, "授权后应能无限制使用"
print("[8] 授权后无限制: PASS")

# 7. 错误授权码激活
ok_err, msg_err = cm.activate_license("XM-0000-0000-0000-0000-0000")
assert not ok_err, "错误码不应激活成功"
print(f"[9] 错误码激活拒绝: PASS - {msg_err}")

print("\n" + "=" * 60)
print("  ALL TESTS PASSED!")
print("=" * 60)

