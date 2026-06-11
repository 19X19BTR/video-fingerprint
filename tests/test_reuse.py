"""测试激活码防重复使用"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from video_fingerprint_gui import CreditManager, TRIAL_CREDITS
from ed25519_license import generate_license

cm = CreditManager()

# 清除
appdata = cm._appdata_path()
if os.path.exists(appdata):
    os.remove(appdata)
try:
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\XMTools\VideoFP", 0, winreg.KEY_ALL_ACCESS)
    winreg.DeleteValue(key, cm.machine_id)
    winreg.CloseKey(key)
except:
    pass

# 1. 初始
s = cm.get_state()
print("[1] Initial: remaining=%d" % s['remaining'])
assert s['remaining'] == 20

# 2. 生成基础版
lic = generate_license(cm.machine_id, credits=100, expire_days=0)

# 3. 第一次激活 - 应成功
ok1, msg1 = cm.activate(lic)
s = cm.get_state()
print("[2] First: ok=%s, msg=%s, remaining=%d" % (ok1, msg1, s['remaining']))
assert ok1
assert s['remaining'] == 120

# 4. 第二次用同一个码 - 应拒绝
ok2, msg2 = cm.activate(lic)
print("[3] Second: ok=%s, msg=%s" % (ok2, msg2))
assert not ok2
assert "已使用过" in msg2

# 5. 额度没变
s = cm.get_state()
print("[4] After reject: remaining=%d" % s['remaining'])
assert s['remaining'] == 120

# 6. 换个码，应该能用
lic2 = generate_license(cm.machine_id, credits=300, expire_days=0)
ok3, msg3 = cm.activate(lic2)
s = cm.get_state()
print("[5] Different key: ok=%s, remaining=%d" % (ok3, s['remaining']))
assert ok3
assert s['remaining'] == 420

# 清理
os.remove(cm._appdata_path())
print("\nALL TESTS PASSED")
