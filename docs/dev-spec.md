# TexPaste 开发规范文档

**版本：** 1.0
**日期：** 2026-03-26

---

## 1. 项目结构

```
texpaste/
├── src/
│   ├── main.py                     # 入口：初始化 QApplication，启动 AppController
│   ├── app/
│   │   ├── __init__.py
│   │   ├── controller.py           # AppController：主状态机，协调所有服务
│   │   ├── tray.py                 # TrayManager：托盘图标与菜单
│   │   ├── settings_ui.py          # SettingsUI：设置窗口
│   │   ├── history_ui.py           # HistoryUI：历史记录窗口
│   │   └── screenshot_overlay.py  # ScreenshotOverlay：截图遮罩层
│   ├── core/
│   │   ├── __init__.py
│   │   ├── hotkey.py               # HotkeyManager
│   │   ├── screenshot.py           # ScreenshotCapture
│   │   ├── recognizer.py           # RecognizerService + RecognitionWorker
│   │   ├── clipboard.py            # ClipboardManager
│   │   └── word_paste.py           # WordPasteService + PandocConverter
│   ├── models/
│   │   ├── __init__.py
│   │   ├── enums.py                # ContentType, AppState 等枚举
│   │   └── history.py              # HistoryRecord dataclass
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py               # ConfigManager
│   │   ├── db.py                   # HistoryRepository
│   │   ├── logger.py               # 日志初始化
│   │   ├── startup.py              # StartupChecker
│   │   └── updater.py              # UpdateChecker
│   └── resources/
│       ├── icons/
│       │   ├── texpaste.ico        # 主图标
│       │   ├── tray_normal.png
│       │   ├── tray_loading.png
│       │   ├── tray_error.png
│       │   └── tray_paused.png
│       └── prompts/
│           └── recognize.txt       # System prompt 模板
├── tests/
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_content_type.py
│   │   ├── test_history.py
│   │   └── test_pandoc.py
│   ├── integration/
│   │   ├── test_recognizer.py      # 需要有效 API Key
│   │   └── test_word_paste.py      # 需要 Word/WPS 安装
│   └── fixtures/
│       └── formulas/               # 测试用截图 PNG
├── scripts/
│   ├── build.py                    # PyInstaller 打包脚本
│   └── release.py                  # 版本号更新 + 打包
├── config.json                     # 运行时配置（git ignore）
├── config.default.json             # 默认配置模板（纳入 git）
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .gitignore
└── README.md
```

---

## 2. 编码规范

### 2.1 Python 版本与风格

- **Python 3.11+**，使用 `match` 语句替代 if-elif 链
- 遵循 **PEP 8**，行长限制 **100 字符**
- 使用 **类型注解**（`from __future__ import annotations`）
- 格式化工具：`ruff format`（替代 black）
- Lint 工具：`ruff check`
- 类型检查：`mypy --strict`（核心模块）

### 2.2 命名约定

| 对象 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | `snake_case.py` | `word_paste.py` |
| 类名 | `PascalCase` | `RecognizerService` |
| 函数/方法 | `snake_case` | `detect_content_type` |
| 常量 | `UPPER_SNAKE_CASE` | `DEFAULT_TIMEOUT` |
| Qt Signal | `snake_case` | `recognition_complete` |
| 私有方法 | `_snake_case` | `_convert_to_docx` |

### 2.3 导入顺序

```python
# 1. 标准库
import os
import re
from pathlib import Path

# 2. 第三方库
import httpx
from PyQt6.QtCore import QObject, Signal
from PyQt6.QtWidgets import QSystemTrayIcon

# 3. 本项目模块
from models.enums import ContentType
from utils.config import ConfigManager
```

### 2.4 Qt 开发规范

- Signal 定义放在类体最顶部，紧跟 `__init__`
- **禁止**在 Worker 线程中直接操作任何 Qt Widget
- **禁止**在主线程中执行阻塞 IO（HTTP、COM、subprocess）
- 使用 `QThread` + Worker 对象模式，不继承 `QThread`：

