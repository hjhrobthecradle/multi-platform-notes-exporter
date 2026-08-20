# Note Exporter Agent Guidelines

## 1. 项目定位
多平台便签（小米、OPPO、vivo、Apple 备忘录、Google Keep）导出至 Joplin 标准 Markdown 与资源目录的轻量 Python 工具。

## 2. 运行与测试
- **交互式运行**: `python main.py`
- **命令行运行**: `python main.py -p <xiaomi|oppo|vivo|apple|google|all> -c config.yaml`
- **运行单元测试**: `python -m unittest discover -s tests -p "test_*.py"`

## 3. 技术栈与依赖
- **核心栈**: Python 3.8+，内置轻量 HTTP 会话与 HTML/Markdown 解析器，基础功能零第三方强依赖。
- **可选依赖**: `requirements.txt`（PyYAML, requests, markdownify, gkeepapi, pyicloud）。

## 4. 目录与约定
- `main.py`: 程序入口。
- `config.yaml` / `config.example.yaml`: 配置文件与示例（严禁提交真实凭据与 Cookie）。
- `note_exporter/`:
  - `models.py`: 统一抽象模型 `UnifiedNote`, `UnifiedAttachment`, `ExportResult`。
  - `config.py`: 配置读取与回退解析。
  - `cli.py`: CLI 路由与交互式菜单。
  - `exporter/`: Markdown 生成器、HTML 解析器与文件名跨平台安全性处理。
  - `providers/`: 各平台 Provider（小米、OPPO、vivo、Apple、Google）。
  - `utils/`: 纯标准库 HTTP 请求与终端高亮日志。
- `export_output/`: 导出笔记输出根目录（按平台分文件夹并包含 `_resources/` 附件）。
- `tests/`: 单元测试目录。

## 5. 当前状态与演进
- **现役状态**: 5 大主流平台解析、附件下载、Markdown 转换与 Joplin 目录导入已全部实现。
- **下一步**: 持续增强网络异常重试、提供更多外部笔记格式（Obsidian / Notion）适配支持。
