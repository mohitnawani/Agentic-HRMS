# RAG evaluation

`rag_questions.json` is the Day 16 benchmark derived from the currently
uploaded 12-page Agentic HRMS project document. It contains eight supported
questions and two questions whose answers are absent from the document.

Run the evaluation from `backend`:

```powershell
.\venv-hrms\Scripts\python.exe -m app.rag.evaluation
```

For machine-readable output:

```powershell
.\venv-hrms\Scripts\python.exe -m app.rag.evaluation --json
```

An answerable case passes only when:

1. retrieval includes the expected page and evidence terms;
2. the generated answer contains the expected facts; and
3. at least one model citation points to that evidence.

An unsupported case passes only when the exact safe fallback is returned with
no citations. The command exits successfully when at least 8 of 10 cases pass.

The initial `top_k=5` baseline scored 8/10. The structured database evidence
ranked seventh for its question, so `top_k` was increased to 7 without changing
the `0.45` maximum cosine-distance threshold. The tuned run scored 10/10.

Update this dataset whenever the evaluated policy documents change. Do not
weaken expected evidence or answer terms merely to improve the score.

## Agent intent evaluation

`agent_intents.json` is the deterministic Day 20 routing benchmark. Run it
from `backend` with:

```powershell
.\venv-hrms\Scripts\python.exe -m app.agent.evaluation
```

The command succeeds when at least 8 of the 10 prompts route to the expected
RAG, database, action, or general path.
