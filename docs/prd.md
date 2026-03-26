# TexPaste - Windows 桌面端公式识别与智能粘贴工具 PRD

## 1. Executive Summary

### 1.1 Problem Statement
学术工作者在阅读论文、教材时，遇到数学公式需要手动输入到 Word/WPS 文档中，现有 OCR 工具无法准确识别公式，且识别后的 LaTeX 代码无法直接粘贴到 Word 使用，效率极低。

### 1.2 Proposed Solution
开发 TexPaste —— 一款 Windows 桌面端工具，通过快捷键截图调用大模型 API 智能识别公式/文本，自动转换为 Word 可编辑的公式格式并智能粘贴，实现"所见即所得"的公式录入体验。

### 1.3 Success Criteria
| KPI | 目标值 |
|-----|--------|
| 公式识别准确率 | ≥ 95%（标准数学公式） |
| 端到端响应时间 | ≤ 5 秒（从截图到剪贴板） |
| 用户满意度 | CSAT ≥ 4.5/5.0 |
| 日活用户留存率 | ≥ 60%（30天） |

---

## 2. User Experience & Functionality

### 2.1 User Personas

**主要用户：学术研究者**
- 年龄：22-45岁
- 场景：撰写论文、整理笔记、制作课件
- 痛点：手动输入公式耗时，LaTeX 代码无法直接粘贴
- 技术水平：中等，熟悉基本快捷键操作

### 2.2 User Stories

#### US-001: 后台常驻与托盘管理
```
As a 用户，I want 程序以托盘图标形式静默运行，
So that 不占用任务栏空间，随时可用。
```
**Acceptance Criteria:**
- [ ] 程序启动后仅在系统托盘显示图标
- [ ] 右键托盘图标显示菜单：设置、暂停/恢复、退出
- [ ] 托盘图标显示当前状态（运行中/暂停/错误）


#### US-002: 快捷键截图
```
As a 用户，I want 通过自定义快捷键快速截图，
So that 无需切换窗口即可捕获屏幕内容。
```
**Acceptance Criteria:**
- [ ] 默认快捷键：Ctrl+Shift+A（可自定义）
- [ ] 快捷键触发后进入区域截图模式
- [ ] 支持鼠标框选任意矩形区域
- [ ] ESC 键取消截图

#### US-003: 智能识别
```
As a 用户，I want 截图后自动识别内容类型并输出正确格式，
So that 无需手动判断和处理。
```
**Acceptance Criteria:**
- [ ] 截图完成后立即发送到 API（需确认）
- [ ] 大模型自动判断内容类型：
  - 纯文字 → 输出 Plain Text
  - 纯公式 → 输出原始 LaTeX（无 `$` 包裹）
  - 混合内容 → 输出 Markdown（公式用 `$...$` 或 `$$...$$` 包裹）
- [ ] 支持识别以下公式类型：
  - 基础数学公式（上下标、分式、根号、积分、求和等）
  - 矩阵/多行公式（matrix、align 环境）
  - 化学方程式（mhchem 宏包语法）
  - 物理符号（向量、张量等）
- [ ] 识别结果自动复制到剪贴板（纯文本格式）
- [ ] 识别过程中托盘图标显示加载状态
- [ ] 识别失败时弹出系统通知显示错误信息

#### US-004: Word/WPS 智能粘贴
```
As a 用户，I want 在 Word/WPS 中快捷粘贴时自动转换为可编辑公式，
So that 无需手动转换格式。
```
**Acceptance Criteria:**
- [ ] 默认快捷键：Ctrl+Shift+V（可自定义）
- [ ] 仅在 Word/WPS 窗口激活时有效
- [ ] 非Word/WPS窗口按下快捷键时，显示系统通知提示
- [ ] 读取剪贴板内容，调用 Pandoc 转换为 DOCX 格式
- [ ] 通过 COM 接口插入到当前光标位置
- [ ] 公式以 OMML 格式插入（Word 原生公式格式）
- [ ] 普通文本保持原格式插入

#### US-005: API 配置管理
```
As a 用户，I want 自定义配置大模型 API，
So that 可使用不同服务商的模型。
```
**Acceptance Criteria:**
- [ ] 支持配置项：
  - API Endpoint URL
  - API Key
  - 模型名称
  - 请求超时时间（默认 30s）
  - 最大重试次数（默认 3）
- [ ] API Key 输入框使用密码遮罩
- [ ] 支持测试连接按钮验证配置
- [ ] 配置保存到本地 JSON 文件（便携式）
- [ ] 预设常用服务商模板：OpenAI、Claude、DeepSeek、kimi 等

