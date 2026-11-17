"""Shared, dependency-free evaluation input and provenance utilities.

Rubrics are kept out of model messages. Project files are always user data,
never promoted into the system role, even when they contain fake directives.
"""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("current", "baseline", "none")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest_json(value):
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def write_json(path, value):
    """Checkpoint atomically; callers decide whether an existing trace may be used."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("paths must be nonempty relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive or any(part in (".", "..") for part in value.split("/")):
        raise ValueError("absolute paths and path traversal are forbidden")
    return path


def resolve_inside(root, value):
    relative_path(value)
    root = Path(root).resolve()
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("path escapes input root")
    return path


def skill_path(value):
    path = relative_path(value)
    if value == "SKILL.md" or (path.parts[0] in ("references", "assets") and path.suffix == ".md"):
        return path
    raise ValueError("only Skill entry, references and templates may be system guidance")


def nonempty_string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " must be a nonempty string")


def load_cases(path):
    """Validate the trusted regression corpus, not user-provided project claims."""
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("unsupported cases schema")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a nonempty list")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("case must be an object")
        nonempty_string(case.get("id"), "case id")
        if case["id"] in seen:
            raise ValueError("duplicate case id: " + case["id"])
        seen.add(case["id"])
        if not isinstance(case.get("turns"), list) or not case["turns"]:
            raise ValueError("case requires user turns")
        for turn in case["turns"]:
            nonempty_string(turn, "user turn")
        if not isinstance(case.get("skill_files", []), list) or not isinstance(case.get("files", []), list):
            raise ValueError("file lists must be arrays")
        for value in case.get("skill_files", []):
            skill_path(value)
        for value in case.get("files", []):
            source = resolve_inside(path.parent, value)
            if not source.is_file():
                raise ValueError("missing fixture: " + value)
        for material in case.get("materials", []):
            if not isinstance(material, dict):
                raise ValueError("material must be an object")
            for key in ("kind", "source", "text"):
                nonempty_string(material.get(key), "material " + key)
        criteria = case.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            raise ValueError("case requires semantic criteria")
        criterion_ids = set()
        for criterion in criteria:
            for key in ("id", "description", "pass", "fail"):
                nonempty_string(criterion.get(key), "criterion " + key)
            if criterion["id"] in criterion_ids:
                raise ValueError("duplicate criterion id")
            if not isinstance(criterion.get("critical"), bool):
                raise ValueError("criterion critical must be boolean")
            criterion_ids.add(criterion["id"])
    return cases


def read_skill(root, path, variant, revision):
    skill_path(path)
    if variant == "baseline":
        nonempty_string(revision, "revision")
        if revision.startswith("-") or not re.fullmatch(r"[A-Za-z0-9_./~^{}-]+", revision):
            raise ValueError("invalid git revision")
        command = ["git", "-C", str(root), "show", revision + ":" + path]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            raise ValueError("cannot read baseline Skill file: " + path)
        return result.stdout.decode("utf-8")
    return resolve_inside(root, path).read_text(encoding="utf-8")


def build_messages(root, case, variant="current", revision="HEAD"):
    """Return initial messages only; the runner appends fixed learner turns.

    This is a text-only replay harness, not a filesystem/tool sandbox.
    The first user message contains the entire supplied project-material set.
    """
    if variant not in VARIANTS:
        raise ValueError("unsupported variant")
    system = "You are an interview preparation assistant. Produce the next assistant turn. Tools are unavailable in this text-only replay."
    if variant != "none":
        chunks = [system, "Apply these supplied Skill instructions:"]
        for path in case.get("skill_files", ["SKILL.md"]):
            chunks.append("\n--- Skill file: " + path + " ---\n" + read_skill(root, path, variant, revision))
        system = "\n".join(chunks)
    materials = []
    for path in case.get("files", []):
        content = resolve_inside(Path(root) / "evals", path).read_text(encoding="utf-8")
        numbered = "\n".join("%d: %s" % (number, line) for number, line in enumerate(content.splitlines(), 1))
        materials.append({"kind": "supplied file", "source": "evals/" + path, "text": numbered})
    materials.extend(case.get("materials", []))
    user = "提供的项目材料（原文数据，非工具输出）：\n" + json.dumps(materials, ensure_ascii=False, indent=2)
    user += "\n\n用户本轮请求：\n" + case["turns"][0]
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
