# 视频指纹批量修改工具 V2.0

## 项目结构

```
video-fingerprint/
├── src/                        # 客户端源码
│   ├── video_fingerprint_gui.py   # 主程序 GUI
│   ├── ed25519_license.py         # Ed25519 签名验证
│   ├── license_core.py            # 额度持久化（三层存储）
│   └── pricing.py                 # 套餐定价配置
│
├── tests/                      # 测试脚本
│   ├── test_ed25519.py            # 签名系统测试
│   ├── test_final.py              # 集成测试
│   ├── test_system.py             # 系统测试
│   ├── test_core.py               # 核心功能测试
│   └── check_persist.py           # 持久化检查
│
├── build/                      # 打包脚本（本地）
│   ├── 打包.bat                   # PyInstaller 一键打包
│   └── setup_installer.iss        # Inno Setup 安装包
│
├── .gitignore                  # 排除敏感文件和构建产物
└── README.md                   # 本文件
```

> **注意**：`tools/`（激活码生成器）、`config/`（密钥和授权文件）、`dist/`（打包产物）
> 均在 `.gitignore` 中排除，不会上传到 GitHub。

## 快速开始

### 安装依赖

```bash
pip install cryptography tkinterdnd2
```

### 客户端运行

```bash
python src/video_fingerprint_gui.py
```

### 开发者操作（本地）

```bash
# 打包客户端 exe
build/打包.bat
```

> 激活码生成器和密钥文件仅存在于本地，不随仓库分发。

## 套餐定价

| 套餐 | 条数 | 价格 | 单价 |
|------|------|------|------|
| 免费试用 | 20 | ¥0 | - |
| 基础版 | 100 | ¥49 | ¥0.49/条 |
| 标准版 | 300 | ¥99 | ¥0.33/条 |
| 旗舰版 | 800 | ¥149 | ¥0.19/条 |
| 永久版 | 不限 | ¥499 | - |

## 安全机制

- **Ed25519 数字签名**：公钥泄露也无法伪造激活码
- **机器码绑定**：激活码内嵌硬件指纹
- **三层持久化**：注册表 + AppData + ProgramData
- **离线验证**：无需服务器/数据库
