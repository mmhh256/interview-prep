"""Mechanical repository checks. NEVER use this as model-behavior evidence."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

try:
    from .eval_support import ROOT, load_cases, utc_now, write_json
except ImportError:
    from eval_support import ROOT, load_cases, utc_now, write_json


INLINE_ROUTE = re.compile(r"`((?:\.\./)?(?:assets|references)/[^`]+\.md|(?:stage-[1-4]-[a-z-]+|evidence-contract|overview|main-prompt|SKILL)\.md)`")
LINK = re.compile(r"\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)")
TEMPLATE_TARGET = re.compile(r"(?:更新|写入|填写|维护|覆盖)[^。\n;；]*`(?:\.\./)?assets/[^`]*`")


def check_repository(root):
    """Return syntactic issues, not semantic judgments about coaching quality.

    Template-write detection is deliberately narrow and cannot prove all prose
    is consistent. Semantic conflicts and prompt injection require behavioral
    review. Synthetic attack examples are not treated as executable Skill prose.
    """
    root = Path(root)
    issues = []

    def add(path, line, code, message):
        issues.append({"path": path.relative_to(root).as_posix(), "line": line, "code": code, "message": message})

    if not root.is_dir():
        add(root, 1, "invalid-root", "Repository root must be an existing directory")
        return issues
    if not (root / "SKILL.md").is_file():
        add(root / "SKILL.md", 1, "missing-entry", "Required Skill entry SKILL.md is missing or not a file")

    active = [root / "SKILL.md"] + sorted((root / "references").glob("*.md")) + sorted((root / "assets").glob("*.md"))
    for path in active:
        if not path.is_file():
            continue
        in_fence = False
        for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if text.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if TEMPLATE_TARGET.search(text):
                add(path, number, "template-write", "Instruction writes to the read-only template source instead of a workspace copy")
            if path.parent.name == "assets" and re.search(r"(?:更新|写入|填写|维护)本文件", text):
                add(path, number, "template-self-update", "Template tells the coach to update the template itself")
            for target in LINK.findall(text):
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                destination = path.parent / unquote(parsed.path)
                if not destination.exists():
                    add(path, number, "broken-link", "Missing local link: " + target)
            for target in INLINE_ROUTE.findall(text):
                if not (path.parent / target).is_file():
                    add(path, number, "broken-route", "Missing referenced Skill file: " + target)
    skill = root / "SKILL.md"
    readme = root / "README.md"
    if skill.is_file() and readme.is_file():
        version = re.search(r'^\s+version:\s*[\"\']?([^\s\"\']+)', skill.read_text(encoding="utf-8"), re.MULTILINE)
        public = re.search(r"当前 Skill 版本：\*\*([^*]+)\*\*", readme.read_text(encoding="utf-8"))
        if version and public and version.group(1) != public.group(1):
            add(readme, 1, "version-mismatch", "README and Skill version declarations differ")
    corpus = root / "evals/cases.json"
    if corpus.is_file():
        try:
            load_cases(corpus)
        except (ValueError, OSError, TypeError) as error:
            add(corpus, 1, "invalid-corpus", str(error))
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    issues = check_repository(args.root)
    report = {"schema_version": 1, "kind": "static", "created_utc": utc_now(), "status": "fail" if issues else "pass", "issues": issues, "scope": "syntactic paths, links, corpus schema and version consistency only; not model behavior"}
    if args.output:
        write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
