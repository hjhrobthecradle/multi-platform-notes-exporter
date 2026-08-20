import re
import html
from html.parser import HTMLParser
from typing import List, Dict, Tuple, Optional


class SimpleHTMLToMarkdownParser(HTMLParser):
    """
    Robust pure-Python HTML to Markdown converter with support for
    headings, checklists, lists, inline formatting, code blocks, and media.
    """
    def __init__(self):
        super().__init__()
        self.output: List[str] = []
        self.tag_stack: List[Tuple[str, Dict[str, str]]] = []
        self.list_stack: List[str] = []  # 'ul' or 'ol'
        self.ol_counters: List[int] = []
        self.in_pre = False
        self.in_code = False
        self.image_tags: List[Dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        self.tag_stack.append((tag.lower(), attr_dict))

        t = tag.lower()
        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(t[1])
            self._ensure_newline(2)
            self.output.append("#" * level + " ")
        elif t == "p" or t == "div":
            self._ensure_newline(1)
        elif t == "br":
            self.output.append("\n")
        elif t == "hr":
            self._ensure_newline(2)
            self.output.append("---\n\n")
        elif t in ("b", "strong"):
            self.output.append("**")
        elif t in ("i", "em"):
            self.output.append("*")
        elif t in ("s", "strike", "del"):
            self.output.append("~~")
        elif t == "code":
            if not self.in_pre:
                self.output.append("`")
            self.in_code = True
        elif t == "pre":
            self._ensure_newline(2)
            self.output.append("```\n")
            self.in_pre = True
        elif t == "blockquote":
            self._ensure_newline(1)
            self.output.append("> ")
        elif t == "ul":
            self.list_stack.append("ul")
            self._ensure_newline(1)
        elif t == "ol":
            self.list_stack.append("ol")
            self.ol_counters.append(1)
            self._ensure_newline(1)
        elif t == "li":
            self._ensure_newline(1)
            indent = "  " * max(0, len(self.list_stack) - 1)
            # Check for checklist / task item class or data attribute
            classes = attr_dict.get("class", "").split()
            is_checked = attr_dict.get("data-checked") == "true" or "checked" in classes
            is_todo = "todo" in classes or "task-list-item" in classes or "checkbox" in classes

            if is_todo or "data-checked" in attr_dict:
                box = "[x] " if is_checked else "[ ] "
                self.output.append(f"{indent}- {box}")
            elif self.list_stack and self.list_stack[-1] == "ol":
                idx = self.ol_counters[-1] if self.ol_counters else 1
                self.output.append(f"{indent}{idx}. ")
                if self.ol_counters:
                    self.ol_counters[-1] += 1
            else:
                self.output.append(f"{indent}- ")
        elif t == "input":
            if attr_dict.get("type") == "checkbox":
                is_checked = "checked" in attr_dict or attr_dict.get("checked") == "true"
                self.output.append("[x] " if is_checked else "[ ] ")
        elif t == "img":
            src = attr_dict.get("src", "")
            alt = attr_dict.get("alt", "image")
            if src:
                self.output.append(f"![{alt}]({src})")
                self.image_tags.append(attr_dict)
        elif t == "a":
            self.output.append("[")

    def handle_endtag(self, tag: str):
        t = tag.lower()
        # Find matching tag in stack
        attr_dict = {}
        for i in range(len(self.tag_stack) - 1, -1, -1):
            if self.tag_stack[i][0] == t:
                attr_dict = self.tag_stack.pop(i)[1]
                break

        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._ensure_newline(2)
        elif t in ("p", "div"):
            self._ensure_newline(1)
        elif t in ("b", "strong"):
            self.output.append("**")
        elif t in ("i", "em"):
            self.output.append("*")
        elif t in ("s", "strike", "del"):
            self.output.append("~~")
        elif t == "code":
            if not self.in_pre:
                self.output.append("`")
            self.in_code = False
        elif t == "pre":
            self._ensure_newline(1)
            self.output.append("```\n\n")
            self.in_pre = False
        elif t == "blockquote":
            self._ensure_newline(1)
        elif t == "ul":
            if self.list_stack and self.list_stack[-1] == "ul":
                self.list_stack.pop()
            self._ensure_newline(1)
        elif t == "ol":
            if self.list_stack and self.list_stack[-1] == "ol":
                self.list_stack.pop()
            if self.ol_counters:
                self.ol_counters.pop()
            self._ensure_newline(1)
        elif t == "li":
            self._ensure_newline(1)
        elif t == "a":
            href = attr_dict.get("href", "")
            self.output.append(f"]({href})")

    def handle_data(self, data: str):
        if not self.in_pre:
            # Replace non-breaking spaces
            cleaned = data.replace("\xa0", " ")
            self.output.append(cleaned)
        else:
            self.output.append(data)

    def _ensure_newline(self, count: int = 1):
        if not self.output:
            return
        combined = "".join(self.output[-2:]) if len(self.output) >= 2 else (self.output[-1] if self.output else "")
        trailing_newlines = 0
        for char in reversed(combined):
            if char == "\n":
                trailing_newlines += 1
            else:
                break
        needed = count - trailing_newlines
        if needed > 0:
            self.output.append("\n" * needed)

    def get_markdown(self) -> str:
        text = "".join(self.output)
        text = html.unescape(text)
        # Collapse 3+ consecutive newlines to 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


def html_to_markdown(html_content: str) -> str:
    """
    Converts HTML string to Markdown.
    Uses markdownify if installed, otherwise uses our built-in parser.
    """
    if not html_content or not html_content.strip():
        return ""

    # Try markdownify if installed
    try:
        from markdownify import markdownify as md
        res = md(html_content, heading_style="ATX", autolinks=False)
        return res.strip()
    except ImportError:
        pass

    # Built-in parser
    parser = SimpleHTMLToMarkdownParser()
    parser.feed(html_content)
    return parser.get_markdown()
