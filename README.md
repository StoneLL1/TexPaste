# TexPaste

<p align="center">
  <img src="src/resources/icons/texpaste.ico" alt="TexPaste Logo" width="128" height="128">
</p>

<p align="center">
  <strong>Windows 桌面效率工具 — 截图识别公式，智能粘贴到 Word/WPS</strong>
</p>

<p align="center">
  <a href="#功能特性">功能特性</a> •
  <a href="#安装">安装</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#详细功能">详细功能</a> •
  <a href="#开发">开发</a>
</p>

---

## 功能特性

### 核心功能

| 快捷键 | 功能 | 说明 |
|--------|------|------|
| `Ctrl+Shift+A` | 截图识别 | 框选屏幕区域 → LLM 识别 → 自动复制到剪贴板 |
| `Ctrl+Shift+V` | 智能粘贴 | 将剪贴板内容智能粘贴到 Word/WPS（公式保持原生格式） |

### 主要特性

- **智能内容识别**：自动判断纯文本 / LaTeX 公式 / Markdown+公式混合
- **原生公式粘贴**：通过 Pandoc 转换，公式在 Word/WPS 中保持可编辑的原生格式
- **多模型支持**：兼容 OpenAI API 格式的各类模型（GPT-4o、Claude、DeepSeek、Kimi 等）
- **提示词模板**：内置 4 种预设模板，支持自定义模板（最多 10 个）
- **历史记录**：SQLite 本地存储，支持搜索，7 天自动清理
- **系统托盘**：常驻托盘，支持暂停/恢复，不干扰日常工作
- **安装程序**：一键安装，自动检测并安装 Pandoc 依赖

## 安装

### 系统要求

- Windows 10/11（64 位）
- Microsoft Word 或 WPS Office（智能粘贴功能需要）

### 下载安装

1. 前往 [Releases](https://github.com/StoneLL1/TexPaste/releases) 页面
2. 下载最新版本的 `TexPaste-Setup-x.x.x.exe`
3. 运行安装程序，按向导完成安装
4. 安装程序会自动检测并安装 Pandoc（如果系统未安装）

### 首次配置

1. 启动 TexPaste，右键托盘图标 → 设置
2. 在「API 配置」中填写：
   - **API 地址**：如 `https://api.openai.com/v1`
   - **API Key**：你的密钥
   - **模型**：如 `gpt-4o`
3. 点击「测试连接」验证配置
4. 保存设置

## 快速开始

### 基本使用流程

```
┌─────────────────────────────────────────────────────────────┐
│  1. 按 Ctrl+Shift+A                                         │
│     → 屏幕变暗，出现选区工具                                   │
│                                                             │
│  2. 框选要识别的区域                                         │
│     → 支持数学公式、表格、混合文本                              │
│                                                             │
│  3. 释放鼠标                                                 │
│     → 自动调用 LLM 识别                                       │
│     → 识别结果自动复制到剪贴板                                  │
│                                                             │
│  4. 打开 Word/WPS，按 Ctrl+Shift+V                          │
│     → 智能粘贴：公式以原生格式插入                              │
└─────────────────────────────────────────────────────────────┘
```

### 示例

| 识别内容 | 输出格式 |
|---------|---------|
| 纯文字 | Plain Text |
| 纯公式 | 裸 LaTeX（无 `$` 包裹） |
| 文字+公式 | Markdown（`$...$` 行内公式，`$$...$$` 块公式） |
| 表格 | Markdown 表格 |

## 详细功能

### 快捷键自定义

在设置 → 快捷键中可以自定义：
- 截图快捷键（默认 `Ctrl+Shift+A`）
- 粘贴快捷键（默认 `Ctrl+Shift+V`）

格式：`ctrl+shift+a`、`alt+win+s` 等

### API 配置

| 配置项 | 说明 |
|--------|------|
| API 地址 | 兼容 OpenAI 格式的 API 端点 |
| API Key | 你的 API 密钥 |
| 模型 | 模型名称，如 `gpt-4o`、`deepseek-chat` |
| 超时 | API 请求超时时间（秒） |
| 最大重试 | 失败重试次数 |

### 提示词模板

内置 4 种预设模板：
- **智能识别**：自动判断内容类型，支持表格识别
- **纯 LaTeX**：仅输出 LaTeX 公式
- **纯 Markdown**：仅输出 Markdown 格式
- **纯文本**：仅输出纯文本

支持添加最多 10 个自定义模板，可随时切换。

### 通知设置

可自定义哪些操作显示系统通知：
- 识别成功通知
- 粘贴成功通知
- 错误通知

### 历史记录

- 自动保存每次识别结果
- 支持关键词搜索
- 双击记录可复制内容
- 7 天自动清理过期记录

## 开发

### 环境搭建

```bash
# 克隆仓库
git clone https://github.com/StoneLL1/TexPaste.git
cd TexPaste

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev.txt

# 复制默认配置
cp config.default.json config.json
```

### 运行

```bash
python src/main.py
```

### 构建

```bash
# 构建 EXE
python scripts/build.py

# 构建安装程序（需要安装 Inno Setup 6）
python scripts/build_installer.py
```

### 项目结构

```
TexPaste/
├── src/
│   ├── main.py              # 入口
│   ├── app/                 # UI 层（托盘、设置、历史）
│   ├── core/                # 核心服务（识别、粘贴、热键）
│   ├── models/              # 数据模型
│   ├── utils/               # 工具类（配置、日志、数据库）
│   └── resources/           # 资源文件（图标、提示词模板）
├── scripts/                 # 构建脚本
├── installer/               # 安装程序配置
├── config.default.json      # 默认配置
└── README.md
```

## 常见问题

### Q: 粘贴时提示"未找到 Word/WPS 实例"？

A: 请确保 Word 或 WPS 已经打开，并且光标在文档中。

### Q: 公式粘贴后显示为文本而不是公式？

A: 请检查 Pandoc 是否正确安装。可以在设置中指定 Pandoc 的完整路径。

### Q: 如何使用便携模式？

A: 在 `TexPaste.exe` 同级目录创建名为 `.portable` 的空文件，数据将存储在程序目录而不是 `%APPDATA%`。

## 许可证

[MIT License](LICENSE)

## 贡献者

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/StoneLL1">
        <img src="https://github.com/StoneLL1.png?size=100" width="100px;" alt="StoneLL1"/>
        <br />
        <sub><b>StoneLL1</b></sub>
      </a>
    </td>
  </tr>
</table>

## 致谢

- [pastemd](https://github.com/euclidean-dreams/pastemd) - Word 粘贴实现参考
- [Pandoc](https://pandoc.org/) - 文档格式转换
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI 框架