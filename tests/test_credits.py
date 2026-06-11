"""测试额度叠加逻辑"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

# 先清数据
from video_fingerprint_gui import CreditManager, TRIAL_CREDITS
import json

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

# 1. 初始状态
s = cm.get_state()
print(f"[1] 初始: total={s['total']} used={s['used']} remaining={s['remaining']} licensed={s['licensed']}")
assert s['total'] == 20
assert s['remaining'] == 20

# 2. 使用5条
cm.use(5)
s = cm.get_state()
print(f"[2] 用5条: total={s['total']} used={s['used']} remaining={s['remaining']}")
assert s['remaining'] == 15

# 3. 激活基础版(+100)
from ed25519_license import generate_license
lic_basic = generate_license(cm.machine_id, credits=100, expire_days=0)
ok, msg = cm.activate(lic_basic)
print(f"[3] 基础版激活: {ok} - {msg}")
s = cm.get_state()
print(f"    total={s['total']} used={s['used']} remaining={s['remaining']} licensed={s['licensed']}")
assert s['total'] == 120  # 20 + 100
assert s['used'] == 5
assert s['remaining'] == 115
assert not s['licensed']  # 不是永久版

# 4. 再激活标准版(+300)
lic_std = generate_license(cm.machine_id, credits=300, expire_days=0)
ok, msg = cm.activate(lic_std)
print(f"[4] 标准版激活: {ok} - {msg}")
s = cm.get_state()
print(f"    total={s['total']} used={s['used']} remaining={s['remaining']}")
assert s['total'] == 420  # 120 + 300
assert s['remaining'] == 415

# 5. 激活永久版
lic_life = generate_license(cm.machine_id, credits=0, expire_days=0)
ok, msg = cm.activate(lic_life)
print(f"[5] 永久版激活: {ok} - {msg}")
s = cm.get_state()
print(f"    total={s['total']} used={s['used']} remaining={s['remaining']} licensed={s['licensed']}")
assert s['total'] == 999999
assert s['licensed'] == True

# 清理
appdata = cm._appdata_path()
if os.path.exists(appdata):
    os.remove(appdata)

print("\nALL TESTS PASSED")
