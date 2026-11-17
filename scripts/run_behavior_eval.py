"""Collect actual API outputs; this command DOES NOT grade model behavior.

Credentials are read only from environment variables by the CLI. A local HTTP
fixture is useful for unit tests but is not a real model evaluation. No model-
proposed commands or file updates are executed.
"""
import argparse
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

try:
    from .eval_support import ROOT, VARIANTS, build_messages, digest_json, load_cases, utc_now, write_json
except ImportError:
    from eval_support import ROOT, VARIANTS, build_messages, digest_json, load_cases, utc_now, write_json


class EvaluationError(Exception):
    def __init__(self, message, http_status=None):
        super().__init__(message)
        self.http_status = http_status


class NoRedirect(HTTPRedirectHandler):
    """Never forward a bearer credential to a redirected API destination."""
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def validate_endpoint(base_url):
    parts = urlsplit(base_url)
    local = parts.hostname in ("127.0.0.1", "localhost", "::1")
    if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("API endpoint must not embed credentials, query parameters or fragments")
    if parts.scheme != "https" and not (parts.scheme == "http" and local):
        raise ValueError("HTTPS is required except for loopback HTTP test fixtures")


def call_model(base_url, api_key, model, api, messages, timeout):
    """Return visible assistant text and provider provenance, never error bodies."""
    if api == "responses":
        route = "/responses"
        payload = {"model": model, "input": messages, "max_output_tokens": 4096}
    else:
        route = "/chat/completions"
        payload = {"model": model, "messages": messages, "max_tokens": 4096}
    request = Request(base_url.rstrip("/") + route, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}, method="POST")
    start = time.monotonic()
    # Loopback fixtures must never traverse an OS proxy (Windows may proxy local
    # hosts by default). Remote HTTPS still uses the configured system proxy.
    local = urlsplit(base_url).hostname in ("127.0.0.1", "localhost", "::1")
    opener = build_opener(NoRedirect(), ProxyHandler({})) if local else build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            data = json.load(response)
    except HTTPError as error:
        # Provider error bodies may echo credentials. Do not persist them.
        raise EvaluationError("HTTP %d" % error.code, error.code) from None
    except (URLError, OSError, ValueError) as error:
        raise EvaluationError("transport/response error: " + type(error).__name__) from None
    if not isinstance(data, dict) or data.get("error"):
        raise EvaluationError("provider returned an error or malformed response")
    if api_key in json.dumps(data, ensure_ascii=False):
        # Even successful responses can reflect the bearer token in text or
        # metadata. Reject them before any provider fields enter a checkpoint.
        raise EvaluationError("provider response exposed evaluation credential; output not retained")
    try:
        if api == "responses":
            if data.get("status") != "completed":
                raise EvaluationError("response not completed")
            texts = []
            for output in data.get("output", []):
                if output.get("type") == "message":
                    for content in output.get("content", []):
                        if content.get("type") == "output_text":
                            texts.append(content["text"])
                        elif content.get("type") == "refusal":
                            texts.append(content["refusal"])
            text = "\n".join(texts)
        else:
            choice = data["choices"][0]
            if choice.get("finish_reason") not in ("stop", "tool_calls"):
                raise EvaluationError("response not completed (including truncation)")
            if choice.get("finish_reason") == "tool_calls":
                raise EvaluationError("tool calls are unsupported in this text-only harness")
            text = choice["message"].get("content") or choice["message"].get("refusal") or ""
    except (KeyError, TypeError, IndexError, AttributeError):
        raise EvaluationError("malformed assistant output") from None
    if not isinstance(text, str) or not text.strip():
        raise EvaluationError("empty assistant output")
    return {"assistant": text, "returned_model": data.get("model"), "response_id": data.get("id"), "latency_seconds": round(time.monotonic() - start, 3), "usage": data.get("usage")}


def source_revision(root, variant, revision):
    target = revision if variant == "baseline" else "HEAD"
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", target + "^{commit}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode("ascii").strip() if result.returncode == 0 else "unversioned"


def final_status(samples):
    statuses = [sample["status"] for sample in samples]
    if all(status == "completed" for status in statuses):
        return "completed"
    if "completed" in statuses:
        return "partial"
    if "error" in statuses:
        return "error"
    return "not_run"