#### US-006: 快捷键自定义
```
As a 用户，I want 自定义截图和粘贴的快捷键，
So that 适应个人使用习惯。
```
**Acceptance Criteria:**
- [ ] 支持修改快捷键：截图、智能粘贴
- [ ] 快捷键输入框支持按键录制
- [ ] 检测快捷键冲突并提示
- [ ] 保存后立即生效

#### US-007: 历史记录管理
```
As a 用户，I want 查看历史识别记录，
So that 回溯和复用之前的识别结果。
```
**Acceptance Criteria:**
- [ ] 托盘菜单入口：查看历史记录
- [ ] 历史记录包含：时间戳、截图缩略图、识别结果
- [ ] 点击记录可复制识别结果到剪贴板
- [ ] 支持搜索历史记录
- [ ] 自动清理超过 7 天的记录
- [ ] 历史记录存储在本地 SQLite 数据库

#### US-008: 自动更新
```
As a 用户，I want 软件自动检查更新，
So that 及时获得新功能和 bug 修复。
```
**Acceptance Criteria:**
- [ ] 启动时自动检查更新（可关闭）
- [ ] 发现新版本时弹出系统通知
- [ ] 提供下载链接跳转
- [ ] 支持手动检查更新（托盘菜单）

### 2.3 Non-Goals

**本期不包含：**
- 多显示器跨屏截图
- 离线/本地模型支持
- 批量图片识别
- 云端同步配置
- Mac/Linux 平台支持
- 图片编辑/标注功能
- OCR 文字识别（仅由大模型完成）

---

## 3. AI System Requirements

### 3.1 Tool Requirements

| 组件 | 说明 |
|------|------|
| 大模型 API | 兼容 OpenAI API 格式的 Vision 模型 |
| Pandoc | Markdown/LaTeX → DOCX 转换 |
| 系统依赖 | Windows 10/11, .NET (可选) |

### 3.2 Prompt Engineering

**System Prompt 设计：**
```
You are a mathematical formula and text recognition assistant.
Analyze the image and determine the content type, then output in the appropriate format:

1. Pure Text: Output plain text only, no special formatting.
2. Pure Formula: Output raw LaTeX code without $ delimiters.
3. Mixed Content: Output Markdown format with formulas wrapped in $...$ or $$...$$

Supported formula types:
- Standard math (fractions, roots, integrals, sums, limits)
- Matrices and multi-line equations (matrix, align, cases environments)
- Chemical equations (use mhchem \ce{} syntax)
- Physics notation (vectors, tensors, Greek letters)

Rules:
- Preserve original formatting and structure
- Use standard LaTeX syntax
- For chemical equations, use \ce{...} from mhchem package
```

### 3.3 Evaluation Strategy

| 测试场景 | 测试用例数 | 通过标准 |
|----------|------------|----------|
| 基础数学公式 | 50 | 准确率 ≥ 95% |
| 矩阵/多行公式 | 20 | 准确率 ≥ 90% |
| 化学方程式 | 20 | 准确率 ≥ 90% |
| 混合内容 | 30 | 准确率 ≥ 85% |
| 边缘情况 | 20 | 无崩溃，优雅降级 |

---

## 4. Technical Specifications

### 4.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        TexPaste Application                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Tray Icon  │  │   Settings  │  │    History Manager      │  │
│  │   Manager   │  │     UI      │  │   (SQLite Storage)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         │                │                      │                │
│         ▼                ▼                      ▼                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Core Services Layer                      ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  ││
│  │  │  Hotkey     │  │  Screenshot │  │   Clipboard         │  ││
│  │  │  Manager    │  │   Capture   │  │   Manager           │  ││
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  ││
│  │         │               │                      │           ││
│  │         ▼               ▼                      ▼           ││
│  │  ┌─────────────────────────────────────────────────────┐  ││
│  │  │              Recognition Service                    │  ││
│  │  │  (Vision API Client + Content Type Classifier)     │  ││
│  │  └─────────────────────────────────────────────────────┘  ││
│  │                          │                                ││
│  │                          ▼                                ││
│  │  ┌─────────────────────────────────────────────────────┐  ││
│  │  │            Word Paste Service                       │  ││
│  │  │  (Pandoc Converter + COM Interface Handler)         │  ││
│  │  └─────────────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │       External Services       │
              │  ┌─────────┐    ┌─────────┐   │
              │  │ LLM API │    │ Pandoc  │   │
              │  └─────────┘    └─────────┘   │
              └───────────────────────────────┘
