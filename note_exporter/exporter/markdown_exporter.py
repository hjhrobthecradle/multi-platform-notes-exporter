import os
import re
import urllib.request
import urllib.parse
from typing import List, Optional
from datetime import datetime

from ..models import UnifiedNote, UnifiedAttachment, ExportResult
from .sanitizer import sanitize_filename, get_unique_filepath
from .html_converter import html_to_markdown


def format_frontmatter(note: UnifiedNote) -> str:
    """Generates YAML frontmatter string for the note."""
    lines = ["---"]
    safe_title = (note.title or note.clean_title()).replace('"', '\\"')
    lines.append(f'title: "{safe_title}"')
    
    if note.created_at:
        lines.append(f'created: "{note.created_at.isoformat()}"')
    if note.updated_at:
        lines.append(f'updated: "{note.updated_at.isoformat()}"')
    
    if note.tags:
        lines.append("tags:")
        for tag in note.tags:
            safe_tag = tag.replace('"', '\\"')
            lines.append(f'  - "{safe_tag}"')
            
    lines.append(f'source_platform: "{note.source_platform}"')
    lines.append(f'source_id: "{note.id}"')
    
    if note.is_pinned:
        lines.append("pinned: true")
    if note.is_archived:
        lines.append("archived: true")
    if note.folder and note.folder != "Default":
        safe_folder = note.folder.replace('"', '\\"')
        lines.append(f'folder: "{safe_folder}"')

    lines.append("---\n")
    return "\n".join(lines)


class MarkdownExporter:
    """Exports UnifiedNotes into structured Markdown directory with localized attachments."""

    def __init__(self, base_output_dir: str = "export_output"):
        self.base_output_dir = os.path.abspath(base_output_dir)

    def export_notes(self, platform: str, notes: List[UnifiedNote], progress_callback=None) -> ExportResult:
        platform_dir = os.path.join(self.base_output_dir, platform)
        resources_dir = os.path.join(platform_dir, "_resources")
        os.makedirs(resources_dir, exist_ok=True)

        result = ExportResult(
            platform=platform,
            total_notes=len(notes),
            output_dir=platform_dir
        )

        for idx, note in enumerate(notes):
            try:
                self._export_single_note(note, platform_dir, resources_dir, result)
                result.exported_notes += 1
            except Exception as e:
                result.failed_notes += 1
                result.errors.append(f"Note '{note.clean_title()}' ({note.id}): {str(e)}")
            
            if progress_callback:
                progress_callback(idx + 1, len(notes), note)

        return result

    def _export_single_note(self, note: UnifiedNote, platform_dir: str, resources_dir: str, result: ExportResult):
        folder_name = sanitize_filename(note.folder if note.folder else "Default")
        target_dir = os.path.join(platform_dir, folder_name) if folder_name != "Default" else platform_dir
        os.makedirs(target_dir, exist_ok=True)

        rel_resources_dir = os.path.relpath(resources_dir, target_dir).replace("\\", "/")

        content_md = note.content_markdown
        if not content_md and note.content_raw:
            content_md = html_to_markdown(note.content_raw)
        if not content_md:
            content_md = ""

        downloaded_refs = []
        for att in note.attachments:
            result.total_attachments += 1
            try:
                saved_filename = self._save_attachment(att, resources_dir)
                result.downloaded_attachments += 1
                rel_att_path = f"{rel_resources_dir}/{saved_filename}"
                downloaded_refs.append((att, rel_att_path, saved_filename))

                if att.url:
                    content_md = content_md.replace(att.url, rel_att_path)
                if att.id:
                    content_md = re.sub(rf'!?\[([^\]]*)\]\((?:attachment://)?{re.escape(att.id)}\)', rf'![\1]({rel_att_path})', content_md)
            except Exception as att_err:
                result.errors.append(f"Attachment {att.filename or att.id} error: {str(att_err)}")

        for att, rel_path, filename in downloaded_refs:
            if rel_path not in content_md and filename not in content_md:
                ext = os.path.splitext(filename)[1].lower()
                if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'):
                    content_md += f"\n\n![{filename}]({rel_path})"
                else:
                    content_md += f"\n\n[{filename}]({rel_path})"

        frontmatter = format_frontmatter(note)
        note_title = note.clean_title()
        
        body_content = content_md.strip()
        first_line = body_content.splitlines()[0].strip() if body_content else ""
        if not first_line.startswith("# ") and note_title:
            final_content = f"{frontmatter}# {note_title}\n\n{body_content}\n"
        else:
            final_content = f"{frontmatter}{body_content}\n"

        safe_filename = sanitize_filename(f"{note_title}.md")
        file_path = get_unique_filepath(target_dir, safe_filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_content)

    def _save_attachment(self, att: UnifiedAttachment, resources_dir: str) -> str:
        raw_name = att.filename or f"att_{att.id}"
        ext = os.path.splitext(raw_name)[1]
        if not ext and att.mime_type:
            ext_map = {
                "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
                "image/webp": ".webp", "audio/mp4": ".m4a", "audio/mpeg": ".mp3",
                "audio/aac": ".aac", "audio/amr": ".amr"
            }
            ext = ext_map.get(att.mime_type, ".bin")
            raw_name = f"{raw_name}{ext}"

        safe_name = sanitize_filename(f"{att.id}_{raw_name}")
        target_path = os.path.join(resources_dir, safe_name)

        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            return safe_name

        if att.content_bytes:
            with open(target_path, "wb") as f:
                f.write(att.content_bytes)
            return safe_name

        if att.url:
            req = urllib.request.Request(
                att.url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    **att.headers
                }
            )
            if att.cookies:
                cookie_str = "; ".join([f"{k}={v}" for k, v in att.cookies.items()])
                req.add_header("Cookie", cookie_str)

            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                with open(target_path, "wb") as f:
                    f.write(data)
            return safe_name

        raise ValueError("Attachment has neither content_bytes nor url.")
