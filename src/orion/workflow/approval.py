"""Human approval gate for Temporal workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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


class ApprovalGate:
    """Mixin that adds human approval capability to any Temporal workflow.

    Usage:
        class MyWorkflow(ApprovalGate):
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
        with workflow.run_timeout(timedelta(seconds=timeout_seconds)):
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
