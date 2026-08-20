import os
import glob
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base import BaseProvider
from ..models import UnifiedNote, UnifiedAttachment
from ..utils.logger import Logger
from ..exporter.html_converter import html_to_markdown


class AppleNotesProvider(BaseProvider):
    name = "apple"
    display_name = "Apple 备忘录 (iCloud Notes)"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.apple_id = self.config.get("apple_id", "")
        self.password = self.config.get("password", "")
        self.export_path = self.config.get("export_path", "")
        self.api = None

    def authenticate(self) -> bool:
        if self.export_path and os.path.exists(self.export_path):
            Logger.info(f"使用本地 Apple Notes 导出目录: {self.export_path}")
            return True

        if not self.apple_id or not self.password:
            Logger.error("Apple 备忘录需要配置 'apple_id' 和 'password' 或配置 'export_path' 本地目录。")
            return False

        try:
            from pyicloud import PyiCloudService
            Logger.info(f"正在登录 iCloud: {self.apple_id}...")
            self.api = PyiCloudService(self.apple_id, self.password)

            if self.api.requires_2fa:
                Logger.warn("iCloud 需要双重认证 (2FA)！")
                code = input("请输入您受信任设备收到的 6 位验证码: ").strip()
                result = self.api.validate_2fa_code(code)
                if not result:
                    Logger.error("2FA 验证码错误或过期。")
                    return False
                Logger.success("iCloud 2FA 验证成功！")
            elif self.api.requires_2sa:
                Logger.warn("iCloud 需要两步验证 (2SA)！")
                devices = self.api.trusted_devices
                for i, device in enumerate(devices):
                    print(f"  [{i}] {device.get('deviceName', 'SMS')} ({device.get('phoneNumber', '')})")
                device_idx = int(input("请选择发送验证码的设备编号: ") or "0")
                device = devices[device_idx]
                if not self.api.send_verification_code(device):
                    Logger.error("发送验证码失败。")
                    return False
                code = input("请输入接收到的验证码: ").strip()
                if not self.api.validate_verification_code(device, code):
                    Logger.error("验证码验证失败。")
                    return False
                Logger.success("iCloud 验证成功！")

            return True
        except ImportError:
            Logger.error("未找到 pyicloud 库。可通过 'pip install pyicloud' 安装，或使用 'export_path' 模式。")
            return False
        except Exception as e:
            Logger.error(f"iCloud 登录失败: {e}")
            return False

    def fetch_notes(self) -> List[UnifiedNote]:
        if self.export_path and os.path.exists(self.export_path):
            return self._fetch_from_local_export()
        elif self.api:
            return self._fetch_from_icloud_api()
        return []

    def _fetch_from_local_export(self) -> List[UnifiedNote]:
        """Parses locally exported Apple Notes (HTML or Markdown or text files)."""
        html_files = glob.glob(os.path.join(self.export_path, "**", "*.html"), recursive=True)
        txt_files = glob.glob(os.path.join(self.export_path, "**", "*.txt"), recursive=True)
        md_files = glob.glob(os.path.join(self.export_path, "**", "*.md"), recursive=True)
        
        all_files = list(set(html_files + txt_files + md_files))
        Logger.info(f"在本地 Apple 导出目录中发现 {len(all_files)} 个笔记文件。")
        
        notes = []
        for file_path in all_files:
            try:
                rel_path = os.path.relpath(file_path, self.export_path)
                folder = os.path.dirname(rel_path) or "Default"
                stem, ext = os.path.splitext(os.path.basename(file_path))
                
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                if ext.lower() == ".html":
                    content_md = html_to_markdown(content)
                else:
                    content_md = content

                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                ctime = datetime.fromtimestamp(os.path.getctime(file_path))

                notes.append(
                    UnifiedNote(
                        id=stem,
                        source_platform="apple",
                        title=stem,
                        content_raw=content,
                        content_markdown=content_md,
                        folder=folder,
                        created_at=ctime,
                        updated_at=mtime
                    )
                )
            except Exception as e:
                Logger.warn(f"解析本地笔记文件 {file_path} 失败: {e}")

        return notes

    def _fetch_from_icloud_api(self) -> List[UnifiedNote]:
        """Fetches notes from iCloud service."""
        notes = []
        try:
            # iCloud notes service
            icloud_notes = getattr(self.api, "notes", None)
            if not icloud_notes:
                Logger.warn("当前 iCloud 账号暂无法通过 Web API 直接读取 Notes（可能开启了高级数据保护 ADP）。")
                return []

            for note_item in icloud_notes:
                try:
                    title = getattr(note_item, "title", "") or ""
                    body = getattr(note_item, "body", "") or ""
                    content_md = html_to_markdown(body) if body else ""
                    created_at = getattr(note_item, "date_created", None)
                    updated_at = getattr(note_item, "date_modified", None)
                    folder = getattr(note_item, "folder", "Default") or "Default"

                    notes.append(
                        UnifiedNote(
                            id=str(getattr(note_item, "id", title)),
                            source_platform="apple",
                            title=title,
                            content_raw=body,
                            content_markdown=content_md,
                            folder=str(folder),
                            created_at=created_at,
                            updated_at=updated_at
                        )
                    )
                except Exception as ne:
                    Logger.warn(f"解析单个 iCloud 笔记失败: {ne}")

            Logger.success(f"从 iCloud 成功拉取 {len(notes)} 条备忘录。")
        except Exception as e:
            Logger.error(f"拉取 iCloud 备忘录失败: {e}")

        return notes
