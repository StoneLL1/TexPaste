# TexPaste

Windows 桌面效率工具 — 截图识别数学公式，智能粘贴到 Word/WPS。

## 功能

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Shift+A` | 框选截图 → LLM 识别 → 自动复制结果到剪贴板 |
| `Ctrl+Shift+V` | 读取剪贴板内容 → 智能粘贴到 Word/WPS（公式保持原生格式） |

- **自动识别内容类型**：纯文字 / 纯 LaTeX 公式 / Markdown+公式混合
- **兼容 OpenAI API 格式**的各类模型（GPT-4o、Claude、DeepSeek、Kimi 等）
- **历史记录**：SQLite 存储，7 天自动清理，支持搜索
- **托盘常驻**，支持暂停/恢复
- **便携模式**：在 exe 同级目录创建 `.portable` 文件即可将数据存在本地

## 系统要求

- Windows 10/11
- [Pandoc](https://pandoc.org/installing.html) (Word/WPS 粘贴功能需要)
- Microsoft Word 或 WPS Office（智能粘贴功能需要）

## 开发环境搭建

```bash
# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements-dev.txt

# 复制默认配置
cp config.default.json config.json
# 编辑 config.json，填入 api_key 等

# 运行
python src/main.py
```

## 配置

配置文件：`config.json`（首次运行自动从 `config.default.json` 生成）

```json
{
  "api": {
    "endpoint": "https://api.openai.com/v1",
    "api_key": "sk-...",
    "model": "gpt-4o",
    "timeout": 30,
    "max_retries": 3
  },
  "hotkeys": {
    "screenshot": "ctrl+shift+a",
    "paste": "ctrl+shift+v"
  }
}
```

## 构建 exe

```bash
python scripts/build.py
# 输出：dist/TexPaste.exe
```

## 文档

- [`docs/prd.md`](docs/prd.md) — 产品需求文档
- [`docs/architecture.md`](docs/architecture.md) — 技术架构
- [`docs/dev-spec.md`](docs/dev-spec.md) — 开发规范
