import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base import BaseProvider
from ..models import UnifiedNote, UnifiedAttachment
from ..utils.http import SimpleHttpSession
from ..utils.logger import Logger
from ..exporter.html_converter import html_to_markdown


class XiaomiNotesProvider(BaseProvider):
    name = "xiaomi"
    display_name = "小米便签 (Xiaomi Notes)"

    BASE_URL = "https://i.mi.com"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.session = SimpleHttpSession()
        self.cookie_str = self.config.get("cookie", "")
        self.service_token = self.config.get("service_token", "")
        self.user_id = self.config.get("user_id", "")
        self.folders_map: Dict[str, str] = {}

    def authenticate(self) -> bool:
        if self.cookie_str:
            self.session.set_cookie_string(self.cookie_str)
        if self.service_token:
            self.session.cookies["serviceToken"] = self.service_token
        if self.user_id:
            self.session.cookies["userId"] = str(self.user_id)

        if not self.session.cookies.get("serviceToken") and not self.cookie_str:
            Logger.error("小米便签需要配置 Cookie 或 (service_token + user_id)。")
            Logger.info("获取方法：在浏览器登录 i.mi.com -> F12 网络请求中复制 Cookie。")
            return False

        Logger.info("正在验证小米云服务登录状态...")
        resp = self.session.get(f"{self.BASE_URL}/status/lite/profile")
        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("result") == "ok" or data.get("code") == 0:
                    user_info = data.get("data", {})
                    Logger.success(f"小米账号验证成功！用户: {user_info.get('userId', 'Mi User')}")
                    return True
            except Exception:
                pass

        # Sometimes /status/lite/profile might fail but /note/folder/ works
        folder_resp = self.session.get(f"{self.BASE_URL}/note/folder/")
        if folder_resp.status_code == 200:
            try:
                data = folder_resp.json()
                if "data" in data or "entries" in data or data.get("result") == "ok":
                    Logger.success("小米便签接口连接成功！")
                    return True
            except Exception:
                pass

        Logger.error("小米账号 Cookie 已失效或无效，请重新在 i.mi.com 登录并获取 Cookie。")
        return False

    def _fetch_folders(self):
        """Fetches folder list to map folderId to folder name."""
        try:
            resp = self.session.get(f"{self.BASE_URL}/note/folder/")
            if resp.status_code == 200:
                data = resp.json()
                entries = data.get("data", {}).get("folders", []) or data.get("data", {}).get("entries", [])
                for f in entries:
                    f_id = str(f.get("id", ""))
                    f_name = f.get("subject", "") or f.get("name", "")
                    if f_id and f_name:
                        self.folders_map[f_id] = f_name
        except Exception as e:
            Logger.warn(f"获取小米文件夹列表失败: {e}")

    def fetch_notes(self) -> List[UnifiedNote]:
        self._fetch_folders()
        notes: List[UnifiedNote] = []
        sync_tag = ""
        has_more = True
        page = 1

        Logger.info("正在从小米云服务拉取便签列表...")
        while has_more:
            params: Dict[str, Any] = {"limit": 100}
            if sync_tag:
                params["syncTag"] = sync_tag

            resp = self.session.get(f"{self.BASE_URL}/note/full/page/", params=params)
            if resp.status_code != 200:
                Logger.error(f"拉取小米便签第 {page} 页失败: HTTP {resp.status_code}")
                break

            try:
                result_data = resp.json()
            except Exception as e:
                Logger.error(f"解析小米便签返回 JSON 失败: {e}")
                break

            data_obj = result_data.get("data", {})
            entries = data_obj.get("entries", [])
            if not entries:
                break

            Logger.info(f"第 {page} 页获取到 {len(entries)} 条便签记录...")
            for item in entries:
                try:
                    unified_note = self._parse_note_entry(item)
                    if unified_note and not unified_note.is_deleted:
                        notes.append(unified_note)
                except Exception as ex:
                    Logger.warn(f"解析便签条目异常: {ex}")

            sync_tag = data_obj.get("syncTag", "")
            has_more = bool(data_obj.get("hasMore", False))
            page += 1

        Logger.success(f"共获取到 {len(notes)} 条有效小米便签。")
        return notes

    def _parse_note_entry(self, entry: Dict[str, Any]) -> Optional[UnifiedNote]:
        note_id = str(entry.get("id", ""))
        if not note_id:
            return None

        # Folder
        folder_id = str(entry.get("folderId", "0"))
        folder_name = self.folders_map.get(folder_id, "Default")

        # Dates (milliseconds)
        created_ts = entry.get("createDate") or entry.get("dateCreated")
        created_at = datetime.fromtimestamp(created_ts / 1000) if created_ts else None
        
        updated_ts = entry.get("modifyDate") or entry.get("dateModified")
        updated_at = datetime.fromtimestamp(updated_ts / 1000) if updated_ts else None

        # Status
        status = entry.get("status", "")
        is_deleted = status in ("deleted", "trashed")

        # Content parsing
        raw_content = entry.get("content", "") or ""
        snippet = entry.get("snippet", "") or entry.get("subject", "")

        # Attachments & extraInfo
        extra_info_str = entry.get("extraInfo", "")
        extra_info = {}
        if extra_info_str:
            try:
                extra_info = json.loads(extra_info_str) if isinstance(extra_info_str, str) else extra_info_str
            except Exception:
                pass

        attachments: List[UnifiedAttachment] = []
        content_md = ""

        # Check if raw_content is Delta JSON or rich HTML or plain text
        if raw_content.startswith("{") or raw_content.startswith("["):
            try:
                delta_json = json.loads(raw_content)
                content_md = self._convert_delta_to_markdown(delta_json, attachments)
            except Exception:
                content_md = raw_content
        elif "<p>" in raw_content or "<div>" in raw_content or "<br" in raw_content:
            content_md = html_to_markdown(raw_content)
        else:
            content_md = raw_content

        # Extract images from extraInfo
        if extra_info:
            # Check img list
            img_list = extra_info.get("img", []) or extra_info.get("images", [])
            for idx, img in enumerate(img_list):
                file_id = img.get("fileId") or img.get("id") or f"img_{idx}"
                img_url = f"{self.BASE_URL}/note/img/{file_id}/full"
                attachments.append(
                    UnifiedAttachment(
                        id=str(file_id),
                        filename=f"mi_img_{file_id}.jpg",
                        url=img_url,
                        mime_type="image/jpeg",
                        cookies=dict(self.session.cookies),
                        headers={"Referer": f"{self.BASE_URL}/"}
                    )
                )

        title = snippet.strip()
        if not title and content_md:
            first_line = content_md.splitlines()[0].strip().lstrip("#").strip()
            title = first_line[:60]

        return UnifiedNote(
            id=note_id,
            source_platform="xiaomi",
            title=title,
            content_raw=raw_content,
            content_markdown=content_md,
            folder=folder_name,
            created_at=created_at,
            updated_at=updated_at,
            is_deleted=is_deleted,
            attachments=attachments,
            extra_metadata=extra_info
        )

    def _convert_delta_to_markdown(self, delta: Any, attachments: List[UnifiedAttachment]) -> str:
        """Converts Xiaomi Delta JSON format to Markdown."""
        if isinstance(delta, dict) and "ops" in delta:
            ops = delta["ops"]
        elif isinstance(delta, list):
            ops = delta
        else:
            return str(delta)

        lines = []
        curr_line = ""

        for op in ops:
            insert_val = op.get("insert", "")
            attrs = op.get("attributes", {})

            if isinstance(insert_val, str):
                text = insert_val
                if attrs.get("bold"):
                    text = f"**{text}**"
                if attrs.get("italic"):
                    text = f"*{text}*"
                if attrs.get("strike"):
                    text = f"~~{text}~~"
                
                if "\n" in text:
                    parts = text.split("\n")
                    curr_line += parts[0]
                    lines.append(curr_line)
                    for p in parts[1:-1]:
                        lines.append(p)
                    curr_line = parts[-1]
                else:
                    curr_line += text
            elif isinstance(insert_val, dict):
                # Image / voice
                if "image" in insert_val:
                    img_id = insert_val["image"]
                    curr_line += f" ![image]({img_id}) "
                elif "audio" in insert_val:
                    audio_id = insert_val["audio"]
                    curr_line += f" 📎 [audio]({audio_id}) "

        if curr_line:
            lines.append(curr_line)

        return "\n".join(lines)
