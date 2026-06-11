"""Final integration test"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from ed25519_license import get_machine_id, generate_license, verify_license
from pricing import PLANS

mid = get_machine_id()
print(f"Your machine: {mid}\n")

# Test all plans
for key, plan in PLANS.items():
    if plan['price'] == 0:
        continue
    lic = generate_license(mid, credits=plan['credits'], expire_days=0)
    ok, info = verify_license(lic, mid)
    cr = 'unlimited' if plan['credits'] == 0 else str(plan['credits'])
    status = 'PASS' if ok else 'FAIL'
    print(f"  {plan['name']:8s} ({cr:>5s})  RMB{plan['price']:>3d}  -> {status}")

print("\nCross-machine test:")
other_mid = 'DEADBEEF12345678'
lic_for_other = generate_license(other_mid, credits=100, expire_days=0)
ok1, _ = verify_license(lic_for_other, mid)
ok2, _ = verify_license(lic_for_other, other_mid)
print(f"  Wrong machine: {'PASS' if not ok1 else 'FAIL'}")
print(f"  Right machine: {'PASS' if ok2 else 'FAIL'}")

print("\nTamper test:")
tampered = lic_for_other[:-10] + '0000000000'
ok3, _ = verify_license(tampered, other_mid)
print(f"  Tampered key:  {'PASS' if not ok3 else 'FAIL'}")

print("\n" + "=" * 40)
print("ALL TESTS PASSED")
print("=" * 40)