```

### 4.2 Technology Stack

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| GUI 框架 | PyQt6 | 跨平台、成熟稳定 |
| 系统托盘 | QSystemTrayIcon | 原生托盘支持 |
| 截图 | PyQt6 + QScreen | 原生截图能力 |
| 全局热键 | pynput / keyboard | 全局快捷键监听 |
| HTTP 客户端 | httpx / requests | 异步 API 调用 |
| 剪贴板 | pyperclip + win32clipboard | 跨格式剪贴板操作 |
| Word 自动化 | pywin32 (COM) | Word/WPS COM 接口 |
| 格式转换 | Pandoc CLI | Markdown → DOCX |
| 数据存储 | SQLite | 历史记录本地存储 |
| 配置管理 | JSON | 便携式配置文件 |
| 打包工具 | PyInstaller / Nuitka | 单文件 exe |

### 4.3 Directory Structure

```
texpaste/
├── src/
│   ├── main.py                 # 程序入口
│   ├── app/
│   │   ├── __init__.py
│   │   ├── tray.py             # 托盘图标管理
│   │   ├── settings.py         # 设置窗口 UI
│   │   └── history.py          # 历史记录窗口 UI
│   ├── core/
│   │   ├── __init__.py
│   │   ├── hotkey.py           # 快捷键管理器
│   │   ├── screenshot.py       # 截图功能
│   │   ├── clipboard.py        # 剪贴板管理
│   │   ├── recognizer.py       # 大模型识别服务
│   │   └── word_paste.py       # Word 粘贴服务
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py           # 配置文件管理
│   │   ├── logger.py           # 日志工具
│   │   └── updater.py          # 自动更新检查
│   ├── models/
│   │   ├── __init__.py
│   │   └── history.py          # 历史记录数据模型
│   └── resources/
│       ├── icons/              # 托盘图标资源
│       ├── prompts/            # Prompt 模板
│       └── templates/          # 预设模板
├── config.json                 # 配置文件
├── history.db                  # SQLite 历史记录
├── requirements.txt
├── pyproject.toml
└── README.md
```

### 4.4 Configuration Schema

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
    "screenshot": "Ctrl+Shift+A",
    "paste": "Ctrl+Shift+V"
  },
  "history": {
    "retention_days": 7,
    "max_records": 1000
  },
  "update": {
    "auto_check": true,
    "check_url": "https://api.github.com/repos/xxx/texpaste/releases/latest"
  },
  "appearance": {
    "theme": "system"
  }
}
```

### 4.5 API Integration

**OpenAI API 调用示例：**
```python
import httpx

async def recognize_image(image_base64: str, config: dict) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config['endpoint']}/chat/completions",
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": config["model"],
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": "识别图片中的内容"},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }}
                    ]}
                ],
                "max_tokens": 4096
            },
            timeout=config["timeout"]
        )
    return response.json()["choices"][0]["message"]["content"]
```

### 4.6 Word/WPS Integration

**COM 接口实现方案：**

```python
import win32com.client
import subprocess
import tempfile
import os

class WordPasteService:
    def __init__(self):
        self.word_app = None

    def get_active_word(self):
        """获取当前激活的 Word/WPS 应用"""
        try:
            # 尝试连接已运行的 Word
            self.word_app = win32com.client.GetActiveObject("Word.Application")
            return self.word_app
        except:
            # 尝试 WPS
            try:
                self.word_app = win32com.client.GetActiveObject("Kwps.Application")
                return self.word_app
            except:
                return None

    def paste_to_word(self, content: str, content_type: str):
        """智能粘贴到 Word"""
        word = self.get_active_word()
        if not word:
            return False, "未检测到 Word/WPS 窗口"

        selection = word.Selection

        if content_type == "latex":
            # 转换并插入公式
            docx_path = self._convert_latex_to_docx(content)
            self._insert_docx_content(word, docx_path, selection)
        else:
            # 插入纯文本
            selection.TypeText(content)

        return True, "粘贴成功"

    def _convert_latex_to_docx(self, latex: str) -> str:
        """使用 Pandoc 将 LaTeX 转换为 DOCX"""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.md', delete=False, encoding='utf-8'
        ) as f:
            f.write(f"$${latex}$$")

        output_path = f.name.replace('.md', '.docx')
        subprocess.run([
            'pandoc', f.name,
            '-o', output_path,
            '--from=markdown',
            '--to=docx'
        ], check=True)

        os.unlink(f.name)
        return output_path

    def _insert_docx_content(self, word, docx_path: str, selection):
        """插入 DOCX 内容到光标位置"""
        temp_doc = word.Documents.Open(docx_path)
        temp_doc.Content.Copy()
        selection.Paste()
        temp_doc.Close(False)
        os.unlink(docx_path)
```

### 4.7 Security & Privacy

| 安全项 | 措施 |
|--------|------|
| API Key 存储 | 本地加密存储，不传输到任何第三方 |
| 截图数据 | 仅发送到用户配置的 API 端点，不本地留存（除历史记录缩略图） |
| 历史记录 | 本地 SQLite 加密存储 |
| 网络传输 | 仅 HTTPS 加密传输 |

---

## 5. Risks & Roadmap

