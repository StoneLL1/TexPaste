# TexPaste — CLAUDE.md

## Project Overview

**TexPaste** 是一个 Windows 桌面效率工具，面向需要频繁处理数学公式/文本的用户（研究人员、学生）。核心流程：

1. 用户按快捷键 → 框选屏幕区域截图
2. 调用 LLM API 识别内容（纯文本 / LaTeX / Markdown+公式）
3. 识别结果自动写入剪贴板
4. 用户在 Word/WPS 中按智能粘贴快捷键 → 公式以原生格式插入

**成功指标**：识别准确率 ≥95%，端到端响应 ≤5s，CSAT ≥4.5/5.0。

---

## Core Features

| ID | 功能 | 默认快捷键 |
|----|------|-----------|
| US-001 | 托盘图标常驻，菜单含设置/暂停/退出 | — |
| US-002 | 全局快捷键触发区域截图 | Ctrl+Shift+A |
| US-003 | LLM API 识别（自动判断 Text/LaTeX/Markdown） | — |
| US-004 | 识别结果自动复制到剪贴板 | — |
| US-005 | Word/WPS 智能粘贴（Pandoc+COM） | Ctrl+Shift+V |
| US-006 | API 配置（地址/Key/模型，兼容 OpenAI 格式） | — |
| US-007 | 快捷键自定义 | — |
| US-008 | 历史记录管理（SQLite，7天自动清理） | — |

**输出格式规则**：
- 纯文字 → Plain Text
- 纯公式 → 裸 LaTeX（不加 `$` 包裹）
- 混合内容 → Markdown，行内公式 `$...$`，块公式 `$$...$$`

---

## Architecture (3-Layer)

```
┌─────────────────────────────────────┐
│  UI Layer                           │
│  TrayManager | SettingsUI |         │
│  HistoryUI | ScreenshotOverlay      │
├─────────────────────────────────────┤
│  Application Controller             │
│  AppController (state machine)      │
│  States: IDLE → CAPTURING →         │
│          RECOGNIZING → DONE         │
├─────────────────────────────────────┤
│  Core Services                      │
│  HotkeyManager  ScreenshotCapture   │
│  RecognizerService  ClipboardManager│
│  WordPasteService                   │
├─────────────────────────────────────┤
│  Infrastructure                     │
│  ConfigManager  HistoryRepository   │
│  Logger  UpdateChecker              │
└─────────────────────────────────────┘
```

---

## Directory Structure (Actual)

```
TexPaste/
├── src/
│   ├── main.py                        # 入口：单实例锁 + 启动 AppController
│   ├── app/
│   │   ├── controller.py              # AppController：主状态机
│   │   ├── tray.py                    # TrayManager：托盘图标
│   │   ├── settings_ui.py             # SettingsUI：设置窗口（含快捷键Tab）
│   │   ├── history_ui.py              # HistoryUI：历史记录窗口
│   │   └── screenshot_overlay.py     # ScreenshotOverlay：截图遮罩层
│   ├── core/
│   │   ├── hotkey.py                  # HotkeyManager
│   │   ├── screenshot.py              # ScreenshotCapture
│   │   ├── recognizer.py              # RecognizerService + Worker
│   │   ├── clipboard.py               # ClipboardManager + detect_content_type
│   │   └── word_paste.py              # WordPasteService + PandocConverter + Worker
│   ├── models/
│   │   ├── enums.py                   # ContentType, AppState
│   │   └── history.py                 # HistoryRecord dataclass
│   ├── utils/
│   │   ├── config.py                  # ConfigManager
│   │   ├── db.py                      # HistoryRepository
│   │   ├── logger.py                  # 日志初始化
│   │   ├── startup.py                 # StartupChecker
│   │   └── updater.py                 # UpdateChecker
│   └── resources/
│       ├── icons/                     # texpaste.ico, tray_*.png
│       └── prompts/recognize.txt      # System prompt 模板
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/formulas/
├── scripts/
│   ├── build.py
│   └── release.py
├── docs/
│   ├── prd.md
│   ├── architecture.md
│   └── dev-spec.md
├── config.default.json
├── texpaste.spec
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

## Key Modules

| 模块 | 文件 | 职责 |
|------|------|------|
| `AppController` | `src/app/controller.py` | 状态机，协调所有服务 |
| `HotkeyManager` | `src/core/hotkey.py` | pynput 全局热键监听（后台线程） |
| `ScreenshotOverlay` | `src/app/screenshot_overlay.py` | 全屏透明窗口 + QRubberBand 框选 |
| `RecognizerService` | `src/core/recognizer.py` | httpx 异步调用 LLM API，QThread worker |
| `ClipboardManager` | `src/core/clipboard.py` | QClipboard 读写 |
| `WordPasteService` | `src/core/word_paste.py` | Pandoc + COM 接口插入公式 |
| `ConfigManager` | `src/utils/config.py` | JSON 配置读写，dot-notation 访问 |
| `HistoryRepository` | `src/utils/db.py` | SQLite CRUD，7天自动清理 |

### ⚠️ WordPasteService — 特别说明

参考了开源项目 [pastemd](https://github.com/euclidean-dreams/pastemd) 的实现逻辑。

核心流程：
1. 检测当前激活窗口是否为 Word/WPS（`pywin32 GetForegroundWindow`）
2. 调用 **Pandoc** 将 Markdown/LaTeX 内容转换为 `.docx` 临时文件
3. 通过 **pywin32 COM 接口**（`win32com.client`）将转换后内容插入光标位置

---

## Development Environment

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
cp config.default.json config.json
python src/main.py
```

需要系统安装 **Pandoc**：https://pandoc.org/installing.html

---

## Coding Standards

- Python 3.11+，PEP 8，行宽 100 字符
- 所有函数必须有类型注解
- `ruff format && ruff check` + `mypy --strict`（utils/, models/）
- 命名：`snake_case` 函数/变量，`PascalCase` 类，`UPPER_SNAKE_CASE` 常量
- Qt 槽函数加 `@Slot()` 装饰器
- **禁止在主线程做阻塞 IO**

---

## Threading Model

```
主线程 (Qt Event Loop)
  ├── TrayManager / ScreenshotOverlay / SettingsUI / HistoryUI

后台线程
  ├── HotkeyListenerThread  (pynput)
  ├── RecognitionWorker     (httpx → QThread)
  └── WordPasteWorker       (Pandoc subprocess + COM → QThread)
```

线程通信：**只通过 Qt Signals/Slots**

---

## Error Handling

| 级别 | 场景 | 处理方式 |
|------|------|---------|
| FATAL | 配置损坏、重复启动 | 弹窗提示，安全退出 |
| ERROR | API 失败、COM 异常 | 系统通知 + 写日志，保持运行 |
| WARNING | Pandoc 未安装 | 通知提示 |
| INFO | 正常流程节点 | 仅写日志 |

API 调用：指数退避重试 3 次（1s → 2s → 4s），超时 30s。日志禁止记录 API Key。

---

## Build

```bash
python scripts/build.py
# 输出：dist/TexPaste.exe
```

---

## Key References

- **pastemd**：https://github.com/euclidean-dreams/pastemd
- **docs/**：prd.md / architecture.md / dev-spec.md
