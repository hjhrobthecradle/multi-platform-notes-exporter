import json
import glob
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base import BaseProvider
from ..models import UnifiedNote, UnifiedAttachment
from ..utils.http import SimpleHttpSession
from ..utils.logger import Logger
from ..exporter.html_converter import html_to_markdown


class OppoNotesProvider(BaseProvider):
    name = "oppo"
    display_name = "OPPO 便签 (HeyTap Cloud)"

    BASE_URL = "https://cloud.heytap.com"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.session = SimpleHttpSession()
        self.cookie_str = self.config.get("cookie", "")
        self.export_path = self.config.get("export_path", "")
        self.categories_map: Dict[str, str] = {}

    def authenticate(self) -> bool:
        if self.export_path and os.path.exists(self.export_path):
            Logger.info(f"使用本地 OPPO 便签导出目录: {self.export_path}")
            return True

        if self.cookie_str:
            self.session.set_cookie_string(self.cookie_str)

        if not self.session.cookies:
            Logger.error("OPPO 便签需要配置 Cookie 或配置本地 'export_path' 目录。")
            Logger.info("获取方法：在浏览器登录 cloud.heytap.com -> F12 网络请求中复制 Cookie。")
            return False

        self.session.headers.update({
            "Referer": "https://cloud.heytap.com/",
            "Origin": "https://cloud.heytap.com",
            "Accept": "application/json, text/plain, */*"
        })

        Logger.info("正在验证 OPPO 云服务登录状态...")
        try:
            resp = self.session.get(f"{self.BASE_URL}/notes/v1/categories")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") in (200, 0, "200", "0") or "data" in data:
                    Logger.success("OPPO 云服务验证成功！")
                    return True
        except Exception:
            pass

        # Try user profile or note list check
        try:
            resp = self.session.get(f"{self.BASE_URL}/notes/v1/list", params={"pageSize": 5, "pageNum": 1})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") in (200, 0, "200", "0") or "data" in data:
                    Logger.success("OPPO 云服务连接成功！")
                    return True
        except Exception:
            pass

        Logger.warn("OPPO Cookie 验证未完全通过，但将尝试继续拉取（若失败请更新 Cookie）。")
        return True

    def fetch_notes(self) -> List[UnifiedNote]:
        if self.export_path and os.path.exists(self.export_path):
            return self._fetch_from_local_export()
        return self._fetch_from_api()

    def _fetch_from_local_export(self) -> List[UnifiedNote]:
        """Parses local OPPO export files (HTML/JSON/TXT)."""
        html_files = glob.glob(os.path.join(self.export_path, "**", "*.html"), recursive=True)
        txt_files = glob.glob(os.path.join(self.export_path, "**", "*.txt"), recursive=True)
        all_files = html_files + txt_files
        Logger.info(f"在本地 OPPO 导出目录中发现 {len(all_files)} 个笔记文件。")

        notes = []
        for file_path in all_files:
            try:
                rel_path = os.path.relpath(file_path, self.export_path)
                folder = os.path.dirname(rel_path) or "Default"
                stem, ext = os.path.splitext(os.path.basename(file_path))

                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                content_md = html_to_markdown(content) if ext.lower() == ".html" else content
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                notes.append(
                    UnifiedNote(
                        id=stem,
                        source_platform="oppo",
                        title=stem,
                        content_raw=content,
                        content_markdown=content_md,
                        folder=folder,
                        updated_at=mtime
                    )
                )
            except Exception as e:
                Logger.warn(f"解析 OPPO 本地文件 {file_path} 失败: {e}")

        return notes

    def _fetch_from_api(self) -> List[UnifiedNote]:
        notes: List[UnifiedNote] = []
        page_num = 1
        page_size = 50

        Logger.info("正在从 OPPO 云服务拉取便签...")
        while True:
            try:
                resp = self.session.get(
                    f"{self.BASE_URL}/notes/v1/list",
                    params={"pageNum": page_num, "pageSize": page_size}
                )
                if resp.status_code != 200:
                    Logger.error(f"拉取 OPPO 便签第 {page_num} 页失败: HTTP {resp.status_code}")
                    break

                data = resp.json()
                note_list = data.get("data", {}).get("list", []) or data.get("data", {}).get("entries", [])
                if not note_list and isinstance(data.get("data"), list):
                    note_list = data.get("data")

                if not note_list:
                    break

                Logger.info(f"第 {page_num} 页获取到 {len(note_list)} 条便签...")
                for item in note_list:
                    unified_note = self._parse_oppo_note(item)
                    if unified_note:
                        notes.append(unified_note)

                total = data.get("data", {}).get("total", 0)
                if len(notes) >= total or len(note_list) < page_size:
                    break

                page_num += 1
            except Exception as e:
                Logger.error(f"拉取 OPPO 便签异常: {e}")
                break

        Logger.success(f"共获取到 {len(notes)} 条 OPPO 便签。")
        return notes

    def _parse_oppo_note(self, item: Dict[str, Any]) -> Optional[UnifiedNote]:
        note_id = str(item.get("noteId") or item.get("id") or "")
        if not note_id:
            return None

        title = item.get("title", "") or item.get("subject", "")
        raw_content = item.get("content", "") or item.get("body", "") or ""
        folder = item.get("categoryName") or item.get("folderName") or "Default"

        created_ts = item.get("createTime") or item.get("createDate")
        created_at = datetime.fromtimestamp(created_ts / 1000) if created_ts else None

        updated_ts = item.get("updateTime") or item.get("modifyDate")
        updated_at = datetime.fromtimestamp(updated_ts / 1000) if updated_ts else None

        # Format markdown
        content_md = html_to_markdown(raw_content) if "<" in raw_content else raw_content

        # Attachments / images
        attachments: List[UnifiedAttachment] = []
        img_list = item.get("images", []) or item.get("attachments", [])
        for idx, img in enumerate(img_list):
            if isinstance(img, str):
                img_url = img
                img_id = f"{note_id}_img_{idx}"
            elif isinstance(img, dict):
                img_url = img.get("url") or img.get("src", "")
                img_id = str(img.get("id") or f"{note_id}_img_{idx}")
            else:
                continue

            if img_url:
                attachments.append(
                    UnifiedAttachment(
                        id=img_id,
                        filename=f"oppo_{img_id}.jpg",
                        url=img_url,
                        cookies=dict(self.session.cookies)
                    )
                )

        return UnifiedNote(
            id=note_id,
            source_platform="oppo",
            title=title,
            content_raw=raw_content,
            content_markdown=content_md,
            folder=folder,
            created_at=created_at,
            updated_at=updated_at,
            attachments=attachments,
            extra_metadata=item
        )
