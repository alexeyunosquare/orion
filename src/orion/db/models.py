from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


class WorkflowStatus(StrEnum):
    """Status of a workflow or activity execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionRequest(SQLModel, table=True):
    """Persisted record of each tool/workflow invocation."""

    __tablename__ = "execution_requests"

    id: int | None = Field(default=None, primary_key=True)
    correlation_id: str = Field(index=True, unique=True)
    workflow_id: str | None = Field(default=None, index=True)
    tool_name: str | None = None
    input_data: dict | None = Field(default=None, sa_column=Column(JSON))
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    activities: list["ActivityRecord"] = Relationship(back_populates="request")
    outputs: list["ExecutionOutput"] = Relationship(back_populates="request")


class ActivityRecord(SQLModel, table=True):
    """Individual activity execution within a workflow."""

    __tablename__ = "activity_records"

    id: int | None = Field(default=None, primary_key=True)
    request_id: int = Field(foreign_key="execution_requests.id")
    activity_type: str
    attempt: int = 1
    status: WorkflowStatus = WorkflowStatus.PENDING
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    request: ExecutionRequest | None = Relationship(back_populates="activities")


class ExecutionOutput(SQLModel, table=True):
    """Final output of an execution."""

    __tablename__ = "execution_outputs"

    id: int | None = Field(default=None, primary_key=True)
    request_id: int = Field(foreign_key="execution_requests.id")
    output_data: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    request: ExecutionRequest | None = Relationship(back_populates="outputs")


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
