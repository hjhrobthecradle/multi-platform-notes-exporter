# 多平台便签导出至 Joplin 工具 (Multi-Platform Notes Exporter)

一个轻量、高效的跨平台便签导出工具，支持将 **小米便签、OPPO便签、vivo便签、Apple备忘录 (iCloud)、Google Keep** 的便签内容、多级分类、待办清单及多媒体附件一键导出为标准的 Markdown + 本地资源目录，支持 1 步直接导入至 **Joplin**。

---

## 🌟 核心特性

- **多平台支持**：覆盖国内主流手机厂商（小米、OPPO、vivo）、Apple（iPhone/Mac）以及国外 Google Keep。
- **Joplin 完美兼容**：导出为标准 Markdown + YAML Frontmatter + `_resources` 附件目录结构，Joplin 可一键完整导入。
- **富文本 & 待办转换**：智能将各平台的 HTML、Delta JSON、Checklist 自动转译为标准 GitHub Flavored Markdown 语法（如 `- [ ]`、`- [x]`、加粗、斜体、引用、标题等）。
- **图片与附件本地化**：自动下载图片、录音及附件，并自动重写笔记内的引用链接为相对路径。
- **多级分类与标签保留**：保持原有文件夹层级结构与标签元数据。
- **极简运行 & 零强依赖**：内置纯 Python HTTP 会话与 HTML/Delta 解析器，无需复杂编译环境即可开箱即用。

---

## 🚀 快速开始

### 1. 运行环境准备
确保系统安装了 Python 3.8+：
```bash
python --version
```

可选安装增强依赖（如需在线提取 Google Keep 或 iCloud 2FA，或提升解析性能）：
```bash
pip install -r requirements.txt
```

### 2. 交互式运行
直接运行主程序，进入交互式菜单：
```bash
python main.py
```
终端将显示图形化菜单，可按提示选择对应平台进行导出。

### 3. 命令行参数运行
```bash
# 导出小米便签
python main.py -p xiaomi -c config.yaml

# 命令行直接传入 Cookie 导出
python main.py -p xiaomi --cookie "serviceToken=xxx; userId=yyy"

# 导出所有已配置的平台
python main.py -p all -o ./my_notes_export
```

