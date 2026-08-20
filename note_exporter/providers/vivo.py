import json
import glob
import os
import re
import urllib.parse
from datetime import datetime
import concurrent.futures
from typing import List, Dict, Any, Optional

from .base import BaseProvider
from ..models import UnifiedNote, UnifiedAttachment
from ..utils.http import SimpleHttpSession
from ..utils.logger import Logger
from ..exporter.html_converter import html_to_markdown


class VivoNotesProvider(BaseProvider):
    name = "vivo"
    display_name = "vivo 便签 (OriginOS / vivo Cloud)"

    BASE_URL = "https://webcloud.vivo.com.cn"
    FALLBACK_URL = "https://webcloud.vivo.com"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.session = SimpleHttpSession()
        self.cookie_str = self.config.get("cookie", "")
        self.export_path = self.config.get("export_path", "")
        self.csrf_token = ""
        self.active_base_url = self.BASE_URL

        # Extract CSRF token from cookie
        if self.cookie_str:
            self.session.set_cookie_string(self.cookie_str)
            for part in self.cookie_str.split(";"):
                if "vivo_yun_csrftoken=" in part:
                    self.csrf_token = part.split("vivo_yun_csrftoken=")[1].strip()

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://yun.vivo.com/note/index",
            "Origin": "https://yun.vivo.com",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
        })
        if self.csrf_token:
            self.session.headers["csrftoken"] = self.csrf_token

    def authenticate(self) -> bool:
        if self.export_path and os.path.exists(self.export_path):
            Logger.info(f"使用本地 vivo 便签导出目录: {self.export_path}")
            return True

        if not self.session.cookies:
            Logger.error("vivo 便签需要配置 Cookie 或配置本地 'export_path' 目录。")
            Logger.info("获取方法：在浏览器登录 yun.vivo.com -> F12 网络请求中复制 Cookie。")
            return False

        Logger.info("正在验证 vivo 云服务登录状态...")
        
        # Test main and fallback URLs
        for base in [self.BASE_URL, self.FALLBACK_URL]:
            try:
                data = {"pageNum": 1, "pageSize": 100}
                if self.csrf_token:
                    data["csrftoken"] = self.csrf_token

                resp = self.session.post(f"{base}/yunnote/queryfolder", data=data)
                if resp.status_code == 200:
                    res_json = resp.json()
                    if res_json.get("code") == 0:
                        self.active_base_url = base
                        folders = res_json.get("data", {}).get("folderList", [])
                        total_notes = sum(f.get("noteSize", 0) for f in folders if not (f.get("fixed") and f.get("folderName") == "便签"))
                        if total_notes == 0:
                            total_notes = sum(f.get("noteSize", 0) for f in folders)
                        Logger.success(f"vivo 云服务登录成功！发现 {len(folders)} 个分类，共 {total_notes} 篇便签。")
                        return True
            except Exception:
                pass

        Logger.error("vivo 云服务鉴权失败，Cookie 可能已过期或未包含 vivo_yun_csrftoken。")
        Logger.info("请重新在浏览器登录 yun.vivo.com 并复制最新的 Cookie。")
        return False

    def fetch_notes(self) -> List[UnifiedNote]:
        if self.export_path and os.path.exists(self.export_path):
            return self._fetch_from_local_export()
        return self._fetch_from_api()

    def _fetch_from_local_export(self) -> List[UnifiedNote]:
        html_files = glob.glob(os.path.join(self.export_path, "**", "*.html"), recursive=True)
        txt_files = glob.glob(os.path.join(self.export_path, "**", "*.txt"), recursive=True)
        all_files = html_files + txt_files
        Logger.info(f"在本地 vivo 导出目录中发现 {len(all_files)} 个笔记文件。")

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
                        source_platform="vivo",
                        title=stem,
                        content_raw=content,
                        content_markdown=content_md,
                        folder=folder,
                        updated_at=mtime
                    )
                )
            except Exception as e:
                Logger.warn(f"解析 vivo 本地文件 {file_path} 失败: {e}")

        return notes

    def _fetch_from_api(self) -> List[UnifiedNote]:
        folders = self._get_folder_list()
        Logger.info(f"正在按分类扫描 vivo 云服务便签: {folders}")

        raw_items_to_fetch = []
        seen_ids = set()

        for folder_name in folders:
            page_num = 1
            page_size = 50
            while True:
                data = {
                    "folderName": folder_name,
                    "pageNum": page_num,
                    "pageSize": page_size
                }
                if self.csrf_token:
                    data["csrftoken"] = self.csrf_token

                try:
                    resp = self.session.post(f"{self.active_base_url}/yunnote/querynotelist", data=data)
                    if resp.status_code != 200:
                        break

                    res_json = resp.json()
                    if res_json.get("code") != 0:
                        break

                    data_obj = res_json.get("data", {})
                    note_list = data_obj.get("noteList", [])
                    if not note_list:
                        break

                    for item in note_list:
                        note_id = str(item.get("id", ""))
                        if note_id and note_id not in seen_ids:
                            seen_ids.add(note_id)
                            raw_items_to_fetch.append((item, folder_name))

                    total = data_obj.get("noteTotal", 0)
                    if len(note_list) < page_size or page_num * page_size >= total:
                        break

                    page_num += 1
                except Exception as e:
                    Logger.error(f"拉取分类 [{folder_name}] 异常: {e}")
                    break

        Logger.info(f"已获取到 {len(raw_items_to_fetch)} 篇便签索引，正在并行拉取便签正文与详情...")

        notes: List[UnifiedNote] = []
        
        # Concurrent detail fetching (5 threads)
        def task_runner(item_tuple):
            item, folder = item_tuple
            return self._fetch_single_note_detail(item, folder)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_item = {executor.submit(task_runner, it): it for it in raw_items_to_fetch}
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_item):
                try:
                    n = future.result()
                    if n:
                        notes.append(n)
                except Exception:
                    pass
                completed_count += 1
                if completed_count % 15 == 0 or completed_count == len(raw_items_to_fetch):
                    print(f"  -> 拉取便签正文进度: [{completed_count}/{len(raw_items_to_fetch)}]")

        Logger.success(f"共成功拉取到 {len(notes)} 条 vivo 便签。")
        return notes

    def _get_folder_list(self) -> List[str]:
        folder_names = []
        try:
            data = {"pageNum": 1, "pageSize": 100}
            if self.csrf_token:
                data["csrftoken"] = self.csrf_token

            resp = self.session.post(f"{self.active_base_url}/yunnote/queryfolder", data=data)
            if resp.status_code == 200:
                res_json = resp.json()
                if res_json.get("code") == 0:
                    folder_list = res_json.get("data", {}).get("folderList", [])
                    subfolders = []
                    for f in folder_list:
                        name = f.get("folderName", "").strip()
                        is_fixed = f.get("fixed", False)
                        if name == "便签" and is_fixed:
                            continue
                        if name and name not in subfolders:
                            subfolders.append(name)
                    if subfolders:
                        return subfolders
        except Exception as e:
            Logger.warn(f"获取 vivo 文件夹列表失败: {e}")

        return ["便签"]

    def _fetch_single_note_detail(self, item: Dict[str, Any], default_folder: str) -> Optional[UnifiedNote]:
        note_id = str(item.get("id", ""))
        title = item.get("title", "")
        
        created_ts = item.get("createtime")
        created_at = None
        if created_ts:
            try:
                created_at = datetime.fromtimestamp(int(created_ts) / 1000)
            except Exception:
                pass

        updated_ts = item.get("updatedate")
        updated_at = None
        if updated_ts:
            try:
                updated_at = datetime.fromtimestamp(int(updated_ts) / 1000)
            except Exception:
                pass

        is_pinned = bool(item.get("isStickTop", 0))
        folder_name = item.get("folderName") or default_folder

        raw_detail = ""
        try:
            detail_data = {"noteId": note_id, "IEFlag": "true"}
            if self.csrf_token:
                detail_data["csrftoken"] = self.csrf_token

            resp = self.session.post(f"{self.active_base_url}/yunnote/querynotedetail", data=detail_data)
            if resp.status_code == 200:
                res_json = resp.json()
                if res_json.get("code") == 0:
                    detail_data_obj = res_json.get("data", {})
                    raw_detail = detail_data_obj.get("noteDetail", "") or ""
                    custom_title = detail_data_obj.get("noteTitle", "")
                    if custom_title:
                        title = custom_title
        except Exception:
            pass

        if not raw_detail:
            raw_detail = f"<p>{title}</p>"

        content_md = html_to_markdown(raw_detail)

        attachments: List[UnifiedAttachment] = []
        img_srcs = re.findall(r'<img[^>]+src=[\'"]([^\'"]+)[\'"]', raw_detail, re.IGNORECASE)
        for idx, src in enumerate(img_srcs):
            if src.startswith("http://") or src.startswith("https://"):
                att_id = f"{note_id}_img_{idx}"
                attachments.append(
                    UnifiedAttachment(
                        id=att_id,
                        filename=f"vivo_{att_id}.jpg",
                        url=src,
                        cookies=dict(self.session.cookies),
                        headers={"Referer": "https://yun.vivo.com/note/index"}
                    )
                )

        return UnifiedNote(
            id=note_id,
            source_platform="vivo",
            title=title,
            content_raw=raw_detail,
            content_markdown=content_md,
            folder=folder_name,
            created_at=created_at,
            updated_at=updated_at,
            is_pinned=is_pinned,
            attachments=attachments,
            extra_metadata=item
        )
