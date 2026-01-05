def test_claim_assigned_to_single_cluster(db_session, embedder):
    from app.db import assign_claim_to_cluster

    # Fake claims
    cid1 = 1
    cid2 = 2

    # Insert minimal rows
    db_session.execute("INSERT INTO claim (claim_id, claim_text, content_hash) VALUES (1,'a','ha')")
    db_session.execute("INSERT INTO claim (claim_id, claim_text, content_hash) VALUES (2,'b','hb')")
    db_session.commit()

    r1 = assign_claim_to_cluster(
        db_session,
        claim_id=cid1,
        best_match_claim_id=None,
        best_match_similarity=0.0,
        join_threshold=0.8,
    )

    r2 = assign_claim_to_cluster(
        db_session,
        claim_id=cid1,
        best_match_claim_id=cid2,
        best_match_similarity=0.9,
        join_threshold=0.8,
    )

    assert r1["cluster_id"] == r2["cluster_id"]
    assert r2["assigned"] is False

