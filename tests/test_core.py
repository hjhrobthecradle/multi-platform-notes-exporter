import unittest
import os
import tempfile
import shutil
from datetime import datetime

from note_exporter.models import UnifiedNote, UnifiedAttachment, ExportResult
from note_exporter.config import load_config, create_default_config_if_missing, DEFAULT_CONFIG_TEMPLATE
from note_exporter.exporter.sanitizer import sanitize_filename, get_unique_filepath
from note_exporter.exporter.html_converter import html_to_markdown, SimpleHTMLToMarkdownParser
from note_exporter.exporter.markdown_exporter import MarkdownExporter, format_frontmatter


class TestSanitizer(unittest.TestCase):
    def test_sanitize_illegal_chars(self):
        raw = 'test:file/name*with?illegal"chars<here>|end'
        cleaned = sanitize_filename(raw)
        self.assertNotIn(":", cleaned)
        self.assertNotIn("/", cleaned)
        self.assertNotIn("*", cleaned)
        self.assertNotIn("?", cleaned)
        self.assertNotIn('"', cleaned)
        self.assertNotIn("<", cleaned)
        self.assertNotIn(">", cleaned)
        self.assertNotIn("|", cleaned)

    def test_windows_reserved_names(self):
        self.assertEqual(sanitize_filename("CON"), "_CON")
        self.assertEqual(sanitize_filename("prn.txt"), "_prn.txt")
        self.assertEqual(sanitize_filename("nul"), "_nul")

    def test_empty_or_whitespace(self):
        self.assertEqual(sanitize_filename(""), "untitled")
        self.assertEqual(sanitize_filename("   ...  "), "untitled")

    def test_unique_filepath(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file1 = os.path.join(temp_dir, "note.md")
            with open(file1, "w") as f:
                f.write("a")
            unique1 = get_unique_filepath(temp_dir, "note.md")
            self.assertEqual(os.path.basename(unique1), "note (1).md")

            with open(unique1, "w") as f:
                f.write("b")
            unique2 = get_unique_filepath(temp_dir, "note.md")
            self.assertEqual(os.path.basename(unique2), "note (2).md")


class TestHTMLConverter(unittest.TestCase):
    def test_headings_and_paragraphs(self):
        html = "<h1>Title</h1><p>This is <b>bold</b> and <i>italic</i> and <s>deleted</s>.</p>"
        md = html_to_markdown(html)
        self.assertIn("# Title", md)
        self.assertIn("**bold**", md)
        self.assertIn("*italic*", md)
        self.assertIn("~~deleted~~", md)

    def test_checklists(self):
        html = '<ul><li class="todo checked" data-checked="true">Done task</li><li class="todo">Pending task</li></ul>'
        md = html_to_markdown(html)
        self.assertIn("- [x] Done task", md)
        self.assertIn("- [ ] Pending task", md)

    def test_nested_lists(self):
        html = "<ol><li>First</li><li>Second</li></ol>"
        md = html_to_markdown(html)
        self.assertIn("1. First", md)
        self.assertIn("2. Second", md)

    def test_code_blocks(self):
        html = "<pre><code>def hello():\n    return 'world'</code></pre>"
        md = html_to_markdown(html)
        self.assertIn("```", md)
        self.assertIn("def hello():", md)

    def test_links_and_images(self):
        html = '<p><a href="https://example.com">Link</a> and <img src="image.jpg" alt="Photo" /></p>'
        md = html_to_markdown(html)
        self.assertIn("[Link](https://example.com)", md)
        self.assertIn("![Photo](image.jpg)", md)


class TestModelsAndExporter(unittest.TestCase):
    def test_clean_title(self):
        note = UnifiedNote(
            id="101",
            source_platform="xiaomi",
            content_markdown="First line of note\nSecond line"
        )
        self.assertEqual(note.clean_title(), "First line of note")

    def test_frontmatter_generation(self):
        dt = datetime(2026, 8, 20, 12, 0, 0)
        note = UnifiedNote(
            id="101",
            source_platform="vivo",
            title="Meeting Notes",
            content_markdown="Discuss project roadmap",
            folder="Work",
            tags=["office", "urgent"],
            created_at=dt,
            updated_at=dt,
            is_pinned=True
        )
        fm = format_frontmatter(note)
        self.assertIn('title: "Meeting Notes"', fm)
        self.assertIn('source_platform: "vivo"', fm)
        self.assertIn('folder: "Work"', fm)
        self.assertIn('pinned: true', fm)
        self.assertIn('- "office"', fm)
        self.assertIn('- "urgent"', fm)

    def test_markdown_exporter_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = MarkdownExporter(base_output_dir=temp_dir)
            att = UnifiedAttachment(
                id="att_1",
                filename="sample.png",
                content_bytes=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            )
            note = UnifiedNote(
                id="note_001",
                source_platform="xiaomi",
                title="Test Note",
                content_markdown="Here is an image: ![sample](attachment://att_1)",
                folder="Personal",
                attachments=[att]
            )

            result = exporter.export_notes("xiaomi", [note])
            self.assertEqual(result.exported_notes, 1)
            self.assertEqual(result.downloaded_attachments, 1)
            
            note_file = os.path.join(temp_dir, "xiaomi", "Personal", "Test Note.md")
            self.assertTrue(os.path.exists(note_file))
            with open(note_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn('title: "Test Note"', content)
            self.assertIn("../_resources/att_1_sample.png", content)


class TestConfig(unittest.TestCase):
    def test_fallback_config_parser(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cfg_file = os.path.join(temp_dir, "test_config.yaml")
            with open(cfg_file, "w", encoding="utf-8") as f:
                f.write("""output_dir: "./custom_out"\nxiaomi:\n  cookie: "test_cookie"\n""")
            cfg = load_config(cfg_file)
            self.assertEqual(cfg.get("output_dir"), "./custom_out")
            self.assertEqual(cfg.get("xiaomi", {}).get("cookie"), "test_cookie")

    def test_create_default_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cfg_file = os.path.join(temp_dir, "auto_config.yaml")
            create_default_config_if_missing(cfg_file)
            self.assertTrue(os.path.exists(cfg_file))
            cfg = load_config(cfg_file)
            self.assertIn("xiaomi", cfg)
            self.assertIn("vivo", cfg)


if __name__ == "__main__":
    unittest.main()
