"""
视频指纹批量修改工具
极简三步：选视频 → 选份数 → 开始生成
- 命名：原文件名_8位随机hex.mp4
- 输出：源视频同目录
- 单实例锁定
"""

import os
import sys
import struct
import shutil
import uuid
import hashlib
import json
import time
import threading
import ctypes
import ctypes.wintypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinterdnd2

from datetime import datetime
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
import base64

# ═══════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════

TRIAL_CREDITS = 20
REG_KEY_PATH = r"Software\XMTools\VideoFP"
APPDATA_DIR_NAME = "XMVideoFP"
MUTEX_NAME = "Global\\XM_VideoFP_V2_SingleInstance"

KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', '.keys')
EMBEDDED_PUBLIC_KEY_HEX = "1a2ce4a41e1197be7bdc7bee1c94a08a9aa1563f6d79728e881c9edb6f61b2b8"


# ═══════════════════════════════════════════════
# 单实例锁
# ═══════════════════════════════════════════════

def try_lock():
    """尝试获取全局互斥锁，返回 (成功, handle)"""
    if sys.platform != 'win32':
        return True, None
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return False, handle
        return True, handle
    except:
        return True, None


# ═══════════════════════════════════════════════
# Ed25519 签名验证
# ═══════════════════════════════════════════════

def _load_public_key():
    if EMBEDDED_PUBLIC_KEY_HEX:
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(EMBEDDED_PUBLIC_KEY_HEX))
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, 'r') as f:
            data = json.load(f)
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(data['public']))
    return None


def get_machine_id():
    import platform
    parts = [platform.node(), platform.processor()]
    if sys.platform == 'win32':
        import subprocess
        for cmd in [['wmic', 'baseboard', 'get', 'SerialNumber'],
                     ['wmic', 'cpu', 'get', 'ProcessorId']]:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                for line in r.stdout.strip().split('\n'):
                    s = line.strip()
                    if s and not s[0].isalpha():
                        parts.append(s)
                        break
            except:
                pass
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:16].upper()


def verify_license(license_key, current_machine_id):
    pk = _load_public_key()
    if not pk:
        return False, "公钥未配置"
    key = license_key.strip()
    if key.startswith('VFP-'):
        key = key[4:]
    key += '=' * (4 - len(key) % 4) if len(key) % 4 else ''
    try:
        data = base64.urlsafe_b64decode(key)
    except:
        return False, "激活码格式错误"
    if len(data) < 85:
        return False, "激活码数据不完整"
    payload, sig = data[:21], data[21:85]
    try:
        pk.verify(sig, payload)
    except:
        return False, "激活码签名验证失败"
    try:
        mid = payload[13:21].hex().upper()
        credits = struct.unpack('>I', payload[5:9])[0]
    except:
        return False, "激活码解析失败"
    if mid != current_machine_id.upper():
        return False, "激活码不适用于本机"
    return True, {"credits": credits}


# ═══════════════════════════════════════════════
# 额度管理
# ═══════════════════════════════════════════════

