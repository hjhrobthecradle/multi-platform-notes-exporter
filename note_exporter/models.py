from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any


@dataclass
class UnifiedAttachment:
    """Represents an attachment (image, audio, file) in a note."""
    id: str
    filename: str
    url: Optional[str] = None
    content_bytes: Optional[bytes] = None
    mime_type: Optional[str] = None
    local_relative_path: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)


@dataclass
class UnifiedNote:
    """Represents a unified note across all providers."""
    id: str
    source_platform: str  # e.g., "xiaomi", "oppo", "vivo", "apple", "google"
    title: str = ""
    content_raw: str = ""
    content_markdown: str = ""
    folder: str = "Default"
    tags: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_pinned: bool = False
    is_archived: bool = False
    is_deleted: bool = False
    attachments: List[UnifiedAttachment] = field(default_factory=list)
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def clean_title(self, max_length: int = 80) -> str:
        """Return a clean title, fallback to first line of markdown/raw if empty."""
        title = self.title.strip() if self.title else ""
        if not title:
            # Try to get first non-empty line of markdown
            lines = [line.strip().lstrip("#").strip() for line in (self.content_markdown or self.content_raw).splitlines()]
            for line in lines:
                if line:
                    title = line
                    break
        if not title:
            title = f"Untitled Note ({self.id})"
        # Remove markdown chars or line breaks
        title = title.replace("\r", " ").replace("\n", " ").strip()
        if len(title) > max_length:
            title = title[:max_length].rstrip() + "..."
        return title


@dataclass
class ExportResult:
    """Result of an export operation."""
    platform: str
    total_notes: int = 0
    exported_notes: int = 0
    failed_notes: int = 0
    total_attachments: int = 0
    downloaded_attachments: int = 0
    errors: List[str] = field(default_factory=list)
    output_dir: str = ""
