"""Validate and aggregate EXTERNAL semantic reviews of real output traces.

This tool does not judge behavior using regexes, keywords or model self-reports.
A reviewer must inspect the full inputs and outputs and supply a reason plus
verbatim output evidence (or an explicit, scoped omission) for every criterion.
"""
import argparse
import json
from pathlib import Path

try:
    from .eval_support import ROOT, digest_json, load_cases, nonempty_string, utc_now, write_json
except ImportError:
    from eval_support import ROOT, digest_json, load_cases, nonempty_string, utc_now, write_json


def require(condition, message):
    if not condition:
        raise ValueError(message)


def valid_turn(number, turns):
    require(type(number) is int and 1 <= number <= len(turns), "evidence references an invalid output turn")


def validate_evidence(item, turns):
    nonempty_string(item.get("reason"), "semantic reason")
    refs = item.get("input_refs")
    require(isinstance(refs, list) and refs, "review requires input evidence references")
    for ref in refs:
        nonempty_string(ref, "input reference")
    evidence = item.get("evidence", {})
    if evidence.get("type") == "quote":
        valid_turn(evidence.get("turn"), turns)
        quote = evidence.get("text")
        nonempty_string(quote, "evidence quote")
        require(quote in turns[evidence["turn"] - 1]["assistant"], "evidence quote does not occur in assistant output")
    elif evidence.get("type") == "absence":
        inspected = evidence.get("turns")
        require(isinstance(inspected, list) and inspected, "absence evidence requires inspected turns")
        require(len(set(inspected)) == len(inspected), "duplicate absence evidence turn")
        for number in inspected:
            valid_turn(number, turns)
        nonempty_string(evidence.get("observation"), "absence observation")
    else:
        raise ValueError("evidence must be a quote or a scoped absence")


def validate_completed_turns(sample, expected_turns):
    turns = sample.get("turns")
    require(isinstance(turns, list) and len(turns) == len(expected_turns), "completed sample turn count mismatch")
    for number, (turn, expected_user) in enumerate(zip(turns, expected_turns), 1):
        require(isinstance(turn, dict), "completed turn must be an object")
        require(type(turn.get("turn")) is int and turn["turn"] == number, "completed turn sequence mismatch")
        require(turn.get("user") == expected_user, "completed turn input mismatch")
        nonempty_string(turn.get("assistant"), "completed assistant output")


def score_run(run, cases, judgments):
    require(run.get("kind") == "behavior" and run.get("schema_version") == 1, "only behavior traces can be reviewed")
    require(judgments.get("schema_version") == 1, "unsupported judgment schema")
    require(judgments.get("run_id") == run.get("run_id"), "review run_id mismatch")
    trace_hash = digest_json(run)
    require(judgments.get("trace_sha256") == trace_hash, "review trace hash mismatch")
    case_by_id = {case["id"]: case for case in cases}
    selected_ids = run.get("case_ids", [])
    require(isinstance(selected_ids, list) and selected_ids and len(selected_ids) == len(set(selected_ids)), "invalid trace case IDs")
    require(all(case_id in case_by_id for case_id in selected_ids), "unknown trace case ID")
    selected = [case_by_id[case_id] for case_id in selected_ids]
    case_hash = digest_json(selected)
    require(run.get("cases_sha256") == case_hash and judgments.get("cases_sha256") == case_hash, "review cases/rubric hash mismatch")
    reviewer = judgments.get("reviewer", {})
    nonempty_string(reviewer.get("name"), "reviewer name")
    require(reviewer.get("type") in ("human", "agent-author", "independent-model"), "unsupported reviewer type")
    require(type(reviewer.get("independent")) is bool, "reviewer must disclose independence")
    require(not (reviewer["type"] == "agent-author" and reviewer["independent"]), "author review cannot be independent")
    repeats = run.get("repeats_requested")
    require(type(repeats) is int and repeats > 0, "repeats_requested must be a positive integer")
    samples = {}
    for sample in run.get("samples", []):
        key = (sample.get("case_id"), sample.get("sample_index"))
        require(key not in samples, "duplicate trace sample")
        require(key[0] in selected_ids and type(key[1]) is int and key[1] > 0, "invalid trace sample key")
        require(sample.get("status") in ("completed", "error", "not_run", "pending"), "invalid trace sample status")
        if sample["status"] == "completed":
            validate_completed_turns(sample, case_by_id[key[0]]["turns"])
        samples[key] = sample
    require(samples, "trace has no sample records")
    expected_samples = {(case_id, index) for case_id in selected_ids for index in range(1, repeats + 1)}
    require(set(samples) == expected_samples, "trace sample coverage mismatch")
    reviewed = {}
    critical_failures = 0
    reviews = judgments.get("reviews")
    require(isinstance(reviews, list), "reviews must be a list")
    for review in reviews:
        key = (review.get("case_id"), review.get("sample_index"))
        require(key not in reviewed, "duplicate sample review")
        require(key in samples, "review references an unknown sample")
        sample = samples[key]
        require(sample["status"] == "completed", "only completed samples can receive a behavior verdict")
        expected = {criterion["id"]: criterion for criterion in case_by_id[key[0]]["criteria"]}
        supplied = review.get("criteria")
        require(isinstance(supplied, list), "review criteria must be a list")
        identifiers = [item.get("id") for item in supplied]
        require(len(identifiers) == len(set(identifiers)), "duplicate criterion review")
        require(set(identifiers) == set(expected), "review criteria are incomplete or unknown")
        for item in supplied:
            require(item.get("verdict") in ("pass", "fail"), "criterion verdict must be pass or fail")
            validate_evidence(item, sample["turns"])
            if item["verdict"] == "fail" and expected[item["id"]]["critical"]:
                critical_failures += 1
        reviewed[key] = all(item["verdict"] == "pass" for item in supplied)
    completed = sum(sample["status"] == "completed" for sample in samples.values())
    errors = sum(sample["status"] == "error" for sample in samples.values())
    not_run = sum(sample["status"] == "not_run" for sample in samples.values())
    pending = len(samples) - completed - errors - not_run
    passed = sum(reviewed.values())
    failed = len(reviewed) - passed
    ungraded = completed - len(reviewed)
    if not completed:
        status = "not_evaluated"
    elif not reviewed:
        status = "ungraded"
    elif failed:
        status = "fail"
    elif ungraded or errors or not_run or pending:
        status = "partial"
    else:
        status = "pass"
    return {"schema_version": 1, "kind": "behavior-score", "created_utc": utc_now(), "run_id": run["run_id"], "trace_sha256": trace_hash, "cases_sha256": case_hash, "reviewer": reviewer, "status": status, "summary": {"completed_samples": completed, "error_samples": errors, "not_run_samples": not_run, "pending_samples": pending, "graded_samples": len(reviewed), "passed_samples": passed, "failed_samples": failed, "critical_criterion_failures": critical_failures, "ungraded_samples": ungraded, "pass_rate": passed / len(reviewed) if reviewed else None}, "reviews": reviews, "limitation": "Review integrity and aggregation only. Semantic verdicts are supplied by the disclosed reviewer; this is not automatic behavioral or tool-sandbox verification."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/cases.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new score filename")
    try:
        run = json.loads(args.run.read_text(encoding="utf-8"))
        judgments = json.loads(args.judgments.read_text(encoding="utf-8"))
        score = score_run(run, load_cases(args.cases), judgments)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    write_json(args.output, score)
    print(json.dumps({"kind": score["kind"], "status": score["status"], "summary": score["summary"]}, ensure_ascii=True))
    return 0 if score["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
