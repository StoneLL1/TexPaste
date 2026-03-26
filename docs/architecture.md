# TexPaste 技术架构文档

**版本：** 1.0
**日期：** 2026-03-26
**状态：** 待审阅

---

## 1. 架构总览

### 1.1 设计原则

| 原则 | 说明 |
|------|------|
| 单一职责 | 每个模块只负责一个明确的功能域 |
| 依赖反转 | 核心业务逻辑不依赖具体实现，通过接口注入 |
| 失败隔离 | API 失败、COM 失败、Pandoc 失败互不影响主进程 |
| 最小权限 | 仅在需要时访问剪贴板、COM 接口 |
| 便携优先 | 配置、数据均存放在程序目录，支持 U 盘携带 |

### 1.2 整体架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                         TexPaste Process                             │
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐ │
│  │  TrayManager │   │ SettingsUI   │   │    HistoryUI             │ │
│  │  (UI Layer)  │   │  (UI Layer)  │   │    (UI Layer)            │ │
│  └──────┬───────┘   └──────┬───────┘   └────────────┬─────────────┘ │
│         │                  │                        │               │
│         └──────────────────┴────────────────────────┘               │
│                            │ Qt Signals / Slots                     │
│                            ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                     Application Controller                      │ │
│  │              (orchestrates all core services)                   │ │
│  └────┬──────────────┬──────────────┬─────────────────┬────────────┘ │
│       │              │              │                 │              │
│       ▼              ▼              ▼                 ▼              │
│  ┌─────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Hotkey  │  │ Screenshot │  │Clipboard │  │  WordPaste       │   │
│  │ Manager │  │  Capture   │  │ Manager  │  │  Service         │   │
│  └─────────┘  └─────┬──────┘  └────┬─────┘  └────────┬─────────┘   │
│                     │              │                  │              │
│                     ▼              │                  ▼              │
│               ┌───────────┐        │         ┌───────────────────┐  │
│               │Recognizer │        │         │  PandocConverter  │  │
│               │ Service   │        │         │  + COM Handler    │  │
│               └─────┬─────┘        │         └───────────────────┘  │
│                     │              │                                 │
│                     └──────────────┘                                │
│                            │                                        │
│         ┌──────────────────┼──────────────────┐                    │
│         ▼                  ▼                  ▼                    │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐             │
│  │ ConfigMgr   │  │  HistoryRepo │  │   Logger      │             │
│  │ (JSON)      │  │  (SQLite)    │  │               │             │
│  └─────────────┘  └──────────────┘  └───────────────┘             │
└──────────────────────────────────────────────────────────────────────┘
           │                                        │
           ▼                                        ▼
  ┌─────────────────┐                    ┌──────────────────┐
  │  LLM Vision API │                    │  Pandoc CLI      │
  │  (OpenAI-compat)│                    │  (external proc) │
  └─────────────────┘                    └──────────────────┘