def run_evaluation(root, cases, model, base_url, api_key, api="chat", variant="current", revision="HEAD", repeats=1, timeout=90, on_update=None):
    if not cases or not isinstance(model, str) or not model.strip():
        raise ValueError("cases and model are required")
    if api not in ("chat", "responses") or variant not in VARIANTS:
        raise ValueError("unsupported API or variant")
    if type(repeats) is not int or repeats < 1 or timeout <= 0:
        raise ValueError("repeats and timeout must be positive")
    if base_url:
        validate_endpoint(base_url)
    initial = {case["id"]: build_messages(root, case, variant, revision) for case in cases}
    run = {"schema_version": 1, "kind": "behavior", "run_id": str(uuid.uuid4()), "created_utc": utc_now(), "variant": variant, "source_revision": source_revision(root, variant, revision), "requested_model": model, "base_url": base_url, "api": api, "repeats_requested": repeats, "sampling": {"temperature": "provider default", "seed": "not set"}, "case_ids": [case["id"] for case in cases], "cases_sha256": digest_json(cases), "contexts_sha256": {case_id: digest_json(messages) for case_id, messages in initial.items()}, "execution_scope": "text-only; proposed actions are not executed", "learner_scope": "fixed synthetic user-turn replay, not real candidate mastery", "grading_status": "ungraded", "status": "running", "samples": []}
    for case in cases:
        for index in range(1, repeats + 1):
            run["samples"].append({"case_id": case["id"], "sample_index": index, "status": "pending", "turns": []})
    # Persist exact initial inputs so reviewers can inspect context, not just hashes.
    run["initial_messages"] = initial
    if api_key and (api_key in json.dumps(run, ensure_ascii=False) or api_key in json.dumps(cases, ensure_ascii=False)):
        raise ValueError("evaluation credential appears in inputs or metadata; refuse to persist or send")
    if on_update:
        on_update(run)
    blocked = "missing_api_key" if not api_key else ("missing_base_url" if not base_url else None)
    case_by_id = {case["id"]: case for case in cases}
    for sample in run["samples"]:
        if blocked:
            sample.update(status="not_run", reason=blocked)
        else:
            messages = [dict(message) for message in initial[sample["case_id"]]]
            case = case_by_id[sample["case_id"]]
            try:
                for index, turn in enumerate(case["turns"]):
                    if index:
                        messages.append({"role": "user", "content": turn})
                    output = call_model(base_url, api_key, model, api, messages, timeout)
                    sample["turns"].append(dict(output, user=turn, turn=index + 1))
                    messages.append({"role": "assistant", "content": output["assistant"]})
                sample["status"] = "completed"
            except EvaluationError as error:
                sample.update(status="error", error=str(error), failed_turn=len(sample["turns"]) + 1, http_status=error.http_status)
                if error.http_status in (401, 403):
                    # Do not spend five requests repeating an authorization failure.
                    blocked = "authorization_failed"
        if on_update:
            on_update(run)
    run["status"] = final_status(run["samples"])
    run["finished_utc"] = utc_now()
    if on_update:
        on_update(run)
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/cases.json")
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api", choices=("chat", "responses"), default="chat")
    parser.add_argument("--variant", choices=VARIANTS, default="current")
    parser.add_argument("--revision", default="5671dc8206798385d099d94d031524d2aacfab43")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new trace filename")
    try:
        cases = load_cases(args.cases)
        if args.case_ids:
            requested = set(args.case_ids)
            if len(requested) != len(args.case_ids) or not requested <= {case["id"] for case in cases}:
                raise ValueError("case selection contains duplicate or unknown IDs")
            cases = [case for case in cases if case["id"] in requested]
        run = run_evaluation(args.root, cases, args.model, os.environ.get("INTERVIEW_EVAL_BASE_URL"), os.environ.get("INTERVIEW_EVAL_API_KEY"), args.api, args.variant, args.revision, args.repeats, args.timeout, on_update=lambda value: write_json(args.output, value))
    except (ValueError, OSError) as error:
        parser.error(str(error))
    counts = {status: sum(sample["status"] == status for sample in run["samples"]) for status in ("completed", "error", "not_run")}
    print(json.dumps({"kind": "behavior", "status": run["status"], "grading_status": "ungraded", "samples": counts, "trace": str(args.output)}, ensure_ascii=True))
    return 0 if run["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
