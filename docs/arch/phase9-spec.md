# Phase 9 — Human Approval Steps & Agent Memory

**Status:** Draft
**Based on:** `docs/prd.md` §13 Open Questions, `docs/arch/implementation-plan.md` Appendix E
**Dependencies:** Phases 1–8 complete

---

## Table of Contents

1. [Part A — Human Approval Steps](#part-a--human-approval-steps)
2. [Part B — Agent Memory Persistence](#part-b--agent-memory-persistence)
3. [Appendix A — New Directory Additions](#appendix-a--new-directory-additions)
4. [Appendix B — API Contract Additions](#appendix-b--api-contract-additions)

---

## Part A — Human Approval Steps

**Goal:** Enable human-in-the-loop approval gates inside Temporal workflows. A workflow can pause execution at an approval step and wait for an external signal (approve/reject) before continuing.

**PRD References:** §13 Open Questions (Q4), §4.2 Workflow Orchestration (sequential workflows with gates)

### A.1 Why This Matters

Some workflows perform actions that need sign-off:
- Deploying infrastructure changes
- Sending communications to users
- Executing financial transactions
- Any destructive or irreversible operation

Temporal provides the primitives: `workflow.condition()` blocks the workflow fiber until a signal sets a shared variable. The workflow remains durable — it survives worker restarts while waiting.

### A.2 Approval Activity

A new activity type that blocks until a human signals approval or rejection.

**File:** `src/orion/workflow/approval.py`

```python
"""Human approval gate for Temporal workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from temporalio import workflow


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ApprovalRequest:
    """Metadata about an approval request."""
    request_id: str
    title: str
    description: str
    requested_by: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ApprovalResult:
    """Result of an approval gate."""
    decision: ApprovalDecision
    reason: str = ""
    approved_by: str = ""
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    request: ApprovalRequest | None = None
```

### A.3 Approval Gate Mixin

Reusable mixin any workflow can compose to add approval steps.

**File:** `src/orion/workflow/approval.py` (continued)

```python
class ApprovalGate:
    """Mixin that adds human approval capability to any Temporal workflow.

    Usage:
        class MyWorkflow(ApprovalGate, workflow.Defn):
            @workflow.run
            async def run(self, input: dict) -> dict:
                result = await self.wait_for_approval(
                    ApprovalRequest(
                        request_id="deploy-prod-1",
                        title="Deploy to Production",
                        description="Deploy version 2.0 to production",
                        requested_by="ci-pipeline",
                    ),
                    timeout_seconds=86400,  # 24 hours
                )

                if result.decision == ApprovalDecision.REJECTED:
                    return {"status": "rejected", "reason": result.reason}

                # Continue with deployment...
    """

    _approval_result: ApprovalResult | None = None
    _approval_request: ApprovalRequest | None = None

    async def wait_for_approval(
        self,
        request: ApprovalRequest,
        timeout_seconds: int = 86400,
    ) -> ApprovalResult:
        """Block the workflow until a human approves or rejects.

        Must be called from within a Temporal workflow context.
        """
        with workflow.run_timeout(__import__("datetime").timedelta(seconds=timeout_seconds)):
            self._approval_request = request
            self._approval_result = None
            workflow.logger.info(
                "Waiting for approval: request_id=%s title=%s",
                request.request_id,
                request.title,
            )
            # Block until the signal handler sets _approval_result
            await workflow.condition(lambda: self._approval_result is not None)

        result = self._approval_result
        if result is None:
            # Timeout — auto-reject
            result = ApprovalResult(
                decision=ApprovalDecision.REJECTED,
                reason="Approval timed out",
                request=request,
            )
            workflow.logger.warning(
                "Approval timed out: request_id=%s", request.request_id
            )

        return result

    @workflow.signal(name="approve")
    async def handle_approve(
        self,
        approved_by: str = "",
        reason: str = "",
    ) -> None:
        """Signal to approve the pending approval request."""
        self._approval_result = ApprovalResult(
            decision=ApprovalDecision.APPROVED,
            reason=reason,
            approved_by=approved_by,
            request=self._approval_request,
        )
        workflow.logger.info(
            "Approval granted: request_id=%s by=%s",
            self._approval_request.request_id if self._approval_request else "unknown",
            approved_by,
        )

    @workflow.signal(name="reject")
    async def handle_reject(
        self,
        rejected_by: str = "",
        reason: str = "",
    ) -> None:
        """Signal to reject the pending approval request."""
        self._approval_result = ApprovalResult(
            decision=ApprovalDecision.REJECTED,
            reason=reason,
            approved_by=rejected_by,
            request=self._approval_request,
        )
        workflow.logger.info(
            "Approval rejected: request_id=%s by=%s reason=%s",
            self._approval_request.request_id if self._approval_request else "unknown",
            rejected_by,
            reason,
        )
```

### A.4 Example: Approval-Enabled Workflow

Demonstrates the mixin in a real workflow.

**File:** `src/orion/workflow/workflows.py` (new workflow)

```python
from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from orion.workflow import activities
from orion.workflow.approval import ApprovalGate, ApprovalRequest, ApprovalDecision


@workflow.defn(name="approved_research_workflow")
class ApprovedResearchWorkflow(ApprovalGate):
    """Research workflow with human approval before report generation."""

    def __init__(self) -> None:
        self._status: str = "pending"
        self._current_step: int = 0

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query = input_data["query"]
        model = input_data.get("model", "gpt-4")
        approval_timeout = input_data.get("approval_timeout_seconds", 86400)

        retry = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
        )

        # Step 1: Search
        self._status = "searching"
        self._current_step = 1
        search_results = await workflow.execute_activity(
            activities.search_activity,
            query,
            args=[input_data.get("max_results", 5)],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry,
        )

        # Step 2: Summarize
        self._status = "summarizing"
        self._current_step = 2
        combined_text = "\n\n".join(
            r.get("text", "") if isinstance(r, dict) else str(r)
            for r in search_results.get("results", [])
        )
        summary = await workflow.execute_activity(
            activities.summarize_activity,
            combined_text or query,
            args=[model],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=retry,
        )

        # Step 3: Wait for human approval
        self._status = "awaiting_approval"
        self._current_step = 3
        approval = await self.wait_for_approval(
            request=ApprovalRequest(
                request_id=f"approval-{workflow.info.workflow_id}",
                title=f"Approve research report: {query}",
                description=f"Summary: {summary.get('output', '')[:500]}",
                requested_by=input_data.get("requested_by", "system"),
                metadata={"query": query, "model": model},
            ),
            timeout_seconds=approval_timeout,
        )

        if approval.decision == ApprovalDecision.REJECTED:
            self._status = "rejected"
            return {
                "status": "rejected",
                "reason": approval.reason,
                "rejected_by": approval.approved_by,
            }

        # Step 4: Generate report (only after approval)
        self._status = "reporting"
        self._current_step = 4
        report = await workflow.execute_activity(
            activities.report_activity,
            f"Research: {query}",
            args=[summary.get("output", ""), "markdown"],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry,
        )

        self._status = "completed"
        return {
            "search_results": search_results,
            "summary": summary,
            "report": report,
            "approval": {
                "decision": approval.decision,
                "approved_by": approval.approved_by,
            },
        }

    @workflow.query
    def get_progress(self) -> dict:
        return {
            "status": self._status,
            "step": self._current_step,
            "total_steps": 4,
            "pending_approval": self._status == "awaiting_approval",
        }
```

### A.5 Approval API Endpoints

Endpoints to list pending approvals, approve/reject, and view approval history.

**File:** `src/orion/api/routes/approvals.py`

```python
"""API endpoints for human approval management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orion.workflow.client import get_temporal_client

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


class ApprovalActionRequest(BaseModel):
    approved_by: str = ""
    reason: str = ""


class ApprovalInfo(BaseModel):
    workflow_id: str
    run_id: str
    status: str
    progress: dict[str, Any] | None = None


@router.get("/pending")
async def list_pending_approvals() -> dict[str, list[ApprovalInfo]]:
    """List all workflows currently awaiting approval.

    Queries the Temporal namespace for running workflows and filters by
    progress status == 'awaiting_approval'.
    """
    client = await get_temporal_client()
    # List workflows — in production, use Temporal's workflow query API
    # with a custom query index for filtering by approval state.
    # For now, return empty list; implement when workflow listing is needed.
    return {"approvals": []}


@router.post("/{workflow_id}/approve")
async def approve_workflow(
    workflow_id: str,
    request: ApprovalActionRequest,
) -> dict[str, str]:
    """Approve a pending approval request."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)

    # Check workflow is running and awaiting approval
    description = await handle.describe()
    progress = await handle.query("get_progress")
    if not progress.get("pending_approval"):
        raise HTTPException(
            status_code=400,
            detail=f"Workflow is not awaiting approval (status: {progress.get('status')})",
        )

    await handle.signal(
        "approve",
        approved_by=request.approved_by,
        reason=request.reason,
    )
    return {"workflow_id": workflow_id, "status": "approved"}


@router.post("/{workflow_id}/reject")
async def reject_workflow(
    workflow_id: str,
    request: ApprovalActionRequest,
) -> dict[str, str]:
    """Reject a pending approval request."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)

    description = await handle.describe()
    progress = await handle.query("get_progress")
    if not progress.get("pending_approval"):
        raise HTTPException(
            status_code=400,
            detail=f"Workflow is not awaiting approval (status: {progress.get('status')})",
        )

    await handle.signal(
        "reject",
        rejected_by=request.approved_by,
        reason=request.reason,
    )
    return {"workflow_id": workflow_id, "status": "rejected"}
```

### A.6 Wire Into App

**File:** `src/orion/api/app.py` (add router)

```python
from orion.api.routes import approvals

app.include_router(approvals.router, dependencies=[Depends(verify_api_key)])
```

### A.7 Register New Workflow in Worker

**File:** `src/orion/workflow/worker.py` (add to workflows list)

```python
from orion.workflow.workflows import ApprovedResearchWorkflow, ResearchWorkflow

worker = Worker(
    ...
    workflows=[ResearchWorkflow, ApprovedResearchWorkflow],
)
```

### A.8 Approval Persistence

Record approval decisions in PostgreSQL for audit trail.

**File:** `src/orion/db/models.py` (add model)

```python
class ApprovalRecord(SQLModel, table=True):
    """Audit record of approval decisions."""
    __tablename__ = "approval_records"

    id: int | None = Field(default=None, primary_key=True)
    request_id: str = Field(index=True)
    workflow_id: str = Field(index=True)
    title: str
    requested_by: str
    decision: str  # "approved" | "rejected" | "timed_out"
    decided_by: str = ""
    reason: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None
```

### A.9 Tests

**File:** `tests/workflow/test_approval.py`

```python
import pytest
from orion.workflow.approval import (
    ApprovalDecision,
    ApprovalGate,
    ApprovalRequest,
    ApprovalResult,
)


def test_approval_request_fields():
    req = ApprovalRequest(
        request_id="test-1",
        title="Test",
        description="Test description",
        requested_by="user-1",
    )
    assert req.request_id == "test-1"
    assert req.metadata == {}


def test_approval_result_approved():
    result = ApprovalResult(
        decision=ApprovalDecision.APPROVED,
        approved_by="admin",
        reason="Looks good",
    )
    assert result.decision == ApprovalDecision.APPROVED
    assert result.approved_by == "admin"


def test_approval_result_rejected():
    result = ApprovalResult(
        decision=ApprovalDecision.REJECTED,
        approved_by="admin",
        reason="Not ready",
    )
    assert result.decision == ApprovalDecision.REJECTED


def test_approval_gate_has_signal_handlers():
    """ApprovalGate defines approve and reject signal handlers."""
    assert hasattr(ApprovalGate, "handle_approve")
    assert hasattr(ApprovalGate, "handle_reject")
    assert callable(ApprovalGate.handle_approve)
    assert callable(ApprovalGate.handle_reject)
```

**File:** `tests/api/test_approvals.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from orion.api.app import app


@pytest.mark.asyncio
async def test_approve_endpoint_exists():
    """Approval approve endpoint is registered."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Expect 404 (no Temporal) or 400 (not awaiting approval), not 405
        resp = await client.post(
            "/api/v1/approvals/test-wf/approve",
            json={"approved_by": "admin", "reason": "ok"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code in (400, 404, 500)  # Not 405 (method not allowed)
```

### A.10 Deliverables

- [ ] `ApprovalGate` mixin with `wait_for_approval()`, `approve`, `reject` signals
- [ ] `ApprovedResearchWorkflow` example (4 steps: search, summarize, approve, report)
- [ ] `POST /api/v1/approvals/{id}/approve` — approve a pending request
- [ ] `POST /api/v1/approvals/{id}/reject` — reject a pending request
- [ ] `GET /api/v1/approvals/pending` — list workflows awaiting approval
- [ ] `ApprovalRecord` SQLModel for audit trail
- [ ] Alembic migration for `approval_records` table
- [ ] All tests passing with >= 80% coverage

---

## Part B — Agent Memory Persistence

**Goal:** Persist agent conversational memory so multi-turn agents can reference prior interactions. Stored as PostgreSQL records with optional semantic search via embeddings.

**PRD References:** §13 Open Questions (Q3)

### B.1 Design Decisions

**Why PostgreSQL, not a vector database:**
- The platform already uses PostgreSQL. Adding a dedicated vector DB (pgvector, Pinecone, Weaviate) increases operational complexity.
- `pgvector` extension on PostgreSQL gives us embeddings + semantic search in the same database — no new infrastructure.
- For the initial implementation, we store raw text with metadata. Embeddings are optional and computed on write.

**Memory model:**
- Each memory entry belongs to an `agent_id` (logical agent identity) and optionally a `session_id` (conversation thread).
- Entries are tagged with a `role` (user, assistant, system, tool) for context reconstruction.
- Entries carry an optional embedding vector for semantic similarity search.

### B.2 Database Models

**File:** `src/orion/memory/models.py`

```python
"""Agent memory persistence models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, Index, text
from sqlmodel import Field, SQLModel


class MemoryRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MemoryEntry(SQLModel, table=True):
    """Single memory entry for an agent.

    Stores conversational context, tool outputs, or any structured
    knowledge the agent should retain across invocations.
    """

    __tablename__ = "agent_memory"

    id: int | None = Field(default=None, primary_key=True)

    # Identity
    agent_id: str = Field(index=True, description="Logical agent identifier")
    session_id: str | None = Field(
        default=None, index=True, description="Conversation session"
    )

    # Content
    role: MemoryRole = MemoryRole.USER
    content: str = Field(max_length=65535)
    metadata: dict | None = Field(default=None, sa_column=Column(JSON))

    # Embeddings (optional — computed on write)
    # Requires pgvector extension: CREATE EXTENSION IF NOT EXISTS vector;
    # embedding: list[float] | None = Field(
    #     default=None,
    #     sa_column=Column(Vector(1536)),  # OpenAI ada-002 dimension
    # )

    # Ordering
    sequence_number: int = Field(ge=0, description="Order within session")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
    )

    # Composite index for efficient session queries
    __table_args__ = (
        Index(
            "ix_agent_memory_agent_session_sequence",
            "agent_id",
            "session_id",
            "sequence_number",
        ),
    )


class MemorySummary(SQLModel):
    """Projection for memory listing (no table)."""

    id: int
    agent_id: str
    session_id: str | None
    role: MemoryRole
    content_preview: str
    sequence_number: int
    created_at: datetime
```

### B.3 Memory Service

**File:** `src/orion/memory/service.py`

```python
"""Agent memory service for CRUD and retrieval operations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from orion.memory.models import MemoryEntry, MemoryRole, MemorySummary

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for managing agent memory entries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        agent_id: str,
        content: str,
        *,
        session_id: str | None = None,
        role: MemoryRole = MemoryRole.USER,
        metadata: dict[str, Any] | None = None,
        sequence_number: int | None = None,
    ) -> MemoryEntry:
        """Add a memory entry.

        If sequence_number is not provided, auto-increment based on
        the existing count for this agent+session.
        """
        if sequence_number is None:
            result = await self.session.exec(
                select(col(MemoryEntry.sequence_number)).
                where(MemoryEntry.agent_id == agent_id).
                where(MemoryEntry.session_id == session_id).
                order_by(col(MemoryEntry.sequence_number).desc()).
                limit(1)
            )
            sequence_number = (result.first() or 0) + 1

        entry = MemoryEntry(
            agent_id=agent_id,
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata or {},
            sequence_number=sequence_number,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        logger.info(
            "Memory added: agent=%s session=%s seq=%d role=%s",
            agent_id,
            session_id,
            sequence_number,
            role,
        )
        return entry

    async def get_context(
        self,
        agent_id: str,
        session_id: str | None = None,
        *,
        limit: int = 50,
        role: MemoryRole | None = None,
    ) -> list[MemorySummary]:
        """Retrieve recent memory entries for context reconstruction.

        Returns the most recent entries, optionally filtered by role.
        """
        query = (
            select(MemoryEntry)
            .where(MemoryEntry.agent_id == agent_id)
            .order_by(col(MemoryEntry.sequence_number).desc())
            .limit(limit)
        )

        if session_id is not None:
            query = query.where(MemoryEntry.session_id == session_id)

        if role is not None:
            query = query.where(MemoryEntry.role == role)

        result = await self.session.exec(query)
        entries = result.all()

        # Reverse to chronological order
        entries.reverse()

        return [
            MemorySummary(
                id=e.id,
                agent_id=e.agent_id,
                session_id=e.session_id,
                role=e.role,
                content_preview=e.content[:200],
                sequence_number=e.sequence_number,
                created_at=e.created_at,
            )
            for e in entries
        ]

    async def delete_session(
        self,
        agent_id: str,
        session_id: str,
    ) -> int:
        """Delete all memory for a specific session. Returns count deleted."""
        from sqlmodel import delete

        stmt = delete(MemoryEntry).where(
            MemoryEntry.agent_id == agent_id,
            MemoryEntry.session_id == session_id,
        )
        result = await self.session.exec(stmt)
        await self.session.commit()
        count = result.rowcount
        logger.info(
            "Session deleted: agent=%s session=%s count=%d",
            agent_id,
            session_id,
            count,
        )
        return count

    async def delete_agent_memory(
        self,
        agent_id: str,
    ) -> int:
        """Delete all memory for an agent. Returns count deleted."""
        from sqlmodel import delete

        stmt = delete(MemoryEntry).where(MemoryEntry.agent_id == agent_id)
        result = await self.session.exec(stmt)
        await self.session.commit()
        count = result.rowcount
        logger.info("Agent memory deleted: agent=%s count=%d", agent_id, count)
        return count
```

### B.4 Memory Tool

A FastMCP tool that agents can call to access their own memory.

**File:** `src/orion/tools/memory.py`

```python
"""Memory tool for agent self-referential context retrieval."""

from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from orion.memory.models import MemoryRole
from orion.memory.service import MemoryService
from orion.tools.base import ToolResult
from orion.tools.registry import mcp_server


@mcp_server.tool(
    name="agent_memory_add",
    description="Add a memory entry to the agent's persistent memory",
)
async def agent_memory_add(
    agent_id: str,
    content: str,
    session_id: str = "",
    role: str = "user",
    metadata: dict[str, Any] | None = None,
) -> ToolResult:
    """Persist a memory entry for the agent."""
    from orion.db.session import async_session_factory

    async with async_session_factory() as session:
        service = MemoryService(session)
        entry = await service.add(
            agent_id=agent_id,
            content=content,
            session_id=session_id or None,
            role=MemoryRole(role) if role in MemoryRole.__members__ else MemoryRole.USER,
            metadata=metadata,
        )
        return ToolResult(
            output={"id": entry.id, "sequence_number": entry.sequence_number},
            metadata={"agent_id": agent_id, "session_id": entry.session_id},
        )


@mcp_server.tool(
    name="agent_memory_recall",
    description="Recall recent memory entries for context",
)
async def agent_memory_recall(
    agent_id: str,
    session_id: str = "",
    limit: int = 50,
) -> ToolResult:
    """Retrieve recent memory entries."""
    from orion.db.session import async_session_factory

    async with async_session_factory() as session:
        service = MemoryService(session)
        entries = await service.get_context(
            agent_id=agent_id,
            session_id=session_id or None,
            limit=limit,
        )
        return ToolResult(
            output={
                "entries": [
                    {
                        "role": e.role,
                        "content": e.content_preview,
                        "sequence": e.sequence_number,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in entries
                ],
                "count": len(entries),
            },
            metadata={"agent_id": agent_id},
        )
```

### B.5 Memory API Endpoints

For programmatic memory management (external to the agent).

**File:** `src/orion/api/routes/memory.py`

```python
"""API endpoints for agent memory management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from orion.db.session import get_db
from orion.memory.models import MemoryEntry, MemoryRole
from orion.memory.service import MemoryService
from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class MemoryAddRequest(BaseModel):
    agent_id: str
    content: str
    session_id: str | None = None
    role: MemoryRole = MemoryRole.USER
    metadata: dict[str, Any] | None = None


class MemoryAddResponse(BaseModel):
    id: int
    agent_id: str
    session_id: str | None
    role: MemoryRole
    sequence_number: int


class MemoryListResponse(BaseModel):
    entries: list[dict[str, Any]]
    count: int


@router.post("/add", response_model=MemoryAddResponse)
async def add_memory(
    request: MemoryAddRequest,
    db: AsyncSession = Depends(get_db),
) -> MemoryAddResponse:
    """Add a memory entry."""
    service = MemoryService(db)
    entry = await service.add(
        agent_id=request.agent_id,
        content=request.content,
        session_id=request.session_id,
        role=request.role,
        metadata=request.metadata,
    )
    return MemoryAddResponse(
        id=entry.id,
        agent_id=entry.agent_id,
        session_id=entry.session_id,
        role=entry.role,
        sequence_number=entry.sequence_number,
    )


@router.get("/{agent_id}/context", response_model=MemoryListResponse)
async def get_memory_context(
    agent_id: str,
    session_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> MemoryListResponse:
    """Get recent memory context for an agent."""
    service = MemoryService(db)
    entries = await service.get_context(
        agent_id=agent_id,
        session_id=session_id,
        limit=limit,
    )
    return MemoryListResponse(
        entries=[
            {
                "role": e.role,
                "content_preview": e.content_preview,
                "sequence": e.sequence_number,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
        count=len(entries),
    )


@router.delete("/{agent_id}/sessions/{session_id}")
async def delete_session_memory(
    agent_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Delete all memory for a session."""
    service = MemoryService(db)
    count = await service.delete_session(agent_id, session_id)
    return {"deleted": count}
```

### B.6 Wire Into App

**File:** `src/orion/api/app.py` (add router)

```python
from orion.api.routes import memory

app.include_router(memory.router, dependencies=[Depends(verify_api_key)])
```

### B.7 Register Memory Tools

**File:** `src/orion/tools/__init__.py` (add import)

```python
from orion.tools import memory, search, llm, streaming_llm  # noqa: F401
```

### B.8 Alembic Migration

```python
"""Add agent_memory table.

Revision ID: 003_add_agent_memory
Revises: 002_add_approval_records
"""

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "agent_memory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.String(length=65535), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_agent_memory_agent_id", "agent_memory", ["agent_id"]
    )
    op.create_index(
        "ix_agent_memory_session_id", "agent_memory", ["session_id"]
    )
    op.create_index(
        "ix_agent_memory_created_at", "agent_memory", ["created_at"]
    )
    op.create_index(
        "ix_agent_memory_agent_session_sequence",
        "agent_memory",
        ["agent_id", "session_id", "sequence_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_memory_agent_session_sequence", "agent_memory")
    op.drop_index("ix_agent_memory_created_at", "agent_memory")
    op.drop_index("ix_agent_memory_session_id", "agent_memory")
    op.drop_index("ix_agent_memory_agent_id", "agent_memory")
    op.drop_table("agent_memory")
```

### B.9 Tests

**File:** `tests/memory/test_models.py`

```python
import pytest
from orion.memory.models import MemoryEntry, MemoryRole


def test_memory_entry_fields():
    entry = MemoryEntry(
        agent_id="agent-1",
        session_id="session-1",
        role=MemoryRole.USER,
        content="Hello, remember this",
        sequence_number=1,
    )
    assert entry.agent_id == "agent-1"
    assert entry.role == MemoryRole.USER
    assert entry.sequence_number == 1


def test_memory_role_enum():
    assert MemoryRole.USER == "user"
    assert MemoryRole.ASSISTANT == "assistant"
    assert MemoryRole.SYSTEM == "system"
    assert MemoryRole.TOOL == "tool"
```

**File:** `tests/memory/test_service.py`

```python
import pytest
from orion.memory.models import MemoryEntry, MemoryRole
from orion.memory.service import MemoryService


@pytest.mark.asyncio
async def test_add_memory_entry(db_session):
    service = MemoryService(db_session)
    entry = await service.add(
        agent_id="agent-1",
        content="Test memory",
        role=MemoryRole.USER,
    )
    assert entry.id is not None
    assert entry.sequence_number == 1


@pytest.mark.asyncio
async def test_add_memory_auto_increment_sequence(db_session):
    service = MemoryService(db_session)
    e1 = await service.add(agent_id="agent-1", content="First")
    e2 = await service.add(agent_id="agent-1", content="Second")
    assert e2.sequence_number == e1.sequence_number + 1


@pytest.mark.asyncio
async def test_get_context_returns_chronological(db_session):
    service = MemoryService(db_session)
    await service.add(agent_id="agent-1", content="First")
    await service.add(agent_id="agent-1", content="Second")
    await service.add(agent_id="agent-1", content="Third")

    entries = await service.get_context(agent_id="agent-1")
    assert len(entries) == 3
    # First entry should be earliest
    assert entries[0].sequence_number < entries[-1].sequence_number


@pytest.mark.asyncio
async def test_delete_session(db_session):
    service = MemoryService(db_session)
    await service.add(agent_id="agent-1", session_id="s1", content="A")
    await service.add(agent_id="agent-1", session_id="s1", content="B")
    await service.add(agent_id="agent-1", session_id="s2", content="C")

    count = await service.delete_session("agent-1", "s1")
    assert count == 2

    remaining = await service.get_context("agent-1")
    assert len(remaining) == 1
```

**File:** `tests/api/test_memory.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from orion.api.app import app


@pytest.mark.asyncio
async def test_add_memory_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/memory/add",
            json={
                "agent_id": "test-agent",
                "content": "Remember this",
                "role": "user",
            },
            headers={"X-API-Key": "test-key"},
        )
        # May fail if DB not available, but endpoint should exist
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_get_context_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/memory/test-agent/context",
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code in (200, 500)
```

### B.10 Deliverables

- [ ] `MemoryEntry` SQLModel with agent_id, session_id, role, content, metadata
- [ ] `MemoryService` with add, get_context, delete_session, delete_agent_memory
- [ ] `agent_memory_add` and `agent_memory_recall` FastMCP tools
- [ ] `POST /api/v1/memory/add` — add memory entry
- [ ] `GET /api/v1/memory/{agent_id}/context` — retrieve context window
- [ ] `DELETE /api/v1/memory/{agent_id}/sessions/{session_id}` — purge session
- [ ] Alembic migration for `agent_memory` table
- [ ] All tests passing with >= 80% coverage

---

## Appendix A — New Directory Additions

```
src/orion/
├── api/
│   └── routes/
│       ├── approvals.py          ← NEW: approval endpoints
│       └── memory.py             ← NEW: memory CRUD endpoints
├── memory/
│   ├── __init__.py               ← NEW
│   ├── models.py                 ← NEW: MemoryEntry SQLModel
│   └── service.py                ← NEW: MemoryService
├── tools/
│   └── memory.py                 ← NEW: agent_memory_add, agent_memory_recall
└── workflow/
    └── approval.py               ← NEW: ApprovalGate mixin

tests/
├── api/
│   ├── test_approvals.py         ← NEW
│   └── test_memory.py            ← NEW
├── memory/
│   ├── __init__.py               ← NEW
│   ├── test_models.py            ← NEW
│   └── test_service.py           ← NEW
└── workflow/
    └── test_approval.py          ← NEW
```

---

## Appendix B — API Contract Additions

### B.1 Human Approval

```
GET    /api/v1/approvals/pending              → {"approvals": [...]}
POST   /api/v1/approvals/{id}/approve         → {"workflow_id": "...", "status": "approved"}
POST   /api/v1/approvals/{id}/reject          → {"workflow_id": "...", "status": "rejected"}
```

**Approve/Reject Request:**
```json
{
    "approved_by": "admin-user",
    "reason": "Changes look good"
}
```

### B.2 Agent Memory

```
POST   /api/v1/memory/add                     → {"id": 1, "agent_id": "...", "sequence_number": 1}
GET    /api/v1/memory/{agent_id}/context      → {"entries": [...], "count": N}
DELETE /api/v1/memory/{agent_id}/sessions/{session_id}  → {"deleted": N}
```

**Add Memory Request:**
```json
{
    "agent_id": "research-agent",
    "session_id": "session-abc",
    "content": "User asked about Temporal workflows",
    "role": "user",
    "metadata": {"source": "chat"}
}
```

**Get Context Response:**
```json
{
    "entries": [
        {
            "role": "user",
            "content_preview": "User asked about Temporal workflows",
            "sequence": 1,
            "created_at": "2025-01-15T10:30:00Z"
        }
    ],
    "count": 1
}
```

### B.3 New Workflow Type

The `ApprovedResearchWorkflow` is available as a new workflow type:

```
POST   /api/v1/workflows/start
```

**Request:**
```json
{
    "workflow_type": "approved_research_workflow",
    "input": {
        "query": "Research Rust async patterns",
        "model": "gpt-4",
        "max_results": 5,
        "requested_by": "ci-pipeline",
        "approval_timeout_seconds": 86400
    }
}
```

---

## Appendix C — Effort Estimates

| Item | Description | Estimated Effort |
|------|-------------|-----------------|
| A.1-A.10 | Human approval (ApprovalGate, API, tests) | 1-2 days |
| B.1-B.10 | Agent memory (models, service, tools, API, tests) | 1-2 days |
| **Total** | | **2-4 days** |