```

---

## 2. 层次结构

### 2.1 UI Layer（用户界面层）

负责所有可见界面，仅通过 Qt Signals 与下层通信，不包含业务逻辑。

| 组件 | 类名 | 职责 |
|------|------|------|
| 托盘图标 | `TrayManager` | 系统托盘图标、菜单、状态图标切换 |
| 设置窗口 | `SettingsUI` | API 配置、快捷键录制、通用选项 |
| 历史记录窗口 | `HistoryUI` | 历史列表展示、搜索、点击复制 |
| 截图遮罩层 | `ScreenshotOverlay` | 全屏半透明遮罩 + 橡皮筋框选 |

### 2.2 Application Controller（应用控制器）

单例，协调所有核心服务，响应热键事件，驱动识别→剪贴板→通知的完整流程。

**状态机：**

```
IDLE ──(hotkey_screenshot)──► CAPTURING
CAPTURING ──(area_selected)──► RECOGNIZING
CAPTURING ──(ESC)──────────── ► IDLE
RECOGNIZING ──(success)──────► IDLE  (clipboard updated)
RECOGNIZING ──(failure)──────► IDLE  (notification shown)
IDLE ──(hotkey_paste)─────────► PASTING
PASTING ──(success/failure)──► IDLE
```

### 2.3 Core Services Layer（核心服务层）

| 服务 | 类名 | 关键依赖 |
|------|------|----------|
| 快捷键管理 | `HotkeyManager` | `pynput` |
| 截图捕获 | `ScreenshotCapture` | `PyQt6.QScreen` |
| 识别服务 | `RecognizerService` | `httpx`（异步） |
| 剪贴板管理 | `ClipboardManager` | `pyperclip`, `win32clipboard` |
| Word 粘贴 | `WordPasteService` | `pywin32`, `subprocess(pandoc)` |

### 2.4 Infrastructure Layer（基础设施层）

| 组件 | 类名 | 说明 |
|------|------|------|
| 配置管理 | `ConfigManager` | 读写 `config.json`，提供默认值 |
| 历史记录仓库 | `HistoryRepository` | SQLite CRUD，自动清理过期记录 |
| 日志工具 | `Logger` | 基于 `logging` 模块，滚动文件日志 |
| 更新检查 | `UpdateChecker` | GitHub Releases API 检查最新版本 |

---

## 3. 关键流程

### 3.1 截图识别流程

```
User presses Ctrl+Shift+A
        │
        ▼
HotkeyManager fires `screenshot_triggered` signal
        │
        ▼
AppController receives signal
  → sets state = CAPTURING
  → calls ScreenshotCapture.start_capture()
        │
        ▼
ScreenshotOverlay shown (full screen, semi-transparent)
User drags to select area
        │
        ├──(ESC pressed)──► overlay hidden, state = IDLE
        │
        └──(mouse released)──►
              ScreenshotCapture captures QPixmap
              → converts to PNG bytes → base64 encode
              → fires `capture_complete(base64_str)` signal
                      │
                      ▼
              AppController receives signal
                → state = RECOGNIZING
                → tray icon = spinning/loading
                → calls RecognizerService.recognize(base64_str)
                        │
                        ▼
                RecognizerService sends HTTP POST to LLM API
                  (httpx async, runs in QThread worker)
                        │
                        ├──(API error/timeout)──►
                        │    fires `recognition_failed(error_msg)`
                        │    → tray icon = error
                        │    → system notification shown
                        │    → state = IDLE
                        │
                        └──(success)──►
                              fires `recognition_complete(result, content_type)`
                                      │
                                      ▼
                              AppController:
                                → ClipboardManager.set_text(result)
                                → HistoryRepository.save(screenshot, result)
                                → tray icon = normal
                                → system notification: "已复制到剪贴板"
                                → state = IDLE
```

### 3.2 智能粘贴流程

```
User presses Ctrl+Shift+V
        │
        ▼
HotkeyManager fires `paste_triggered` signal
        │
        ▼
AppController:
  → check active window title (win32gui.GetForegroundWindow)
  │
  ├──(not Word/WPS)──► system notification: "请在 Word/WPS 中使用"
  │                    state = IDLE
  │
  └──(is Word/WPS)──►
        content = ClipboardManager.get_text()
        content_type = detect_content_type(content)
                │
                ├──(plain text)──►
                │    WordPasteService.paste_text(content)
                │    → word.Selection.TypeText(content)
                │
                ├──(pure LaTeX)──►
                │    md_content = f"$${content}$$"
                │    docx_path = PandocConverter.md_to_docx(md_content)
                │    WordPasteService.insert_docx(docx_path)
                │    → temp docx opened → content copied → pasted → closed
                │
                └──(markdown with formulas)──►
                     docx_path = PandocConverter.md_to_docx(content)
                     WordPasteService.insert_docx(docx_path)