class CreditManager:
    def __init__(self):
        self.machine_id = get_machine_id()

    def _read(self):
        for reader in [self._reg_read, self._appdata_read]:
            d = reader()
            if d:
                return d
        return None

    def _reg_read(self):
        if sys.platform != 'win32':
            return None
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, self.machine_id)
            winreg.CloseKey(key)
            return json.loads(val)
        except:
            return None

    def _reg_write(self, data):
        if sys.platform != 'win32':
            return
        try:
            import winreg
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, self.machine_id, 0, winreg.REG_SZ, json.dumps(data, ensure_ascii=False))
            winreg.CloseKey(key)
        except:
            pass

    def _appdata_path(self):
        d = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), APPDATA_DIR_NAME)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f'{self.machine_id}.dat')

    def _appdata_read(self):
        p = self._appdata_path()
        if not os.path.exists(p):
            return None
        try:
            with open(p) as f:
                return json.load(f)
        except:
            return None

    def _appdata_write(self, data):
        try:
            with open(self._appdata_path(), 'w') as f:
                json.dump(data, f, ensure_ascii=False)
        except:
            pass

    def _save(self, data):
        self._reg_write(data)
        self._appdata_write(data)

    def get_state(self):
        d = self._read()
        if not d:
            d = {'total': TRIAL_CREDITS, 'used': 0, 'licensed': False}
            self._save(d)
        return {
            'remaining': max(0, d.get('total', TRIAL_CREDITS) - d.get('used', 0)),
            'total': d.get('total', TRIAL_CREDITS),
            'used': d.get('used', 0),
            'licensed': d.get('licensed', False),
        }

    def use(self, n=1):
        d = self._read() or {'total': TRIAL_CREDITS, 'used': 0, 'licensed': False}
        if d.get('licensed'):
            return True, ""
        d['used'] = d.get('used', 0) + n
        self._save(d)
        remaining = max(0, d['total'] - d['used'])
        return True, f"剩余额度: {remaining}"

    def activate(self, key):
        key = key.strip()
        ok, info = verify_license(key, self.machine_id)
        if not ok:
            return False, info
        d = self._read() or {'total': TRIAL_CREDITS, 'used': 0, 'used_keys': []}
        # 检查是否已使用过
        used_keys = d.get('used_keys', [])
        if key in used_keys:
            return False, "该激活码已使用过，不能重复使用"
        # 叠加额度
        add_credits = info.get('credits', 0)  # 0 = 永久不限量
        if add_credits == 0:
            d['total'] = 999999
            d['licensed'] = True
        else:
            d['total'] = d.get('total', 0) + add_credits
        # 记录已使用的激活码
        used_keys.append(key)
        d['used_keys'] = used_keys
        d['license_date'] = datetime.now().isoformat()
        self._save(d)
        if add_credits == 0:
            return True, "永久版激活成功，不限量使用"
        new_remaining = max(0, d['total'] - d.get('used', 0))
        return True, f"激活成功！新增 {add_credits} 条额度，当前剩余 {new_remaining} 条"


# ═══════════════════════════════════════════════
# MP4 指纹修改
# ═══════════════════════════════════════════════

CONTAINERS = {'moov', 'trak', 'mdia', 'minf', 'stbl', 'udta', 'meta', 'ilst'}


def _find_atoms(f, targets, depth=10):
    results = []
    if depth <= 0:
        return results
    f.seek(0, 2)
    end = f.tell()
    f.seek(0)
    while f.tell() < end - 8:
        pos = f.tell()
        hdr = f.read(8)
        if len(hdr) < 8:
            break
        size, name = struct.unpack('>I4s', hdr)
        name = name.decode('ascii', errors='replace')
        if size == 1:
            size = struct.unpack('>Q', f.read(8))[0]
        elif size == 0:
            size = end - pos
        if size < 8 or pos + size > end:
            break
        if name in targets:
            results.append((pos, size, name))
        if name in CONTAINERS:
            skip = 12 if name == 'meta' else 8
            f.seek(pos + skip)
            results.extend(_find_atoms(f, targets, depth - 1))
        f.seek(pos + size)
    return results


def fingerprint_video(src, dst):
    """复制视频并修改指纹"""
    shutil.copy2(src, dst)
    changes = 0
    with open(dst, 'r+b') as f:
        # UUID
        for pos, size, name in _find_atoms(f, ['uuid']):
            f.seek(pos + 8)
            f.write(uuid.uuid4().bytes)
            changes += 1

        # 时间戳
        mp4_epoch = 2082844800
        new_ts = int(time.time()) + mp4_epoch
        for pos, size, name in _find_atoms(f, ['mvhd', 'tkhd']):
            f.seek(pos + 8)
            ver = struct.unpack('B', f.read(1))[0]
            ts_sz = 8 if ver else 4
            for off in [pos + 12, pos + 12 + ts_sz]:
                f.seek(off)
                if ts_sz == 4:
                    f.write(struct.pack('>I', new_ts & 0xFFFFFFFF))
                else:
                    f.write(struct.pack('>Q', new_ts))
                changes += 1

        # 随机填充
        f.seek(0, 2)
        f.write(os.urandom(32))
        changes += 1

    return changes


