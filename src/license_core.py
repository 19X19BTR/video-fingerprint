"""
额度持久化模块
- 试用额度系统（注册表 + AppData + 隐藏文件 三层持久化，防卸载重装）
- 授权码验证调用 ed25519_license 模块
"""

import os
import sys
import json
import hashlib
from datetime import datetime

# 从 Ed25519 签名模块导入
from ed25519_license import get_machine_id, verify_license

# ─────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────

TRIAL_CREDITS = 20                               # 试用额度
REG_KEY_PATH = r"Software\XMTools\VideoFP"       # 注册表路径
APPDATA_DIR_NAME = "XMVideoFP"                   # AppData 子目录名


# ─────────────────────────────────────────────
# 额度管理器（三层持久化）
# ─────────────────────────────────────────────

class CreditManager:
    """
    额度管理器
    - 注册表存储（主）：卸载程序时通常不会清理自定义注册表项
    - AppData 文件存储（备）：双重保险
    - ProgramData 隐藏文件（第三层）：三重保险
    - 读取时取 used 最大的值，防止通过删除某处来"恢复"额度
    """

    def __init__(self):
        self.machine_id = get_machine_id()
        self._reg_available = self._check_reg_available()

    def _check_reg_available(self) -> bool:
        if sys.platform != 'win32':
            return False
        try:
            import winreg
            return True
        except ImportError:
            return False

    # ── 注册表 ──

    def _reg_read(self) -> dict | None:
        if not self._reg_available:
            return None
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_READ)
            data_str, _ = winreg.QueryValueEx(key, self.machine_id)
            winreg.CloseKey(key)
            return json.loads(data_str)
        except:
            return None

    def _reg_write(self, data: dict):
        if not self._reg_available:
            return
        try:
            import winreg
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, self.machine_id, 0, winreg.REG_SZ, json.dumps(data, ensure_ascii=False))
            winreg.CloseKey(key)
        except:
            pass

    # ── AppData ──

    def _appdata_path(self) -> str:
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        directory = os.path.join(appdata, APPDATA_DIR_NAME)
        os.makedirs(directory, exist_ok=True)
        return os.path.join(directory, f'{self.machine_id}.dat')

    def _appdata_read(self) -> dict | None:
        path = self._appdata_path()
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None

    def _appdata_write(self, data: dict):
        try:
            with open(self._appdata_path(), 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except:
            pass

    # ── 隐藏备份（ProgramData） ──

    def _hidden_path(self) -> str:
        base = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
        return os.path.join(base, '.xm_vfp_' + self.machine_id[:8])

    def _hidden_read(self) -> dict | None:
        path = self._hidden_path()
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            return None

    def _hidden_write(self, data: dict):
        try:
            path = self._hidden_path()
            with open(path, 'w') as f:
                json.dump(data, f)
            if sys.platform == 'win32':
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(path, 2)
                except:
                    pass
        except:
            pass

    # ── 核心 API ──

    def get_credits(self) -> dict:
        """
        获取当前额度状态
        返回: { credits, used, total, is_licensed, machine_id, first_seen }
        """
        sources = []
        for reader in [self._reg_read, self._appdata_read, self._hidden_read]:
            d = reader()
            if d:
                sources.append(d)

        if not sources:
            # 首次使用，初始化
            init_data = {
                'total': TRIAL_CREDITS,
                'used': 0,
                'first_seen': datetime.now().isoformat(),
                'machine_id': self.machine_id,
                'is_licensed': False,
                'license_key': '',
            }
            self._save_all(init_data)
            return self._format(init_data)

        # 取已用最多的值（最保守，防删除某处恢复额度）
        best = max(sources, key=lambda x: x.get('used', 0))
        self._save_all(best)  # 同步三处
        return self._format(best)

    def use_credit(self) -> tuple[bool, str]:
        """使用一个额度"""
        state = self.get_credits()

        if state['is_licensed']:
            return True, "已授权版本，无限制"

        if state['credits'] <= 0:
            return False, "试用额度已用完，请购买授权码"

        reg_data = self._reg_read() or self._appdata_read() or self._hidden_read()
        if not reg_data:
            return False, "额度数据异常"

        reg_data['used'] = reg_data.get('used', 0) + 1
        reg_data['last_used'] = datetime.now().isoformat()
        self._save_all(reg_data)

        remaining = reg_data['total'] - reg_data['used']
        return True, f"已使用 1 额度，剩余 {remaining}"

    def activate_license(self, license_key: str) -> tuple[bool, str]:
        """
        激活授权码（Ed25519 签名验证）
        """
        ok, info = verify_license(license_key, self.machine_id)
        if not ok:
            return False, info.get('message', '授权验证失败')

        reg_data = self._reg_read() or self._appdata_read() or {}
        reg_data['is_licensed'] = True
        reg_data['license_key'] = license_key
        reg_data['license_date'] = datetime.now().isoformat()
        reg_data['license_credits'] = info.get('credits', 0)
        reg_data['license_expire_days'] = info.get('expire_days', 0)

        self._save_all(reg_data)
        return True, "授权成功！已解锁无限制使用"

    def _save_all(self, data: dict):
        self._reg_write(data)
        self._appdata_write(data)
        self._hidden_write(data)

    def _format(self, data: dict) -> dict:
        total = data.get('total', TRIAL_CREDITS)
        used = data.get('used', 0)
        return {
            'credits': max(0, total - used),
            'used': used,
            'total': total,
            'is_licensed': data.get('is_licensed', False),
            'machine_id': self.machine_id,
            'first_seen': data.get('first_seen', ''),
        }
