"""检查持久化存储"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from license_core import get_machine_id
import winreg

mid = get_machine_id()
print(f"Machine ID: {mid}")

# 1. Registry
try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\XMTools\VideoFP", 0, winreg.KEY_READ)
    val, _ = winreg.QueryValueEx(key, mid)
    winreg.CloseKey(key)
    data = json.loads(val)
    print(f"\n[REGISTRY]")
    print(f"  licensed: {data.get('is_licensed')}")
    print(f"  total:    {data.get('total')}")
    print(f"  used:     {data.get('used')}")
except FileNotFoundError:
    print("\n[REGISTRY] Not found")

# 2. AppData
appdata = os.environ.get("APPDATA", "")
path = os.path.join(appdata, "XMVideoFP", f"{mid}.dat")
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
    print(f"\n[APPDATA] {path}")
    print(f"  licensed: {data.get('is_licensed')}")
    print(f"  total:    {data.get('total')}")
    print(f"  used:     {data.get('used')}")
else:
    print(f"\n[APPDATA] Not found")

# 3. Hidden backup
progdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
hidden = os.path.join(progdata, f".xm_vfp_{mid[:8]}")
if os.path.exists(hidden):
    with open(hidden) as f:
        data = json.load(f)
    print(f"\n[HIDDEN] {hidden}")
    print(f"  licensed: {data.get('is_licensed')}")
    print(f"  total:    {data.get('total')}")
    print(f"  used:     {data.get('used')}")
else:
    print(f"\n[HIDDEN] Not found")