```

### 3.3 内容类型判断逻辑

```python
def detect_content_type(text: str) -> ContentType:
    """
    判断剪贴板内容类型，用于决定粘贴策略。
    优先级：Markdown with formula > pure LaTeX > plain text
    """
    has_inline_formula  = bool(re.search(r'\$.+?\$', text))
    has_display_formula = bool(re.search(r'\$\$.+?\$\$', text, re.DOTALL))
    has_markdown_syntax = bool(re.search(r'[#*`\[\]]', text))
    looks_like_latex    = bool(re.search(r'\\[a-zA-Z]+\{', text))

    if has_inline_formula or has_display_formula or has_markdown_syntax:
        return ContentType.MARKDOWN
    elif looks_like_latex:
        return ContentType.PURE_LATEX
    else:
        return ContentType.PLAIN_TEXT
```

---

## 4. 模块接口定义

### 4.1 RecognizerService

```python
class RecognizerService(QObject):
    # Signals
    recognition_complete = Signal(str, str)  # (result, content_type)
    recognition_failed   = Signal(str)       # (error_message)
    recognition_progress = Signal(str)       # (status_text)

    def recognize(self, image_base64: str) -> None:
        """启动异步识别，结果通过 Signal 返回"""

    def cancel(self) -> None:
        """取消当前识别请求"""
```

### 4.2 HotkeyManager

```python
class HotkeyManager(QObject):
    # Signals
    screenshot_triggered = Signal()
    paste_triggered      = Signal()

    def register(self, screenshot_key: str, paste_key: str) -> bool:
        """注册全局热键，返回是否成功"""

    def unregister(self) -> None:
        """注销所有热键"""

    def update_hotkeys(self, screenshot_key: str, paste_key: str) -> bool:
        """热更新快捷键（无需重启）"""
```

### 4.3 WordPasteService

```python
class WordPasteService:
    def is_word_active(self) -> bool:
        """检测当前前台窗口是否为 Word 或 WPS"""

    def paste(self, content: str, content_type: ContentType) -> tuple[bool, str]:
        """执行智能粘贴，返回 (success, message)"""
```

### 4.4 ConfigManager

```python
class ConfigManager:
    def get(self, key: str, default=None) -> Any:
        """点分路径读取配置，如 'api.endpoint'"""

    def set(self, key: str, value: Any) -> None:
        """点分路径写入配置并持久化"""

    def reload(self) -> None:
        """从磁盘重新加载配置"""
```

### 4.5 HistoryRepository

```python
class HistoryRepository:
    def save(self, screenshot: bytes, result: str, content_type: str) -> int:
        """保存识别记录，返回记录 ID"""

    def list(self, limit: int = 50, offset: int = 0) -> list[HistoryRecord]:
        """分页查询历史记录"""

    def search(self, query: str) -> list[HistoryRecord]:
        """全文搜索历史记录"""

    def delete_expired(self, retention_days: int) -> int:
        """删除过期记录，返回删除数量"""
```

---

## 5. 数据模型

### 5.1 HistoryRecord（SQLite）

```sql
CREATE TABLE history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT    NOT NULL,          -- ISO8601
    content_type TEXT    NOT NULL,          -- 'text' | 'latex' | 'markdown'
    result       TEXT    NOT NULL,          -- 识别结果
    thumbnail    BLOB,                      -- PNG 截图缩略图（最大 100x100）
    api_model    TEXT                       -- 使用的模型名称
);

CREATE INDEX idx_history_created_at ON history(created_at);
CREATE INDEX idx_history_result_fts ON history(result);  -- 用于 LIKE 搜索
```

### 5.2 ContentType 枚举

```python
from enum import Enum

class ContentType(str, Enum):
    PLAIN_TEXT = "text"
    PURE_LATEX = "latex"
    MARKDOWN   = "markdown"
```

---

## 6. 线程模型

TexPaste 使用 Qt 事件循环为主线程，计算/IO 密集任务放入 Worker 线程，通过 Signal/Slot 通信。

```
Main Thread (Qt Event Loop)
├── UI rendering
├── Tray icon
├── Hotkey signal dispatch
└── State machine transitions

Worker Thread 1: RecognitionWorker (QThread)
└── httpx async HTTP calls to LLM API

Worker Thread 2: WordPasteWorker (QThread)
├── subprocess(pandoc) call
└── COM interface calls (blocking)

