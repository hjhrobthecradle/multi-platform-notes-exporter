import os
import sys
import argparse
from typing import List, Dict, Any

from .config import load_config, create_default_config_if_missing, DEFAULT_CONFIG_TEMPLATE
from .providers import PROVIDERS, BaseProvider
from .exporter import MarkdownExporter
from .utils.logger import Logger
from .models import ExportResult


def print_banner():
    print("""\033[1;96m
=====================================================
    多平台便签导出工具 (Multi-Platform Notes Exporter)
    支持: 小米 | OPPO | vivo | Apple | Google -> Joplin
=====================================================\033[0m""")


def print_joplin_import_guide(output_dir: str):
    Logger.header("Joplin 导入操作指南")
    abs_path = os.path.abspath(output_dir)
    print(f"""
\033[92m便签导出完成！导出目录为:\033[0m \033[1m{abs_path}\033[0m

\033[94m【导入 Joplin 步骤】:\033[0m
 1. 打开 Joplin 桌面客户端。
 2. 点击顶部菜单栏：\033[1m文件 (File)\033[0m -> \033[1m导入 (Import)\033[0m -> \033[1mMD - Markdown (目录)\033[0m。
 3. 选择上述导出的平台目录（例如：`{abs_path}`）。
 4. Joplin 将自动：
    - 按分类层级创建笔记本（如“未分类”、“练习”等）。
    - 完整保留标题、创建时间、修改时间与待办清单。
    - 自动将 `_resources/` 中的图片与附件导入为 Joplin 内部资源。
""")


def run_export_for_platform(platform_key: str, config: Dict[str, Any], output_dir: str) -> ExportResult:
    provider_cls = PROVIDERS.get(platform_key)
    if not provider_cls:
        Logger.error(f"未知平台: {platform_key}")
        return ExportResult(platform=platform_key, errors=[f"Unknown platform {platform_key}"])

    platform_config = config.get(platform_key, {})
    provider: BaseProvider = provider_cls(platform_config)

    Logger.header(f"开始处理: {provider.display_name}")

    if not provider.authenticate():
        Logger.error(f"[{provider.display_name}] 鉴权未通过，跳过导出。请检查 config.yaml 中的配置。")
        return ExportResult(platform=platform_key, errors=["Authentication failed"])

    Logger.info(f"正在拉取 [{provider.display_name}] 便签数据...")
    notes = provider.fetch_notes()
    if not notes:
        Logger.warn(f"[{provider.display_name}] 未拉取到便签或数据为空。")
        return ExportResult(platform=platform_key, total_notes=0)

    Logger.info(f"成功获取 {len(notes)} 条便签，开始转换为 Markdown 并下载附件...")
    exporter = MarkdownExporter(base_output_dir=output_dir)

    def on_progress(curr, total, note):
        if curr % 10 == 0 or curr == total:
            print(f"  -> 导出进度: [{curr}/{total}] 当前: {note.clean_title(30)}")

    result = exporter.export_notes(platform_key, notes, progress_callback=on_progress)

    Logger.success(
        f"[{provider.display_name}] 导出完成！成功: {result.exported_notes}/{result.total_notes} 篇，"
        f"附件: {result.downloaded_attachments}/{result.total_attachments} 个。"
    )
    if result.errors:
        Logger.warn(f"存在 {len(result.errors)} 个错误，可在日志中查看详情。")

    return result


def interactive_menu(config_path: str):
    print_banner()
    create_default_config_if_missing(config_path)
    config = load_config(config_path)
    output_dir = config.get("output_dir", "./export_output")

    platform_keys = ["xiaomi", "oppo", "vivo", "apple", "google"]
    
    while True:
        print("\n\033[1m请选择要导出的平台:\033[0m")
        print(" [1] 小米便签 (Xiaomi Notes)")
        print(" [2] OPPO 便签 (HeyTap Cloud)")
        print(" [3] vivo 便签 (OriginOS Cloud)")
        print(" [4] Apple 备忘录 (iCloud Notes)")
        print(" [5] Google Keep")
        print(" [6] 全部平台 (批量导出已配置的平台)")
        print(" [7] 生成/重置默认 config.yaml 模板")
        print(" [0] 退出")

        choice = input("\n请输入选项编号 [0-7]: ").strip()

        if choice == "0":
            print("退出程序。")
            break
        elif choice == "7":
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_CONFIG_TEMPLATE)
            Logger.success(f"已生成配置文件: {os.path.abspath(config_path)}")
            continue
        elif choice in ("1", "2", "3", "4", "5"):
            selected_key = platform_keys[int(choice) - 1]
            res = run_export_for_platform(selected_key, config, output_dir)
            if res.exported_notes > 0:
                print_joplin_import_guide(os.path.join(output_dir, selected_key))
        elif choice == "6":
            total_exported = 0
            for key in platform_keys:
                res = run_export_for_platform(key, config, output_dir)
                total_exported += res.exported_notes
            if total_exported > 0:
                print_joplin_import_guide(output_dir)
        else:
            Logger.warn("无效输入，请重新选择。")


def main():
    parser = argparse.ArgumentParser(description="多平台便签导出工具 (支持小米、OPPO、vivo、Apple、Google -> Joplin Markdown)")
    parser.add_argument("-p", "--platform", choices=["xiaomi", "oppo", "vivo", "apple", "google", "all"], help="指定导出平台")
    parser.add_argument("-c", "--config", default="config.yaml", help="配置文件路径 (默认: config.yaml)")
    parser.add_argument("-o", "--output", default="", help="导出输出目录")
    parser.add_argument("--cookie", default="", help="快速指定 Cookie (覆盖配置文件)")
    
    args = parser.parse_args()

    create_default_config_if_missing(args.config)
    config = load_config(args.config)

    output_dir = args.output or config.get("output_dir", "./export_output")

    if not args.platform:
        interactive_menu(args.config)
        return

    print_banner()

    if args.platform == "all":
        for key in ["xiaomi", "oppo", "vivo", "apple", "google"]:
            run_export_for_platform(key, config, output_dir)
        print_joplin_import_guide(output_dir)
    else:
        if args.cookie:
            if args.platform not in config:
                config[args.platform] = {}
            config[args.platform]["cookie"] = args.cookie

        res = run_export_for_platform(args.platform, config, output_dir)
        if res.exported_notes > 0:
            print_joplin_import_guide(os.path.join(output_dir, args.platform))


if __name__ == "__main__":
    main()
