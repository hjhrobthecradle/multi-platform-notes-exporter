import os
import json
import glob
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base import BaseProvider
from ..models import UnifiedNote, UnifiedAttachment
from ..utils.logger import Logger


class GoogleKeepProvider(BaseProvider):
    name = "google"
    display_name = "Google Keep"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.username = self.config.get("username", "")
        self.password = self.config.get("password", "")  # App password or master token
        self.takeout_path = self.config.get("takeout_path", "")
        self.keep_client = None

    def authenticate(self) -> bool:
        # Check if local takeout mode
        if self.takeout_path and os.path.exists(self.takeout_path):
            Logger.info(f"Using Google Keep Takeout directory: {self.takeout_path}")
            return True

        if not self.username or not self.password:
            Logger.error("Google Keep requires either 'username' and 'password' (App Password) OR 'takeout_path' in config.")
            return False

        try:
            import gkeepapi
            self.keep_client = gkeepapi.Keep()
            Logger.info(f"Logging into Google Keep as {self.username}...")
            self.keep_client.authenticate(self.username, self.password)
            Logger.success("Google Keep authentication successful!")
            return True
        except ImportError:
            Logger.error("gkeepapi library not found. Run 'pip install gkeepapi' or use 'takeout_path' mode.")
            return False
        except Exception as e:
            Logger.error(f"Google Keep authentication failed: {e}")
            return False

    def fetch_notes(self) -> List[UnifiedNote]:
        if self.takeout_path and os.path.exists(self.takeout_path):
            return self._fetch_from_takeout()
        elif self.keep_client:
            return self._fetch_from_api()
        return []

    def _fetch_from_takeout(self) -> List[UnifiedNote]:
        """Parses Google Takeout Keep JSON files."""
        json_files = glob.glob(os.path.join(self.takeout_path, "**", "*.json"), recursive=True)
        Logger.info(f"Found {len(json_files)} JSON files in Google Takeout path.")
        
        notes = []
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                Logger.warn(f"Failed to parse {jf}: {e}")
                continue

            note_id = os.path.splitext(os.path.basename(jf))[0]
            title = data.get("title", "")
            
            # Content parsing (Checklist or Plain Text)
            lines = []
            if "listContent" in data and isinstance(data["listContent"], list):
                for item in data["listContent"]:
                    text = item.get("text", "")
                    box = "[x]" if item.get("isChecked") else "[ ]"
                    lines.append(f"- {box} {text}")
                content_md = "\n".join(lines)
            else:
                content_md = data.get("textContent", "")

            # Tags / Labels
            tags = []
            if "labels" in data and isinstance(data["labels"], list):
                for label in data["labels"]:
                    if isinstance(label, dict) and "name" in label:
                        tags.append(label["name"])
                    elif isinstance(label, str):
                        tags.append(label)

            # Timestamps
            created_at = None
            if "createdTimestampUsec" in data:
                created_at = datetime.fromtimestamp(data["createdTimestampUsec"] / 1_000_000)

            updated_at = None
            if "userEditedTimestampUsec" in data:
                updated_at = datetime.fromtimestamp(data["userEditedTimestampUsec"] / 1_000_000)

            # Attachments
            attachments = []
            if "attachments" in data and isinstance(data["attachments"], list):
                takeout_dir = os.path.dirname(jf)
                for att_info in data["attachments"]:
                    rel_name = att_info.get("filePath", "")
                    if rel_name:
                        att_path = os.path.join(takeout_dir, rel_name)
                        if os.path.exists(att_path):
                            with open(att_path, "rb") as af:
                                raw_bytes = af.read()
                            attachments.append(
                                UnifiedAttachment(
                                    id=rel_name,
                                    filename=rel_name,
                                    content_bytes=raw_bytes,
                                    mime_type=att_info.get("mimetype")
                                )
                            )

            notes.append(
                UnifiedNote(
                    id=note_id,
                    source_platform="google",
                    title=title,
                    content_markdown=content_md,
                    tags=tags,
                    created_at=created_at,
                    updated_at=updated_at,
                    is_pinned=bool(data.get("isPinned")),
                    is_archived=bool(data.get("isArchived")),
                    is_deleted=bool(data.get("isTrashed")),
                    attachments=attachments
                )
            )

        return notes

    def _fetch_from_api(self) -> List[UnifiedNote]:
        """Fetches notes via gkeepapi."""
        notes = []
        for gnote in self.keep_client.all():
            if gnote.trashed:
                continue

            title = gnote.title or ""
            
            # Content
            if hasattr(gnote, "items") and gnote.items:
                lines = []
                for item in gnote.items:
                    box = "[x]" if item.checked else "[ ]"
                    lines.append(f"- {box} {item.text}")
                content_md = "\n".join(lines)
            else:
                content_md = gnote.text or ""

            # Tags
            tags = [label.name for label in gnote.labels.all()]

            # Timestamps
            created_at = gnote.timestamps.created if hasattr(gnote.timestamps, "created") else None
            updated_at = gnote.timestamps.updated if hasattr(gnote.timestamps, "updated") else None

            # Attachments & Blobs
            attachments = []
            for blob in gnote.blobs:
                try:
                    blob_bytes = self.keep_client.getMediaUrl(blob)
                    # gkeepapi blob extraction
                    # If URL string is returned, download it
                    if isinstance(blob_bytes, str):
                        attachments.append(
                            UnifiedAttachment(
                                id=blob.blob_id,
                                filename=f"{blob.blob_id}.jpg",
                                url=blob_bytes,
                                mime_type=blob.type
                            )
                        )
                except Exception as be:
                    Logger.warn(f"Failed to fetch blob {blob.blob_id}: {be}")

            notes.append(
                UnifiedNote(
                    id=gnote.id,
                    source_platform="google",
                    title=title,
                    content_markdown=content_md,
                    tags=tags,
                    created_at=created_at,
                    updated_at=updated_at,
                    is_pinned=bool(gnote.pinned),
                    is_archived=bool(gnote.archived),
                    attachments=attachments
                )
            )

        return notes
