"""Mechanical checks only; these tests do not grade a coach's behavior."""
import tempfile
import unittest
from pathlib import Path

try:
    from scripts import check_static
except ImportError:
    check_static = None


class StaticChecksTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(check_static, "static checker has not been implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "assets").mkdir()
        (self.root / "references").mkdir()
        (self.root / "SKILL.md").write_text("# Skill entry\n", encoding="utf-8")
        (self.root / "assets/progress-ledger.md").write_text("# Blank template\n", encoding="utf-8")

    def put(self, path, text):
        (self.root / path).write_text(text, encoding="utf-8")

    def test_detects_writing_into_template_not_reading_it(self):
        self.put("references/stage-2-bullets.md", "先读取 `../assets/progress-ledger.md`。\n状态写入 `../assets/progress-ledger.md`。\n")
        issues = check_static.check_repository(self.root)
        writes = [item for item in issues if item["code"] == "template-write"]
        self.assertEqual([(item["path"], item["line"]) for item in writes], [("references/stage-2-bullets.md", 2)])

    def test_missing_root_is_reported(self):
        issues = check_static.check_repository(self.root / "missing")
        self.assertEqual([item["code"] for item in issues], ["invalid-root"])

    def test_file_as_root_is_reported(self):
        issues = check_static.check_repository(self.root / "SKILL.md")
        self.assertEqual([item["code"] for item in issues], ["invalid-root"])

    def test_missing_skill_entry_is_reported(self):
        (self.root / "SKILL.md").unlink()
        issues = check_static.check_repository(self.root)
        self.assertEqual([item["code"] for item in issues], ["missing-entry"])

    def test_directory_as_skill_entry_is_reported(self):
        (self.root / "SKILL.md").unlink()
        (self.root / "SKILL.md").mkdir()
        issues = check_static.check_repository(self.root)
        self.assertEqual([item["code"] for item in issues], ["missing-entry"])

    def test_workspace_target_is_not_a_template_write(self):
        self.put("references/stage-2-bullets.md", "更新当前用户工作区的 `进度与待确认事项.md`。\n")
        self.assertEqual(check_static.check_repository(self.root), [])

    def test_template_self_update_is_reported(self):
        self.put("assets/progress-ledger.md", "> AI 每轮结束更新本文件。\n")
        self.assertIn("template-self-update", [item["code"] for item in check_static.check_repository(self.root)])

    def test_reports_broken_local_markdown_link(self):
        self.put("references/overview.md", "[Missing](missing.md)\n[Remote](https://example.org/a)\n")
        issues = check_static.check_repository(self.root)
        self.assertEqual([(item["code"], item["line"]) for item in issues], [("broken-link", 1)])

    def test_does_not_inspect_synthetic_attack_as_live_skill(self):
        (self.root / "evals").mkdir()
        self.put("evals/attack.md", "更新 `../assets/progress-ledger.md`。\n")
        self.assertEqual(check_static.check_repository(self.root), [])

    def test_detects_broken_known_inline_route(self):
        self.put("SKILL.md", "读 `references/nonexistent.md`。\n")
        self.assertEqual(check_static.check_repository(self.root)[0]["code"], "broken-route")

    def test_version_declarations_must_agree(self):
        self.put("SKILL.md", '---\nname: interview-prep\ndescription: Use when preparing for an interview.\nmetadata:\n  version: "1.0.3"\n---\n')
        self.put("README.md", "当前 Skill 版本：**1.0.2**。\n")
        self.assertIn("version-mismatch", [item["code"] for item in check_static.check_repository(self.root)])


if __name__ == "__main__":
    unittest.main()