### 4. 运行单元测试
```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## 🔑 各平台配置与 Cookie 获取指南

### 1. 小米便签 (Xiaomi Notes)
1. 电脑浏览器打开 [小米云服务 (i.mi.com)](https://i.mi.com/) 并扫码或账号登录。
2. 登录成功后，按键盘 `F12` 打开开发者工具，切换到 **网络 (Network)** 标签页。
3. 刷新页面或点击进入“便签”，在网络请求列表中任意点击一个请求（如 `profile` 或 `full/page`）。
4. 在右侧 **请求标头 (Request Headers)** 中找到 `Cookie` 字段，完整复制整串内容。
5. 粘贴到 `config.yaml` 的 `xiaomi.cookie` 中。

### 2. OPPO 便签 (HeyTap Cloud)
1. 电脑浏览器打开 [欢太云 (cloud.heytap.com)](https://cloud.heytap.com/) 并登录账号。
2. 按 `F12` 打开开发者工具 -> **网络 (Network)**。
3. 点击进入“便签”，在请求列表点击任意请求，复制 **请求标头** 中的 `Cookie` 字符串。
4. 粘贴到 `config.yaml` 的 `oppo.cookie` 中。（若已有本地导出的 HTML 文件，也可直接填写 `export_path` 路径）。

### 3. vivo 便签 (vivo Cloud)
1. 电脑浏览器打开 [vivo 云服务 (yun.vivo.com)](https://yun.vivo.com/) 并登录账号。
2. 按 `F12` 打开开发者工具 -> **网络 (Network)**。
3. 点击进入“便签”，在请求列表点击任意请求，复制 **请求标头** 中的 `Cookie` 字符串。
4. 粘贴到 `config.yaml` 的 `vivo.cookie` 中。

### 4. Apple 备忘录 (iCloud Notes)
- **在线模式**：在 `config.yaml` 中配置 `apple_id` 与 `password`。运行程序时，工具会在终端提示输入手机弹出的 6 位 2FA 验证码即可完成安全验证。
- **本地导出模式**：若开启了 iCloud 高级数据保护 (ADP) 或已通过 Mac/快捷指令导出过笔记文件夹，直接在 `apple.export_path` 中指定该本地文件夹路径即可。

### 5. Google Keep
- **方式 A (推荐免密码)**：
  1. 访问 [Google Takeout (takeout.google.com)](https://takeout.google.com/)。
  2. 仅勾选 **Keep** 并创建导出，下载解压后的文件夹。
  3. 将解压出来的文件夹路径填入 `config.yaml` 的 `google.takeout_path`。工具将自动解析所有 JSON 笔记、待办清单并关联图片音频。
- **方式 B (在线)**：
  1. 在 Google 账号管理 -> 安全性 -> 两步验证中生成一个 **应用专用密码 (App Password)**。
  2. 在 `config.yaml` 中填入 `username` 和 `password`。

---

## 📥 如何导入到 Joplin

导出完成后，导出的笔记目录结构如下：
```text
export_output/
├── xiaomi/
│   ├── _resources/
│   │   ├── mi_img_01.jpg
│   │   └── voice_note.mp3
│   ├── 工作/
│   │   └── 项目周报.md
│   └── 生活/
│       └── 待办清单.md
├── oppo/
│   ├── _resources/
│   └── 灵感备忘.md
└── ...
```

### 导入 Joplin 步骤：
1. 打开 **Joplin 桌面客户端**。
2. 点击顶部菜单栏：`文件 (File)` -> `导入 (Import)` -> `MD - Markdown (目录) / MD - Markdown (Directory)`。
3. 浏览并选中导出的平台目录（例如选择 `export_output/xiaomi` 或整个 `export_output`）。
4. **导入完成**：
   - Joplin 会自动根据文件夹层级创建对应的笔记本与子笔记本。
   - 所有笔记的标题、格式、YAML 元数据、创建时间、修改时间完全保留。
   - 所有的图片和多媒体附件均会自动转换为 Joplin 的内部资源（Resource），无需担心本地文件移动丢失。

---

## 📂 项目结构

```text
各平台便签同步/
├── main.py                     # 程序入口
├── config.yaml                 # 配置文件 (可由程序自动生成)
├── config.example.yaml         # 配置示例模版 (已脱敏)
├── requirements.txt            # Python 依赖清单
├── README.md                   # 使用文档
├── 操作手册.md                 # 详细图文指引
├── AGENTS.md                   # AI 协作与工程规范
├── .gitignore                  # Git 忽略配置
├── tests/                      # 自动化单元测试
│   └── test_core.py            # 核心模型、解析器与导出测试
└── note_exporter/
    ├── cli.py                  # 交互式 CLI 与命令行解析
    ├── config.py               # 配置加载与生成
    ├── models.py               # 统一便签/附件数据模型 (UnifiedNote)
    ├── exporter/
    │   ├── markdown_exporter.py# Markdown 文件生成与附件下载器
    │   ├── html_converter.py   # HTML/Delta 转 Markdown 引擎
    │   └── sanitizer.py        # 文件名与跨平台路径安全处理
    ├── providers/
    │   ├── base.py             # 平台基类
    │   ├── xiaomi.py           # 小米便签 Provider
    │   ├── oppo.py             # OPPO 便签 Provider
    │   ├── vivo.py             # vivo 便签 Provider
    │   ├── apple.py            # Apple 备忘录 Provider
    │   └── google.py           # Google Keep Provider
    └── utils/
        ├── http.py             # 轻量健壮 HTTP 会话
        └── logger.py           # 终端高亮日志
```