### 5.1 Technical Risks

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 大模型 API 不稳定 | 识别失败 | 重试机制 + 本地缓存 + 错误提示 |
| Pandoc 未安装 | 粘贴失败 | 启动时检测，引导安装 |
| Word/WPS 版本兼容 | COM 接口异常 | 支持多版本降级处理 |
| 快捷键冲突 | 功能失效 | 冲突检测 + 提示修改 |
| 公式识别准确率 | 用户体验差 | Prompt 优化 + 模型选择建议 |

### 5.2 Phased Rollout

**Phase 1: MVP (v1.0)**
- 核心截图识别功能
- 基础 Word 粘贴
- API 配置
- 托盘图标

**Phase 2: Enhancement (v1.1)**
- 历史记录管理
- 快捷键自定义
- WPS 完整支持
- 错误处理优化

**Phase 3: Polish (v1.2)**
- 自动更新
- 性能优化
- UI 美化
- 更多预设模板

### 5.3 Dependencies

| 依赖 | 版本 | 用途 | 安装方式 |
|------|------|------|----------|
| PyQt6 | ≥6.4 | GUI 框架 | pip |
| pynput | ≥1.7 | 全局热键 | pip |
| httpx | ≥0.24 | HTTP 客户端 | pip |
| pywin32 | ≥305 | COM 接口 | pip |
| pyperclip | ≥1.8 | 剪贴板 | pip |
| Pandoc | ≥3.0 | 格式转换 | 独立安装 |

---

## 6. Verification

### 6.1 Testing Checklist

**功能测试：**
- [ ] 托盘图标正常显示和交互
- [ ] 快捷键触发截图功能
- [ ] 区域截图框选正常
- [ ] API 调用成功返回结果
- [ ] 纯文本识别正确
- [ ] 纯公式识别正确（无 `$` 包裹）
- [ ] 混合内容识别正确（Markdown 格式）
- [ ] 剪贴板内容正确
- [ ] Word 中智能粘贴成功
- [ ] WPS 中智能粘贴成功
- [ ] 非 Word/WPS 窗口提示正确
- [ ] 配置保存和读取正确
- [ ] 历史记录功能正常
- [ ] 自动更新检查正常

**边界测试：**
- [ ] API 超时处理
- [ ] API Key 错误提示
- [ ] 网络断开处理
- [ ] 无选中区域取消截图
- [ ] 空剪贴板粘贴提示
- [ ] Word 未打开文档提示

**性能测试：**
- [ ] 冷启动时间 < 3s
- [ ] 热启动时间 < 1s
- [ ] 截图响应时间 < 500ms
- [ ] API 调用时间 < 5s (P95)

### 6.2 User Acceptance Test

**测试场景 1：识别论文公式**
1. 打开一篇 PDF 论文
2. 按 Ctrl+Shift+A 截取一个复杂公式
3. 验证：剪贴板中的 LaTeX 代码正确
4. 打开 Word，按 Ctrl+Shift+V
5. 验证：公式正确插入且可编辑

**测试场景 2：识别混合内容**
1. 截取包含文字和公式的段落
2. 验证：输出为 Markdown 格式
3. 粘贴到 Word
4. 验证：文字和公式都正确渲染

**测试场景 3：历史记录**
1. 完成多次识别
2. 打开历史记录窗口
3. 验证：历史记录显示正确
4. 点击历史记录
5. 验证：内容复制到剪贴板

---

## 7. Appendix

### 7.1 Reference Projects

- **pastemd**: Markdown 转 Word 粘贴工具实现参考
  - GitHub: https://github.com/euclidean-dreams/pastemd
  - 核心思路：Pandoc 转换 + COM 接口插入

### 7.2 Glossary

| 术语 | 说明 |
|------|------|
| LaTeX | 科学排版语言，用于数学公式 |
| OMML | Office Math Markup Language，Word 公式格式 |
| MathML | 数学标记语言 |
| COM | Component Object Model，Windows 组件接口 |
| Vision API | 支持图像输入的大模型 API |

### 7.3 Formula Examples

**测试用公式集：**

```latex
% 基础公式
E = mc^2
\frac{-b \pm \sqrt{b^2-4ac}}{2a}
\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}

% 矩阵
\begin{pmatrix}
a & b \\
c & d
\end{pmatrix}

% 多行公式
\begin{align}
f(x) &= x^2 + 2x + 1 \\
     &= (x+1)^2
\end{align}

% 化学方程式
\ce{2H2 + O2 -> 2H2O}
\ce{CO2 + C -> 2CO}

% 物理符号
\vec{F} = m\vec{a}
\nabla \times \vec{E} = -\frac{\partial \vec{B}}{\partial t}
```

---

**Document Version:** 1.0
**Created:** 2026-03-26
**Status:** Ready for Development