```python
# 正确
class RecognitionWorker(QObject):
    finished = Signal(str)
    def run(self): ...

thread = QThread()
worker = RecognitionWorker()
worker.moveToThread(thread)
thread.started.connect(worker.run)

# 错误 - 不要继承 QThread
class BadWorker(QThread):
    def run(self): ...
```

### 2.5 错误处理规范

- 所有对外 IO 操作必须 `try/except`，捕获具体异常类型
- 不允许裸 `except:` 或 `except Exception as e: pass`
- 错误信息必须记录到日志
- 面向用户的错误提示使用中文，日志使用英文

```python
# 正确
try:
    result = await self._call_api(image_base64)
except httpx.TimeoutException:
    logger.error("API request timed out after %ds", self.timeout)
    self.recognition_failed.emit("请求超时，请检查网络连接")
except httpx.HTTPStatusError as e:
    logger.error("API returned HTTP %d: %s", e.response.status_code, e.response.text)
    self.recognition_failed.emit(f"API 错误：{e.response.status_code}")
```

---

## 3. 核心模块实现指南

### 3.1 AppController

`src/app/controller.py`

```python
from PyQt6.QtCore import QObject, QStateMachine, QState
from models.enums import AppState

class AppController(QObject):
    """
    主控制器，持有所有核心服务的引用。
    使用 QStateMachine 管理应用状态。
    """

    def __init__(self, config: ConfigManager):
        super().__init__()
        self.config = config
        self._init_services()
        self._init_state_machine()
        self._connect_signals()

    def _init_services(self):
        self.hotkey_manager   = HotkeyManager(self)
        self.screenshot       = ScreenshotCapture(self)
        self.recognizer       = RecognizerService(self.config, self)
        self.clipboard        = ClipboardManager()
        self.word_paste       = WordPasteService(self)
        self.history_repo     = HistoryRepository()

    def _connect_signals(self):
        self.hotkey_manager.screenshot_triggered.connect(self._on_screenshot_hotkey)
        self.hotkey_manager.paste_triggered.connect(self._on_paste_hotkey)
        self.screenshot.capture_complete.connect(self._on_capture_complete)
        self.recognizer.recognition_complete.connect(self._on_recognition_complete)
        self.recognizer.recognition_failed.connect(self._on_recognition_failed)
```

### 3.2 ScreenshotOverlay

`src/app/screenshot_overlay.py`

关键实现要点：
- 继承 `QWidget`，设置 `Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint`
- 使用 `QRubberBand` 实现框选效果
- 截图时先隐藏遮罩，调用 `QScreen.grabWindow(0)` 截全屏，再根据选区裁剪

```python
class ScreenshotOverlay(QWidget):
    capture_complete = Signal(bytes)  # PNG bytes
    capture_cancelled = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._origin = QPoint()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.capture_cancelled.emit()

    def mouseReleaseEvent(self, event):
        rect = self._rubber_band.geometry()
        if rect.width() > 5 and rect.height() > 5:
            self.hide()
            self._grab_region(rect)

    def _grab_region(self, rect: QRect):
        screen = QApplication.primaryScreen()
        pixmap = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        pixmap.save(buf, "PNG")
        self.capture_complete.emit(bytes(buf.data()))
```

### 3.3 RecognizerService

`src/core/recognizer.py`

- 使用 `QThread` + Worker 执行异步 HTTP
- System Prompt 从 `resources/prompts/recognize.txt` 加载
- 图片以 base64 data URL 方式传给 API

