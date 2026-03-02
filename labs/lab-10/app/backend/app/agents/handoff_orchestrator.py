"""Handoff orchestrator for Lab 10 — Multi-agent workflow with checkpointing.

This module implements the core multi-agent orchestration using the
Agent Framework's built-in ``HandoffBuilder`` workflow.

Architecture
~~~~~~~~~~~~
::

    TriageAgent
      ├─ handoff_to_AccountAgent
      ├─ handoff_to_TransactionHistoryAgent
      └─ handoff_to_PaymentAgent

    Each specialist has a ``handoff_to_TriageAgent`` tool to route
    unrelated questions back to triage.

Key classes:

``CustomHandoffAgentExecutor``
    Prevents duplicate handoff tools when ``HandoffBuilder`` tries
    to inject them automatically — our agents already declare their
    handoff tools in ``default_options["tools"]``.

``CustomHandoffBuilder``
    Uses ``CustomHandoffAgentExecutor`` instead of the default executor.

``HandoffOrchestrator``
    Manages workflow lifecycle, per-thread checkpointing, message
    routing, and tool-approval responses.
"""

import logging
from collections.abc import AsyncIterable, Sequence
from typing import Any, AsyncGenerator

from agent_framework import (
    Agent,
    AgentResponseUpdate,
    CheckpointStorage,
    Content,
    FunctionTool,
    InMemoryCheckpointStorage,
    WorkflowCheckpoint,
    WorkflowEvent,
    tool,
    SupportsAgentRun,
)
from agent_framework.azure import AzureAIClient
from agent_framework.exceptions import AgentFrameworkException
from agent_framework.orchestrations import (
    HandoffAgentExecutor,
    HandoffAgentUserRequest,
    HandoffBuilder,
    HandoffConfiguration,
)

from app.agents.account_agent import AccountAgent
from app.agents.payment_agent import PaymentAgent
from app.agents.transaction_agent import TransactionHistoryAgent

logger = logging.getLogger(__name__)


# ── Handoff tools ─────────────────────────────────────────────────────
# Defined at module level.  Azure AI Agents require tools to be
# declared at agent-creation time (server-side), so we create them
# here and pass them during ``Agent()`` construction.  The
# ``HandoffBuilder`` middleware intercepts these tool calls at runtime
# to perform the actual routing.

@tool(
    name="handoff_to_TriageAgent",
    description="Handoff to the triage-agent agent.",
)
def handoff_to_triage_agent(context: str | None = None) -> str:
    """Transfer the conversation back to the triage agent."""
    return "Handoff to TriageAgent"


@tool(
    name="handoff_to_AccountAgent",
    description="Handoff to the account-agent agent.",
)
def handoff_to_account_agent(context: str | None = None) -> str:
    """Transfer the conversation to the account agent."""
    return "Handoff to AccountAgent"


@tool(
    name="handoff_to_TransactionHistoryAgent",
    description="Handoff to the transaction-history-agent agent.",
)
def handoff_to_transaction_history_agent(context: str | None = None) -> str:
    """Transfer the conversation to the transaction history agent."""
    return "Handoff to TransactionHistoryAgent"


@tool(
    name="handoff_to_PaymentAgent",
    description="Handoff to the payment-agent agent.",
)
def handoff_to_payment_agent(context: str | None = None) -> str:
    """Transfer the conversation to the payment agent."""
    return "Handoff to PaymentAgent"


# ── Custom executor ──────────────────────────────────────────────────

class CustomHandoffAgentExecutor(HandoffAgentExecutor):
    """Executor that avoids injecting duplicate handoff tools.

    Our specialist agents already declare their handoff tools (e.g.
    ``handoff_to_TriageAgent``) in ``agent.default_options["tools"]``.
    The default executor would add *another* copy for each handoff
    target, confusing the model.  This override detects existing tools
    and skips duplicates.
    """

    def _apply_auto_tools(
        self, agent: Agent, targets: Sequence[HandoffConfiguration]
    ) -> None:
        default_options = agent.default_options
        existing_tools = list(default_options.get("tools") or [])
        existing_names = {
            getattr(t, "name", "")
            for t in existing_tools
            if hasattr(t, "name")
        }

        new_tools: list[FunctionTool[Any]] = []
        for target in targets:
            handoff_tool = self._create_handoff_tool(
                target.target_id, target.description
            )
            if handoff_tool.name in existing_names:
                continue  # already present — skip
            new_tools.append(handoff_tool)

        default_options["tools"] = existing_tools + new_tools  # type: ignore[operator]


# ── Custom builder ───────────────────────────────────────────────────

