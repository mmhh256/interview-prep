"""Synthetic, self-contained source for interview regression cases.

No authorship or production metrics can be inferred from this file.
"""


def hybrid_search(query, dense, lexical, min_score=0.72):
    dense_hits = dense(query)
    lexical_hits = lexical(query)
    best = {}
    for hit in dense_hits + lexical_hits:
        if hit["score"] < min_score:
            continue
        doc_id = hit["doc_id"]
        if doc_id not in best or hit["score"] > best[doc_id]["score"]:
            best[doc_id] = dict(hit)
    return sorted(best.values(), key=lambda item: item["score"], reverse=True)


def build_context(hits):
    return "\n".join(hit["text"] for hit in hits)


if __name__ == "__main__":
    calls = []

    def dense(query):
        calls.append("dense")
        return [{"doc_id": "a", "score": 0.80, "text": "A"},
                {"doc_id": "b", "score": 0.60, "text": "B"}]

    def lexical(query):
        calls.append("lexical")
        return [{"doc_id": "a", "score": 0.90, "text": "A2"},
                {"doc_id": "c", "score": 0.75, "text": "C"}]

    results = hybrid_search("sample", dense, lexical)
    print("calls:", calls)
    print("results:", [(hit["doc_id"], hit["score"]) for hit in results])
    print("context:", build_context(results))
