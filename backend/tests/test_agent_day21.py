import json
import uuid

import pytest
from sqlalchemy import delete

from app.db.session import async_session
from app.models.agent_conversation import AgentConversation
from app.rag.generation import GroundedAnswer
from app.rag.retrieval import RetrievedChunk


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        event = "message"
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").lstrip())
        if data_lines:
            events.append((event, json.loads("\n".join(data_lines))))
    return events


async def remove_conversation(events: list[tuple[str, dict]]) -> None:
    meta = next(data for event, data in events if event == "meta")
    async with async_session() as db:
        await db.execute(
            delete(AgentConversation).where(
                AgentConversation.id == uuid.UUID(meta["conversation_id"])
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_stream_endpoint_requires_authentication(client):
    response = await client.post(
        "/api/v1/agent/chat/stream", json={"message": "Hello assistant"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_stream_endpoint_emits_ordered_answer_events(client, employee_token):
    response = await client.post(
        "/api/v1/agent/chat/stream",
        json={"message": "Hello assistant"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    names = [event for event, _ in events]
    assert names[0:2] == ["meta", "status"]
    assert "token" in names
    assert names[-1] == "done"
    answer = "".join(data["text"] for event, data in events if event == "token")
    assert "company policies" in answer.lower()
    assert events[-1][1]["intent"] == "general"
    await remove_conversation(events)


@pytest.mark.asyncio
async def test_stream_endpoint_emits_tool_result(client, employee_token):
    response = await client.post(
        "/api/v1/agent/chat/stream",
        json={"message": "How many leaves do I have left?"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )

    events = parse_sse(response.text)
    tool = next(data for event, data in events if event == "tool")
    assert tool["agent"] == "database"
    assert tool["tool"] == "get_leave_balance"
    assert tool["status"] == "success"
    assert isinstance(tool["data"]["balances"], list)
    await remove_conversation(events)


@pytest.mark.asyncio
async def test_stream_endpoint_emits_policy_sources(
    client, employee_token, monkeypatch
):
    document_id = uuid.uuid4()
    chunk = RetrievedChunk(
        document_id=document_id,
        title="WFH Policy",
        category="policy",
        chunk_index=1,
        page_number=3,
        content="Employees may work remotely two days each week.",
        cosine_distance=0.1,
    )

    async def fake_retrieve(db, question):
        return [chunk]

    async def fake_generate(question, chunks, **kwargs):
        return GroundedAnswer(answer="Two remote days are allowed.", source_numbers=[1])

    monkeypatch.setattr(
        "app.agent.nodes.rag_agent.retrieve_policy_chunks", fake_retrieve
    )
    monkeypatch.setattr(
        "app.agent.nodes.rag_agent.generate_grounded_answer", fake_generate
    )
    response = await client.post(
        "/api/v1/agent/chat/stream",
        json={"message": "What is the WFH policy?"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )

    events = parse_sse(response.text)
    sources = next(data["items"] for event, data in events if event == "sources")
    assert sources[0]["document_id"] == str(document_id)
    assert sources[0]["page_number"] == 3
    assert events[-1][1]["intent"] == "rag"
    await remove_conversation(events)
