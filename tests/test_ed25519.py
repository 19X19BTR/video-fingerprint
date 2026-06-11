"""Ed25519 授权系统完整测试"""
import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from ed25519_license import (
    get_machine_id, generate_license, verify_license
)

mid = get_machine_id()
print(f"Machine ID: {mid}")

# 1. 生成永久无限制授权码
lic = generate_license(mid, credits=0, expire_days=0)
print(f"\n[1] 永久授权码: {lic[:40]}...")

ok, info = verify_license(lic, mid)
assert ok, f"验证失败: {info}"
assert info['credits'] == 0
assert info['expire_days'] == 0
print(f"[1] PASS: credits={info['credits']}, expire={info['expire_days']}")

# 2. 生成 100额度 30天 授权码
lic2 = generate_license(mid, credits=100, expire_days=30)
ok2, info2 = verify_license(lic2, mid)
assert ok2
assert info2['credits'] == 100
assert info2['expire_days'] == 30
print(f"[2] PASS: credits={info2['credits']}, expire={info2['expire_days']}days")

# 3. 错误机器码 → 应失败
ok3, info3 = verify_license(lic, "DEADBEEF12345678")
assert not ok3
print(f"[3] PASS: wrong machine rejected - {info3['message'][:40]}...")

# 4. 篡改授权码 → 签名验证应失败
tampered = lic[:-5] + "XXXXX"
ok4, info4 = verify_license(tampered, mid)
assert not ok4
print(f"[4] PASS: tampered key rejected - {info4['message'][:40]}...")

# 5. 随机垃圾 → 应失败
ok5, info5 = verify_license("VFP-THISISNOTAVALIDKEY", mid)
assert not ok5
print(f"[5] PASS: garbage rejected - {info5['message'][:40]}...")

# 6. 批量生成测试
print("\n[6] Batch generation test:")
for i in range(5):
    fake_mid = hashlib.sha256(os.urandom(16)).hexdigest()[:16].upper()
    fake_lic = generate_license(fake_mid, credits=50, expire_days=7)
    # 应该在自己的机器上验证通过
    ok6, _ = verify_license(fake_lic, fake_mid)
    assert ok6, f"batch #{i} failed"
    print(f"    #{i+1}: {fake_mid} -> OK")

print("\n" + "=" * 50)
print("ALL TESTS PASSED!")
print("=" * 50)