Timer Thread: CleanupTimer (QTimer, 24h interval)
└── HistoryRepository.delete_expired()
```

**规则：**
- COM 接口（pywin32）**必须**在独立线程中调用，不可在主线程阻塞
- UI 更新**必须**通过 Signal 在主线程执行，不可跨线程操作 Qt 控件
- httpx 异步调用使用 `asyncio.run()` 在 Worker 线程的独立事件循环中执行

---

## 7. 错误处理策略

### 7.1 错误分级

| 级别 | 描述 | 处理方式 |
|------|------|----------|
| FATAL | 程序无法启动（配置损坏、依赖缺失） | 弹出对话框 + 退出 |
| ERROR | 功能失败（API 错误、COM 失败） | 系统通知 + 托盘图标变红 + 记录日志 |
| WARNING | 非关键失败（更新检查失败、历史记录写入失败） | 记录日志，静默处理 |
| INFO | 正常操作日志 | 记录日志 |

### 7.2 启动时检查

```python
class StartupChecker:
    def check_all(self) -> list[StartupError]:
        checks = [
            self._check_pandoc(),       # pandoc --version
            self._check_config(),       # JSON 可解析
            self._check_single_instance(),  # 防止重复启动
        ]
        return [e for e in checks if e is not None]
```

### 7.3 API 重试策略

```
Request
  │
  ├──(success)──► return result
  │
  └──(failure)──►
        retry_count += 1
        if retry_count <= max_retries (default 3):
            wait 2^retry_count seconds (exponential backoff)
            goto Request
        else:
            raise RecognitionError(last_error)
```

---

## 8. 打包方案

### 8.1 PyInstaller 配置

```python
# texpaste.spec
block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[
        ('pandoc.exe', '.'),        # 将 pandoc.exe 打包进去
    ],
    datas=[
        ('src/resources', 'resources'),
    ],
    hiddenimports=[
        'win32com.client',
        'win32gui',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
    ],
    ...
)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name='TexPaste',
    icon='src/resources/icons/texpaste.ico',
    console=False,          # 无控制台窗口
    upx=True,               # UPX 压缩
    onefile=True,
)
```

### 8.2 数据文件位置策略

```python
def get_app_data_dir() -> Path:
    """
    便携模式：配置与数据存放在 exe 同级目录
    安装模式：存放在 %APPDATA%/TexPaste
    """
    exe_dir = Path(sys.executable).parent
    portable_flag = exe_dir / '.portable'

    if portable_flag.exists():
        return exe_dir
    else:
        return Path(os.environ['APPDATA']) / 'TexPaste'
```

---

## 9. 外部依赖版本矩阵

| 依赖 | 最低版本 | 推荐版本 | 说明 |
|------|----------|----------|------|
| Python | 3.10 | 3.11+ | f-string + match statement |
| PyQt6 | 6.4.0 | 6.6.0+ | QSystemTrayIcon 稳定性 |
| pynput | 1.7.6 | 1.7.7+ | Windows 热键支持 |
| httpx | 0.24.0 | 0.27.0+ | 异步 HTTP |
| pywin32 | 305 | 306+ | COM 接口 |
| pyperclip | 1.8.2 | 1.9.0+ | 剪贴板 |
| Pandoc | 3.0 | 3.2+ | OMML 输出质量 |

---

## 10. 安全设计

### 10.1 API Key 保护

- API Key **不写入**日志文件
- 设置界面密码框遮罩（`QLineEdit.setEchoMode(Password)`）
- 配置文件权限设置为仅当前用户可读（`os.chmod(config_path, 0o600)`）
- 未来可选：使用 Windows DPAPI 加密存储

### 10.2 截图数据流向

```
Screen pixels
    │
    ▼
QPixmap (in memory only)
    │
    ▼
PNG bytes → base64 string
    │
    ├──► HTTPS POST to user-configured API endpoint  (only copy that leaves device)
    │
    └──► Thumbnail (100x100 max) → SQLite BLOB       (local only)

原始截图不写入磁盘
```
