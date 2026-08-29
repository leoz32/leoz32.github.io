#!/usr/bin/env python3
"""Structural checks for Leo's static homepage."""

from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
RESUME = ROOT / "resume.html"
CSS = ROOT / "assets" / "style.css"

OWNED = [
    "arxiv-daily",
    "Restaurant-Management-System",
    "RAG",
    "paper-copilot",
]
FORKS = [
    "claude-video",
    "RL.cu",
    "SearchClaw",
    "pyre-code",
    "chinese-buy-us-stock-guide",
]
FORBIDDEN = [
    "小何",
    "何帅",
    "woshidandan",
    "xiaohegithub",
    "2281444815",
    "changyan",
    "dog.swf",
]


class SimpleHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.headings: list[tuple[str, str]] = []
        self.ids: list[str] = []
        self.classes: list[str] = []
        self.text_chunks: list[str] = []
        self._href: str | None = None
        self._heading: str | None = None
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: (v or "") for k, v in attrs}
        if "id" in attr:
            self.ids.append(attr["id"])
        if "class" in attr:
            self.classes.extend(attr["class"].split())
        if tag == "a":
            self._href = attr.get("href", "")
        if tag in {"h1", "h2", "h3"}:
            self._heading = tag
            self._heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._href = None
        if tag in {"h1", "h2", "h3"} and self._heading:
            self.headings.append((tag, "".join(self._heading_parts).strip()))
            self._heading = None

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        self.text_chunks.append(text)
        if self._href is not None:
            self.links.append((self._href, text))
        if self._heading:
            self._heading_parts.append(text)

    @property
    def text(self) -> str:
        return " ".join(self.text_chunks)


def parse(path: Path) -> SimpleHTML:
    parser = SimpleHTML()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


class HomepageTests(unittest.TestCase):
    def test_index_exists(self) -> None:
        self.assertTrue(INDEX.is_file())

    def test_no_forks_section_or_repos(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        self.assertNotIn("学习与关注", html)
        for name in FORKS:
            self.assertNotIn(name, html)

    def test_only_owned_project_cards(self) -> None:
        parsed = parse(INDEX)
        hrefs = [href for href, _ in parsed.links]
        project_hrefs = [
            href
            for href in hrefs
            if href.startswith("https://github.com/leoz32/")
            and href.rstrip("/") != "https://github.com/leoz32"
        ]
        repos = [href.rsplit("/", 1)[-1] for href in project_hrefs]
        unique = list(dict.fromkeys(repos))
        self.assertEqual(unique, OWNED)
        self.assertGreaterEqual(parsed.classes.count("card"), 4)
        self.assertEqual(parsed.classes.count("card"), 4)

    def test_resume_is_rightmost_nav_item(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        nav = re.search(r'<nav class="nav"[^>]*>(.*?)</nav>', html, re.S)
        self.assertIsNotNone(nav)
        items = re.findall(r"<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", nav.group(1), re.S)
        labels = [re.sub(r"\s+", "", text) for _, text in items]
        self.assertEqual(labels[-1], "简历")
        self.assertEqual(items[-1][0], "resume.html")
        self.assertIn("关于", labels)
        self.assertIn("项目", labels)
        self.assertIn("GitHub", labels)

    def test_each_card_has_overlay_writeup(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        self.assertGreaterEqual(html.count("card-overlay"), 4)
        expected = {
            "arxiv-daily": ["arxiv", "Computer Vision", "15", "papers.json"],
            "Restaurant-Management-System": ["Flask", "Access", "pyodbc"],
            "RAG": ["OpenStax", "BM25", "RRF"],
            "paper-copilot": ["PROCESS", "Markdown", "OpenAI"],
        }
        for repo, needles in expected.items():
            block = re.search(
                rf'id="overlay-{re.escape(repo)}".*?</div>',
                html,
                re.S,
            )
            self.assertIsNotNone(block, f"missing overlay for {repo}")
            text = block.group(0)
            for needle in needles:
                self.assertIn(needle, text, f"{repo} overlay missing {needle}")

    def test_overlay_shown_on_hover_and_focus(self) -> None:
        css = CSS.read_text(encoding="utf-8")
        self.assertRegex(css, r"\.card:hover\s+\.card-overlay")
        self.assertRegex(css, r"\.card:focus-within\s+\.card-overlay")
        card_block = re.search(r"\.card\s*\{([^}]+)\}", css)
        self.assertIsNotNone(card_block)
        self.assertNotRegex(card_block.group(1), r"overflow\s*:\s*hidden")
        grid_block = re.search(r"\.grid\s*\{([^}]+)\}", css)
        self.assertIsNotNone(grid_block)
        self.assertNotRegex(grid_block.group(1), r"overflow\s*:\s*hidden")
        overlay_block = re.search(r"\.card-overlay\s*\{([^}]+)\}", css)
        self.assertIsNotNone(overlay_block)
        self.assertNotRegex(overlay_block.group(1), r"overflow\s*:\s*hidden")

    def test_resume_page_is_placeholder(self) -> None:
        self.assertTrue(RESUME.is_file())
        parsed = parse(RESUME)
        self.assertTrue(any(text == "简历" for _, text in parsed.headings))
        hrefs = [href for href, _ in parsed.links]
        self.assertTrue(any(href in {"./", "index.html", "/"} for href in hrefs))
        body_text = parsed.text
        for fake in ("教育经历", "工作经历", "实习", "GPA", "论文发表"):
            self.assertNotIn(fake, body_text)

    def test_no_original_author_leftovers(self) -> None:
        for path in (INDEX, RESUME, CSS):
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