def gen_output_name(src_path):
    """生成输出文件名：原文件名_2位hex.mp4，碰撞自动递增"""
    stem = Path(src_path).stem
    ext = Path(src_path).suffix
    directory = os.path.dirname(src_path)
    while True:
        rand_hex = uuid.uuid4().hex[:2].upper()
        dst = os.path.join(directory, f"{stem}_{rand_hex}{ext}")
        if not os.path.exists(dst):
            return dst


# ═══════════════════════════════════════════════
# GUI
# ═══════════════════════════════════════════════

class App:
    BG = '#f5f5f5'
    HEADER_BG = '#1e293b'

    def __init__(self):
        self.cm = CreditManager()
        self.state = self.cm.get_state()
        self.root = tkinterdnd2.TkinterDnD.Tk()
        self.root.title("视频指纹批量修改工具")
        self.root.geometry("620x480")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG)
        self.files = []
        self._build_ui()

    def _build_ui(self):
        # ── 顶栏 ──
        top = tk.Frame(self.root, bg=self.HEADER_BG, height=44)
        top.pack(fill='x')
        top.pack_propagate(False)

        tk.Label(top, text="  视频指纹批量修改工具",
                 font=('Microsoft YaHei', 12, 'bold'), fg='white', bg=self.HEADER_BG
                 ).pack(side='left', padx=10)

        tk.Button(top, text="软件编号", font=('Microsoft YaHei', 8),
                  bg='#334155', fg='#94a3b8', relief='flat',
                  command=self._copy_id).pack(side='right', padx=5, pady=8)

        self.act_btn = tk.Button(top, text="", font=('Microsoft YaHei', 8),
                                 relief='flat', command=self._activate)
        self.act_btn.pack(side='right', padx=2, pady=8)

        self.credit_lbl = tk.Label(top, text="", font=('Microsoft YaHei', 9),
                                   fg='#a3e635', bg=self.HEADER_BG)
        self.credit_lbl.pack(side='right', padx=10)

        self._refresh_credit()

        # ── 主体 ──
        body = tk.Frame(self.root, bg=self.BG, padx=20, pady=10)
        body.pack(fill='both', expand=True)

        # 第一步：选视频
        tk.Label(body, text="第一步：选择视频文件",
                 font=('Microsoft YaHei', 10, 'bold'), bg=self.BG).pack(anchor='w')

        btn_row = tk.Frame(body, bg=self.BG)
        btn_row.pack(fill='x', pady=(2, 5))
        tk.Button(btn_row, text="添加视频", command=self._add, width=10).pack(side='left')
        tk.Button(btn_row, text="删除选中", command=self._delete_selected, width=8).pack(side='left', padx=5)
        tk.Button(btn_row, text="清空", command=self._clear, width=6).pack(side='left', padx=5)
        self.cnt_lbl = tk.Label(btn_row, text="已选 0 个文件",
                                font=('Microsoft YaHei', 9), bg=self.BG)
        self.cnt_lbl.pack(side='left', padx=10)

        lf = tk.Frame(body, bg=self.BG)
        lf.pack(fill='x', pady=(0, 10))
        self.listbox = tk.Listbox(lf, height=6, font=('Consolas', 9), selectmode=tk.EXTENDED)
        sb = tk.Scrollbar(lf, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=sb.set)
        self.listbox.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # 拖放支持（tkinterdnd2，Tcl原生扩展，无GIL冲突）
        VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.ts', '.m4v', '.mpg', '.mpeg', '.3gp'}

        def _on_drop(event):
            try:
                # tkinterdnd2 返回的路径用空格分隔，但带空格的路径用 {} 包裹
                raw = event.data
                files = []
                # 解析 {path with spaces} 和 path_without_spaces
                import re
                parts = re.findall(r'\{([^}]+)\}|([^\s{}]+)', raw)
                for group in parts:
                    path = group[0] or group[1]
                    if os.path.splitext(path)[1].lower() in VIDEO_EXTS and path not in self.files:
                        self.files.append(path)
                        self.listbox.insert(tk.END, path)
                self.cnt_lbl.config(text=f"已选 {len(self.files)} 个文件")
            except Exception as e:
                print(f"拖放错误: {e}")

        self.listbox.drop_target_register(tkinterdnd2.DND_FILES)
        self.listbox.dnd_bind('<<Drop>>', _on_drop)

        # 第二步：每条生成几份
        tk.Label(body, text="第二步：每条视频生成几份",
                 font=('Microsoft YaHei', 10, 'bold'), bg=self.BG).pack(anchor='w')

        copy_row = tk.Frame(body, bg=self.BG)
        copy_row.pack(fill='x', pady=(2, 5))

        self.copy_var = tk.StringVar(value="3")
        for n in [2, 3, 5, 10]:
            tk.Radiobutton(copy_row, text=f"{n}份", variable=self.copy_var, value=str(n),
                           bg=self.BG, font=('Microsoft YaHei', 9)).pack(side='left', padx=8)
        tk.Label(copy_row, text="或自定义:", bg=self.BG,
                 font=('Microsoft YaHei', 9)).pack(side='left', padx=(15, 3))
        tk.Entry(copy_row, textvariable=self.copy_var, width=5,
                 font=('Consolas', 10)).pack(side='left')

        # 提示
        tk.Label(body, text="生成的文件将保存在源视频同目录，命名格式：原文件名_随机码.mp4",
                 font=('Microsoft YaHei', 8), fg='#94a3b8', bg=self.BG).pack(anchor='w', pady=(0, 5))

        # 进度
        self.progress = ttk.Progressbar(body, mode='determinate')
        self.progress.pack(fill='x', pady=(5, 3))
        self.status_lbl = tk.Label(body, text="就绪", font=('Microsoft YaHei', 9),
                                   bg=self.BG, anchor='w')
        self.status_lbl.pack(fill='x')

        # 开始按钮
        tk.Button(body, text="开始生成", command=self._start,
                  bg='#2563eb', fg='white', font=('Microsoft YaHei', 12, 'bold'),
                  relief='flat', height=2, cursor='hand2').pack(fill='x', pady=(8, 0))

        # 底部套餐提示
        self.pricing_lbl = tk.Label(body, text="", font=('Microsoft YaHei', 8),
                                    fg='#94a3b8', bg=self.BG)
        self.pricing_lbl.pack(pady=(5, 0))
        self._refresh_pricing()

    def _refresh_credit(self):
        s = self.state
        if s['licensed'] and s['total'] >= 999999:
            # 永久版
            self.act_btn.config(text="已激活", bg='#166534', fg='white')
            self.credit_lbl.config(text="永久版 - 不限量", fg='#a3e635')
        elif s['remaining'] > 0:
            # 有额度（试用或套餐激活）
            if s['total'] > TRIAL_CREDITS:
                self.act_btn.config(text="已激活", bg='#166534', fg='white')
            else:
                self.act_btn.config(text="输入激活码", bg='#3b82f6', fg='white')
            color = '#a3e635' if s['remaining'] > 10 else ('#fbbf24' if s['remaining'] > 3 else '#f87171')
            self.credit_lbl.config(text=f"剩余额度: {s['remaining']}", fg=color)
        else:
            # 额度用完
            self.act_btn.config(text="输入激活码", bg='#3b82f6', fg='white')
            self.credit_lbl.config(text="剩余额度: 0", fg='#f87171')

    def _refresh_pricing(self):
        if self.state['licensed'] and self.state['total'] >= 999999:
            # 永久版已激活，隐藏套餐
            self.pricing_lbl.config(text="")
        else:
            self.pricing_lbl.config(
                text="基础版100条 ¥49 | 标准版300条 ¥99 | 旗舰版800条 ¥149 | 永久版 ¥499  (额度可叠加)")

    def _copy_id(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.cm.machine_id)
        messagebox.showinfo("已复制", "软件编号已复制到剪贴板\n\n如需购买，请将此编号发给客服")

    def _activate(self):
        if self.state['licensed']:
            messagebox.showinfo("已激活", "软件已激活，可无限制使用")
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("激活软件")
        dlg.geometry("400x160")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        tk.Label(dlg, text="请输入激活码:", font=('Microsoft YaHei', 10)).pack(pady=(20, 5))
        kv = tk.StringVar()
        e = tk.Entry(dlg, textvariable=kv, font=('Consolas', 10), width=42)
        e.pack()
        e.focus()
        rl = tk.Label(dlg, text="", font=('Microsoft YaHei', 9))
        rl.pack(pady=5)

        def go():
            ok, info = self.cm.activate(kv.get().strip())
            rl.config(text=info, fg='#22c55e' if ok else '#ef4444')
            if ok:
                self.state = self.cm.get_state()
                self._refresh_credit()
                self._refresh_pricing()
                dlg.after(1500, dlg.destroy)

        tk.Button(dlg, text="激活", command=go, bg='#3b82f6', fg='white',
                  relief='flat', width=10).pack(pady=3)

    def _add(self):
        for f in filedialog.askopenfilenames(
            filetypes=[("视频", "*.mp4 *.avi *.mkv *.mov *.flv *.wmv *.ts"), ("所有", "*.*")]
        ):
            if f not in self.files:
                self.files.append(f)
                self.listbox.insert(tk.END, f)
        self.cnt_lbl.config(text=f"已选 {len(self.files)} 个文件")

    def _delete_selected(self):
        """删除选中的视频文件"""
        selected = self.listbox.curselection()
        if not selected:
            messagebox.showinfo("提示", "请先选择要删除的视频")
            return
        # 从后往前删除，避免索引偏移
        for idx in reversed(selected):
            self.listbox.delete(idx)
            self.files.pop(idx)
        self.cnt_lbl.config(text=f"已选 {len(self.files)} 个文件")

    def _clear(self):
        self.files.clear()
        self.listbox.delete(0, tk.END)
        self.cnt_lbl.config(text="已选 0 个文件")

    def _start(self):
        if not self.files:
            messagebox.showwarning("提示", "请先添加视频文件")
            return
        try:
            copies = int(self.copy_var.get())
            if copies < 1:
                raise ValueError
        except:
            messagebox.showwarning("提示", "请输入有效的份数（大于0的整数）")
            return

        total_needed = len(self.files) * copies
        if not self.state['licensed']:
            if total_needed > self.state['remaining']:
                if messagebox.askyesno("额度不足",
                    f"需要 {total_needed} 个额度（{len(self.files)}个文件 x {copies}份）\n"
                    f"剩余 {self.state['remaining']} 个额度\n\n是否购买激活码？"):
                    self._activate()
                return

        self._run_async(copies)

    def _run_async(self, copies):
        self._processing = True
        for w in self.root.winfo_children():
            if isinstance(w, tk.Button) and w.cget('text') == '开始生成':
                w.config(state='disabled', text='生成中...')
                break
        threading.Thread(target=self._run, args=(copies,), daemon=True).start()

    def _run(self, copies):
        total = len(self.files) * copies
        done = 0
        errors = []

        for src in self.files:
            for _ in range(copies):
                dst = gen_output_name(src)
                try:
                    fingerprint_video(src, dst)
                    done += 1
                except Exception as e:
                    errors.append(f"{os.path.basename(src)}: {e}")

                pct = done / total * 100
                self.root.after(0, lambda v=pct: self.progress.config(value=v))
                self.root.after(0,
                    lambda s=f"({done}/{total}) {os.path.basename(src)}":
                    self.status_lbl.config(text=s))

        # 扣额度
        if not self.state['licensed']:
            self.cm.use(done)
            self.state = self.cm.get_state()

        self.root.after(0, lambda: self.progress.config(value=100))

        msg = f"完成！成功生成 {done} 个文件"
        if errors:
            msg += f"\n失败 {len(errors)} 个:\n" + '\n'.join(errors[:3])

        def finish():
            messagebox.showinfo("完成", msg)
            self.status_lbl.config(text=f"完成 - 生成 {done} 个文件")
            self._refresh_credit()
            for w in self.root.winfo_children():
                if isinstance(w, tk.Button) and w.cget('text') == '生成中...':
                    w.config(state='normal', text='开始生成')
                    break

        self.root.after(0, finish)

    def run(self):
        self.root.mainloop()


# ═══════════════════════════════════════════════
# 入口 - 单实例锁
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    locked, handle = try_lock()
    if not locked:
        # 已有实例在运行，弹出提示
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("提示", "程序已在运行中，请勿重复打开")
        root.destroy()
        sys.exit(0)
    try:
        App().run()
    finally:
        if handle and sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.kernel32.ReleaseMutex(handle)
                ctypes.windll.kernel32.CloseHandle(handle)
            except:
                pass
