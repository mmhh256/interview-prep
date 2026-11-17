"""Synthetic v2: lexical is accepted for compatibility but no longer called."""


def hybrid_search(query, dense, lexical, min_score=0.72):
    hits = dense(query)
    best = {}
    for hit in hits:
        if hit["score"] >= min_score:
            doc_id = hit["doc_id"]
            if doc_id not in best or hit["score"] > best[doc_id]["score"]:
                best[doc_id] = dict(hit)
    return sorted(best.values(), key=lambda item: item["score"], reverse=True)
