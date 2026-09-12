"""Distributable product instructions stay readable and link to real papers."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProductInstructionsTest(unittest.TestCase):
    def test_instructions_are_scannable(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# WorkLane"))
        self.assertLessEqual(len(text.splitlines()), 140)

    def test_local_instruction_links_resolve_inside_product(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        links = re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text)
        self.assertTrue(links, "Instructions must link to their supporting papers")
        for link in links:
            if link.startswith(("https://", "http://", "mailto:")):
                continue
            target = (ROOT / link).resolve()
            self.assertTrue(target.is_relative_to(ROOT.resolve()), link)
            self.assertTrue(target.is_file(), link)


if __name__ == "__main__":
    unittest.main()