```python
SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "resources" / "prompts" / "recognize.txt"

class RecognitionWorker(QObject):
    finished = Signal(str)
    failed   = Signal(str)

    def __init__(self, image_bytes: bytes, config: dict):
        super().__init__()
        self._image_bytes = image_bytes
        self._config = config

    def run(self):
        import asyncio
        try:
            result = asyncio.run(self._call_api())
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))

    async def _call_api(self) -> str:
        import base64, httpx
        b64 = base64.b64encode(self._image_bytes).decode()
        system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding='utf-8')

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._config['endpoint']}/chat/completions",
                headers={"Authorization": f"Bearer {self._config['api_key']}"},
                json={
                    "model": self._config["model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": [
                            {"type": "text", "text": "识别图片内容"},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/png;base64,{b64}"
                            }}
                        ]}
                    ],
                    "max_tokens": 4096
                },
                timeout=self._config.get("timeout", 30)
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
```

### 3.4 WordPasteService

`src/core/word_paste.py`

**窗口检测：**
```python
import win32gui, win32process

def is_word_wps_active() -> tuple[bool, str]:
    """返回 (is_active, app_name)"""
    hwnd = win32gui.GetForegroundWindow()
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    import psutil
    try:
        proc_name = psutil.Process(pid).name().lower()
        if 'winword' in proc_name:
            return True, 'Word'
        if 'wps' in proc_name or 'et' in proc_name:
            return True, 'WPS'
    except psutil.NoSuchProcess:
        pass
    return False, ''
```

**Pandoc 调用：**
```python
import subprocess, tempfile, os
from pathlib import Path

class PandocConverter:
    def __init__(self, pandoc_path: str = "pandoc"):
        self.pandoc_path = pandoc_path

    def md_to_docx(self, markdown_content: str) -> Path:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.md', delete=False, encoding='utf-8'
        ) as f:
            f.write(markdown_content)
            md_path = Path(f.name)

        docx_path = md_path.with_suffix('.docx')
        result = subprocess.run(
            [self.pandoc_path, str(md_path), '-o', str(docx_path),
             '--from=markdown+tex_math_dollars',
             '--to=docx',
             '--mathml'],
            capture_output=True, text=True, timeout=30
        )
        md_path.unlink()

        if result.returncode != 0:
            raise RuntimeError(f"Pandoc failed: {result.stderr}")
        return docx_path
```

**COM 插入（参考 pastemd 实现）：**
```python
import win32com.client
import pythoncom

class WordPasteService:
    def paste(self, content: str, content_type: ContentType) -> tuple[bool, str]:
        pythoncom.CoInitialize()
        try:
            return self._do_paste(content, content_type)
        finally:
            pythoncom.CoUninitialize()

    def _get_word_app(self):
        for prog_id in ('Word.Application', 'Kwps.Application'):
            try:
                return win32com.client.GetActiveObject(prog_id)
            except Exception:
                continue
        return None

    def _do_paste(self, content: str, content_type: ContentType):
        word = self._get_word_app()
        if word is None:
            return False, "未找到 Word/WPS 实例"

        selection = word.Selection

        if content_type == ContentType.PLAIN_TEXT:
            selection.TypeText(content)
            return True, "已插入文本"

        # LaTeX 或 Markdown：通过 Pandoc 转 docx 再插入
        if content_type == ContentType.PURE_LATEX:
            md_content = f"$${content}$$"
        else:
            md_content = content

        docx_path = PandocConverter().md_to_docx(md_content)
        try:
            tmp_doc = word.Documents.Open(str(docx_path))
            tmp_doc.Content.Copy()
            selection.Paste()
            tmp_doc.Close(False)
        finally:
            docx_path.unlink(missing_ok=True)

        return True, "已插入公式"
```

### 3.5 ConfigManager

`src/utils/config.py`

```python
import json
from pathlib import Path
from typing import Any

class ConfigManager:
    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / 'config.default.json'

    def __init__(self, config_path: Path):
        self._path = config_path
        self._data: dict = {}
        self._load()

    def _load(self):
        defaults = json.loads(self.DEFAULT_CONFIG_PATH.read_text(encoding='utf-8'))
        if self._path.exists():
            user = json.loads(self._path.read_text(encoding='utf-8'))
            self._data = self._deep_merge(defaults, user)
        else:
            self._data = defaults

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        val = self._data
        for k in keys:
            if not isinstance(val, dict) or k not in val:
                return default
            val = val[k]
        return val

    def set(self, key: str, value: Any) -> None:
        keys = key.split('.')
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        self._save()

    def _save(self):
        # 不保存 api_key 到日志
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        result = base.copy()
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = ConfigManager._deep_merge(result[k], v)
            else:
                result[k] = v
        return result
```