class CustomHandoffBuilder(HandoffBuilder):
    """Builder that wires ``CustomHandoffAgentExecutor`` into the workflow."""

    def _resolve_executors(
        self,
        agents: dict[str, SupportsAgentRun],
        handoffs: dict[str, list[HandoffConfiguration]],
    ) -> dict[str, HandoffAgentExecutor]:
        executors: dict[str, HandoffAgentExecutor] = {}

        for agent_id, agent in agents.items():
            resolved_id = self._resolve_to_id(agent)
            autonomous_mode = self._autonomous_mode and (
                not self._autonomous_mode_enabled_agents
                or agent_id in self._autonomous_mode_enabled_agents
            )

            executors[resolved_id] = CustomHandoffAgentExecutor(
                agent=agent,
                handoffs=handoffs.get(resolved_id, []),
                is_start_agent=(agent_id == self._start_id),
                termination_condition=self._termination_condition,
                autonomous_mode=autonomous_mode,
                autonomous_mode_prompt=self._autonomous_mode_prompts.get(
                    agent_id, None
                ),
                autonomous_mode_turn_limit=self._autonomous_mode_turn_limits.get(
                    agent_id, None
                ),
            )

        return executors


# ── Orchestrator ─────────────────────────────────────────────────────

class HandoffOrchestrator:
    """Multi-agent handoff orchestrator with per-thread checkpointing.

    The orchestrator lazily initialises on the first message because
    building agent instances is ``async`` (MCP tool setup).  After that,
    each thread receives its own ``InMemoryCheckpointStorage`` so
    conversations can be resumed independently.
    """

    triage_instructions = """
    You are a banking customer support agent triaging customer requests
    about their banking account, movements, and payments.

    Evaluate the **entire** conversation and hand off to the correct
    specialist using the triage rules below.

    # Triage rules
    - Account information (balance, payment methods, cards, beneficiaries)
      → call handoff_to_AccountAgent
    - Banking movements and transaction history
      → call handoff_to_TransactionHistoryAgent
    - Initiate a payment, upload a bill/invoice, or manage an ongoing
      payment process → call handoff_to_PaymentAgent
    - If the request is unrelated to account, transactions, or payments,
      respond that you cannot help with that topic.
    """

    # Per-thread checkpoint stores.  In production replace with a
    # persistent backend (database, Redis, etc.).
    thread_checkpoint_store: dict[str, CheckpointStorage] = {}

    def __init__(
        self,
        azure_ai_client: AzureAIClient,
        account_agent: AccountAgent,
        transaction_agent: TransactionHistoryAgent,
        payment_agent: PaymentAgent,
    ):
        self.azure_ai_client = azure_ai_client
        self.account_agent = account_agent
        self.transaction_agent = transaction_agent
        self.payment_agent = payment_agent
        self.workflow = None  # built lazily in ``initialize()``

    # ── Lazy async init ──────────────────────────────────────────────

    async def initialize(self, checkpoint_storage: CheckpointStorage) -> None:
        """Build all agents and assemble the handoff workflow."""
        logger.info("Initialising HandoffOrchestrator workflow …")

        # Triage agent — no domain tools, just 3 handoff functions.
        triage_agent = Agent(
            client=self.azure_ai_client,
            instructions=HandoffOrchestrator.triage_instructions,
            name="TriageAgent",
            tools=[
                handoff_to_account_agent,
                handoff_to_transaction_history_agent,
                handoff_to_payment_agent,
            ],
        )
        triage_agent.default_options["tools"] = [
            handoff_to_account_agent,
            handoff_to_transaction_history_agent,
            handoff_to_payment_agent,
        ]

        # Specialist agents — each exposes its own tools + handoff_to_triage
        account_agent = await self.account_agent.build_af_agent()
        transaction_agent = await self.transaction_agent.build_af_agent()
        payment_agent = await self.payment_agent.build_af_agent()

        # Assemble the handoff workflow
        self.workflow = (
            CustomHandoffBuilder(
                name="banking_assistant_handoff",
                participants=[
                    triage_agent,
                    account_agent,
                    transaction_agent,
                    payment_agent,
                ],
            )
            .with_start_agent(triage_agent)
            .add_handoff(
                triage_agent,
                [account_agent, transaction_agent, payment_agent],
            )
            .add_handoff(account_agent, [triage_agent])
            .add_handoff(transaction_agent, [triage_agent])
            .add_handoff(payment_agent, [triage_agent])
            .with_termination_condition(
                # Terminate after 20 user messages (don't count agent responses)
                lambda conv: sum(1 for msg in conv if msg.role == "user") >= 20
            )
            .with_checkpointing(checkpoint_storage)
            .build()
        )
        logger.info("HandoffOrchestrator workflow initialised")

    # ── Checkpoint helpers ───────────────────────────────────────────

    async def _get_or_create_checkpoint_store(
        self, thread_id: str
    ) -> CheckpointStorage:
        store = HandoffOrchestrator.thread_checkpoint_store.get(thread_id)
        if store is not None:
            return store
        logger.info("Creating new checkpoint storage for thread %s", thread_id)
        store = InMemoryCheckpointStorage()
        HandoffOrchestrator.thread_checkpoint_store[thread_id] = store
        return store

    async def _resume_workflow_with_response(
        self,
        checkpoint_storage: CheckpointStorage,
        checkpoint_id: str,
        user_message: str,
    ) -> AsyncIterable[WorkflowEvent]:
        """Resume a workflow that is blocking on ``HandoffAgentUserRequest``."""
        events = self.workflow.run(  # type: ignore[union-attr]
            checkpoint_id=checkpoint_id,
            checkpoint_storage=checkpoint_storage,
            stream=True,
        )

        # Consume all events to locate the ``request_info`` event.
        consumed_events = [event async for event in events]
        for event in consumed_events:
            if event.type == "request_info":
                if isinstance(event.data, HandoffAgentUserRequest):
                    responses: dict[str, object] = {
                        event.request_id: HandoffAgentUserRequest.create_response(
                            user_message
                        )
                    }
                    return self.workflow.run(  # type: ignore[union-attr]
                        responses=responses,
                        checkpoint_id=checkpoint_id,
                        checkpoint_storage=checkpoint_storage,
                        stream=True,
                    )
                raise AgentFrameworkException(
                    f"RequestInfoEvent [{event.request_id}] in checkpoint "
                    f"[{checkpoint_id}] is not a HandoffAgentUserRequest."
                )

        raise AgentFrameworkException(
            f"No RequestInfoEvent found in checkpoint [{checkpoint_id}]"
        )

    # ── Public API ───────────────────────────────────────────────────

    async def processMessageStream(
        self, user_message: str, thread_id: str
    ) -> AsyncGenerator[WorkflowEvent, None]:
        """Stream workflow events for a new user message."""

        checkpoint_storage = await self._get_or_create_checkpoint_store(thread_id)

        # Lazy init — MCP connections require async setup.
        if self.workflow is None:
            await self.initialize(checkpoint_storage)

        checkpoint = await checkpoint_storage.get_latest(
            workflow_name=self.workflow.name  # type: ignore[union-attr]
        )

        if checkpoint is None:
            # First message — start a new conversation.
            async for event in self.workflow.run(user_message, stream=True):  # type: ignore[union-attr]
                yield event
        else:
            # Subsequent message — resume from checkpoint.
            async for event in await self._resume_workflow_with_response(
                checkpoint_storage, checkpoint.checkpoint_id, user_message
            ):
                yield event

    async def processToolApprovalResponse(
        self,
        thread_id: str,
        approved: bool,
        call_id: str,
        request_id: str,
        tool_name: str,
    ) -> AsyncGenerator[WorkflowEvent, None]:
        """Resume the workflow with a human approval / rejection decision."""

        checkpoint_storage = await self._get_or_create_checkpoint_store(thread_id)

        if self.workflow is None:
            await self.initialize(checkpoint_storage)

        checkpoint = await checkpoint_storage.get_latest(
            workflow_name=self.workflow.name  # type: ignore[union-attr]
        )
        if checkpoint is None:
            raise AgentFrameworkException(
                f"No checkpoint found for thread_id: {thread_id} "
                "when trying to process tool approval response"
            )

        # Restart the workflow from the checkpoint to recover the
        # ``function_approval_request`` event reference.
        events = self.workflow.run(  # type: ignore[union-attr]
            checkpoint_id=checkpoint.checkpoint_id,
            checkpoint_storage=checkpoint_storage,
            stream=True,
        )

        responses: dict[str, object] = {}
        consumed_events = [event async for event in events]
        for event in consumed_events:
            yield event
            if event.type == "request_info":
                if (
                    isinstance(event.data, Content)
                    and event.data.type == "function_approval_request"
                ):
                    responses[event.request_id] = (
                        event.data.to_function_approval_response(approved=approved)
                    )
                    async for resumed_event in self.workflow.run(  # type: ignore[union-attr]
                        responses=responses,
                        checkpoint_id=checkpoint.checkpoint_id,
                        checkpoint_storage=checkpoint_storage,
                        stream=True,
                    ):
                        yield resumed_event
                else:
                    raise AgentFrameworkException(
                        f"RequestInfoEvent [{event.request_id}] in checkpoint "
                        f"[{checkpoint.checkpoint_id}] is not a "
                        "function_approval_request."
                    )
