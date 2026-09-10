import asyncio
import uuid

from backend.infrastructure.database import database_engine
from sqlalchemy import text

from backend.domain.analyzer.services.vector_db import _get_embedding, search_similar_logs, add_solution
from backend.domain.analyzer.models.vector import VectorKnowledge


async def smoke():
    await database_engine.initialize()
    sm = database_engine.get_session_maker()

    # 1. Verify migration: column is VECTOR(384)
    async with sm() as session:
        r = await session.execute(text("SELECT atttypmod FROM pg_attribute WHERE attrelid='ai_knowledge'::regclass AND attname='embedding'"))
        dim = r.scalar()
        print(f"Migration check: ai_knowledge.embedding atttypmod = {dim}")
        assert dim == 384, f"Expected 384, got {dim}"

    # 2. Generate embedding with fastembed (should be 384-dim)
    emb = _get_embedding("Windows Event ID 4625 failed logon brute force detected")
    print(f"fastembed embedding dim = {len(emb)}")
    assert len(emb) == 384, f"Expected 384, got {len(emb)}"

    # 3. Insert + search round-trip
    test_event_id = f"TEST-{uuid.uuid4().hex[:8]}"
    async with sm() as session:
        async with session.begin():
            row = VectorKnowledge(
                event_id=test_event_id,
                description="Test brute force detection pattern",
                embedding=emb,
                solution_json={"solution": "block source IP"},
                feedback_score=1,
            )
            session.add(row)
        # Search back
        matches = await search_similar_logs(session, "brute force IP block", top_k=1)
        print(f"Round-trip search returned {len(matches)} match(es)")
        assert len(matches) >= 1, "Expected at least 1 match"
        assert matches[0]["solution"] == "block source IP"

    # 4. Verify cross-dimensional safety (bad 768-dim vector must fail)
    bad_emb = [0.0] * 768
    try:
        async with sm() as session:
            async with session.begin():
                session.add(VectorKnowledge(event_id="BAD-768", description="Should fail", embedding=bad_emb))
        print("ERROR: 768-dim vector was accepted (expected rejection)")
    except Exception as e:
        print(f"768-dim insert correctly rejected: {type(e).__name__}")

    await database_engine.close()
    print("RAG SMOKE TEST PASSED")


asyncio.run(smoke())