---

## 4. 配置文件规范

### 4.1 config.default.json（纳入 git）

```json
{
  "version": "1.0.0",
  "api": {
    "endpoint": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o",
    "timeout": 30,
    "max_retries": 3
  },
  "hotkeys": {
    "screenshot": "ctrl+shift+a",
    "paste": "ctrl+shift+v"
  },
  "history": {
    "retention_days": 7,
    "max_records": 1000
  },
  "update": {
    "auto_check": true,
    "check_url": "https://api.github.com/repos/YOUR_USER/texpaste/releases/latest"
  },
  "pandoc": {
    "executable": "pandoc"
  },
  "appearance": {
    "theme": "system"
  }
}
```

### 4.2 .gitignore 必须包含

```
config.json          # 用户配置（含 API Key）
history.db           # 历史记录
*.db-wal
*.db-shm
logs/
dist/
build/
__pycache__/
.venv/
```

---

## 5. System Prompt 规范

文件：`src/resources/prompts/recognize.txt`

```
You are a precise mathematical formula and text recognition assistant.

Analyze the provided image and classify the content, then respond ONLY with the recognized content in the correct format — no explanations, no preamble.

## Output Format Rules

**Rule 1 — Pure Text:**
If the image contains ONLY plain text (no formulas), output the text as-is.
Example output: The quick brown fox jumps over the lazy dog.

**Rule 2 — Pure Formula:**
If the image contains ONLY a mathematical/chemical/physical formula, output the raw LaTeX code WITHOUT any $ delimiters.
Example output: \frac{-b \pm \sqrt{b^2-4ac}}{2a}

**Rule 3 — Mixed Content (text + formula):**
If the image contains both text and formulas, output Markdown format:
- Plain text portions: output as plain text
- Inline formulas: wrap with $...$
- Display/block formulas: wrap with $$...$$
Example output: The quadratic formula is $x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}$ where $a \neq 0$.

## Supported Formula Types
- Standard math: fractions \frac{}{}, roots \sqrt{}, integrals \int, sums \sum, limits \lim
- Superscripts/subscripts: x^{2}, a_{ij}
- Greek letters: \alpha, \beta, \gamma, \Delta, \Omega
- Matrices: \begin{pmatrix}...\end{pmatrix}, \begin{bmatrix}...\end{bmatrix}
- Multi-line equations: \begin{align}...\end{align}
- Chemical equations: use mhchem syntax \ce{2H2 + O2 -> 2H2O}
- Vectors and tensors: \vec{F}, \hat{n}, \mathbf{A}

## Important Rules
- Preserve the exact mathematical meaning; do not simplify or alter expressions
- Use standard LaTeX syntax only
- For chemical equations, always use \ce{} from the mhchem package
- If the image is unclear or unreadable, output: [UNREADABLE]
```

---

## 6. 测试规范

### 6.1 单元测试

使用 `pytest`，测试文件以 `test_` 开头，测试函数以 `test_` 开头。

```python
# tests/unit/test_content_type.py
import pytest
from core.recognizer import detect_content_type
from models.enums import ContentType

@pytest.mark.parametrize("text,expected", [
    ("Hello world", ContentType.PLAIN_TEXT),
    (r"\frac{1}{2}", ContentType.PURE_LATEX),
    ("The formula $E=mc^2$ is famous.", ContentType.MARKDOWN),
    ("$$\\int_0^1 x dx = \\frac{1}{2}$$", ContentType.MARKDOWN),
])
def test_detect_content_type(text, expected):
    assert detect_content_type(text) == expected
```

