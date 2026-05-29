from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from orion.workflow import activities
from orion.workflow.approval import ApprovalDecision, ApprovalGate, ApprovalRequest


@workflow.defn(name="research_workflow")
class ResearchWorkflow:
    """Multi-step research workflow: search, summarize, report."""

    def __init__(self) -> None:
        self._status: str = "pending"
        self._current_step: int = 0
        self._cancelled: bool = False

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query = input_data["query"]
        model = input_data.get("model", "gpt-4")
        max_results = input_data.get("max_results", 5)

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
            args=[max_results],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry,
        )

        if self._cancelled:
            return {"status": "cancelled", "step": 1}

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

        if self._cancelled:
            return {"status": "cancelled", "step": 2}

        # Step 3: Generate report
        self._status = "reporting"
        self._current_step = 3
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
        }

    @workflow.signal(name="cancel_request")
    async def handle_cancel(self) -> None:
        """Handle external cancellation signal."""
        workflow.logger.info("Cancellation requested via signal")
        self._cancelled = True

    @workflow.query
    def get_progress(self) -> dict:
        """Query current workflow progress without blocking."""
        return {
            "status": self._status,
            "step": self._current_step,
            "total_steps": 3,
        }


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