### 6.2 集成测试标记

需要外部依赖的测试用 `@pytest.mark` 标记，CI 默认跳过：

```python
@pytest.mark.integration
@pytest.mark.requires_api
def test_recognize_formula_image():
    ...

@pytest.mark.integration
@pytest.mark.requires_word
def test_paste_to_word():
    ...
```

运行方式：
```bash
# 仅单元测试
pytest tests/unit/

# 包含集成测试（需配置环境变量）
TEXPASTE_API_KEY=sk-xxx pytest tests/ -m integration
```

### 6.3 覆盖率目标

| 模块 | 目标覆盖率 |
|------|------------|
| `utils/config.py` | ≥ 90% |
| `utils/db.py` | ≥ 85% |
| `core/recognizer.py`（不含 HTTP 调用） | ≥ 80% |
| `core/word_paste.py`（不含 COM 调用） | ≥ 70% |

---

## 7. 日志规范

### 7.1 日志配置

```python
# src/utils/logger.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / 'texpaste.log',
        maxBytes=5 * 1024 * 1024,   # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger = logging.getLogger('texpaste')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger
```

### 7.2 日志规范

- **禁止**在任何日志中记录 API Key 或用户截图内容
- 关键操作需记录 INFO 日志（识别开始/完成，粘贴操作）
- 异常必须记录 ERROR 并包含 `exc_info=True`
- 日志文件存放在 `{app_data_dir}/logs/`

---

## 8. 构建与发布

### 8.1 依赖文件

**requirements.txt**（运行依赖）：
```
PyQt6>=6.4.0
pynput>=1.7.6
httpx>=0.24.0
pywin32>=305
pyperclip>=1.8.2
psutil>=5.9.0
```

**requirements-dev.txt**（开发依赖）：
```
-r requirements.txt
pytest>=7.0
pytest-qt>=4.2
pytest-asyncio>=0.21
ruff>=0.4.0
mypy>=1.8.0
pyinstaller>=6.0
```

### 8.2 构建命令

```bash
# 开发运行
python src/main.py

# 运行测试
pytest tests/unit/ -v

# 代码格式检查
ruff check src/
ruff format --check src/

# 类型检查
mypy src/utils/ src/models/ --strict

# 打包 exe
python scripts/build.py
```

### 8.3 版本规范

使用语义化版本 `MAJOR.MINOR.PATCH`：
- `MAJOR`：不兼容的 API 变更或配置格式变更
- `MINOR`：向后兼容的新功能
- `PATCH`：Bug 修复

版本号在以下位置保持同步：
- `pyproject.toml` → `[project] version`
- `config.default.json` → `version`
- Git tag: `v{version}`

---

## 9. 开发环境搭建

```bash
# 1. 克隆项目
git clone <repo-url>
cd texpaste

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements-dev.txt

# 4. 安装 Pandoc
# 从 https://pandoc.org/installing.html 下载安装，确保 pandoc 在 PATH 中

# 5. 创建用户配置
cp config.default.json config.json
# 编辑 config.json，填入 api_key 等信息

# 6. 运行
python src/main.py
```

---

## 10. 常见问题与解决方案

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 热键无响应 | pynput 被安全软件拦截 | 以管理员身份运行；提示用户添加白名单 |
| COM 接口报错 `Dispatch` | Word/WPS 未完全加载 | 重试 3 次，每次等待 500ms |
| Pandoc 命令找不到 | PATH 未包含 pandoc | `StartupChecker` 检测并提示安装路径 |
| 截图区域全黑 | DPI 缩放问题 | 使用 `QScreen.devicePixelRatio()` 校正坐标 |
| API 返回乱码 | 响应编码不是 UTF-8 | `resp.content.decode('utf-8', errors='replace')` |
| 历史记录数据库锁 | 多线程并发写入 | SQLite WAL 模式 + `check_same_thread=False` + 连接池 |
