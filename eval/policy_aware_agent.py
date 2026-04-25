"""Policy-Aware Agent — Act IV mechanism for τ²-Bench.

Addresses two failure modes identified in Act III:
1. Authentication never checked (Probe 7.1, 100% trigger rate)
2. Reasoning loops consuming steps without tool calls (Probe 6.2, 60% trigger rate)

Mechanism: Enhanced system prompt that explicitly front-loads authentication
requirements and enforces action-oriented behavior per turn.
"""

from typing import List, Optional

from tau2.agent.base_agent import HalfDuplexAgent, ValidAgentInputMessage
from tau2.agent.llm_agent import LLMAgentState
from tau2.data_model.message import (
    APICompatibleMessage,
    AssistantMessage,
    Message,
    MultiToolMessage,
    SystemMessage,
    UserMessage,
)
from tau2.environment.toolkit import Tool
from tau2.utils.llm_utils import generate

POLICY_AWARE_INSTRUCTION = """\
You are a customer service agent that helps the user according to the <policy> provided below.
In each turn you can either:
- Send a message to the user.
- Make a tool call.
You cannot do both at the same time.

IMPORTANT RULES:
1. AUTHENTICATE FIRST: Before any account action, verify the user's identity by looking them up (name+zip or email). Never skip authentication.
2. CONFIRM BEFORE CHANGES: Before modifying orders, canceling, or exchanging, state what you will do and get user confirmation.
3. FOLLOW POLICY EXACTLY: Apply all policy rules strictly — return windows, non-returnable items, refund methods.

Always make sure you generate valid JSON only.
""".strip()

SYSTEM_PROMPT = """\
<instructions>
{agent_instruction}
</instructions>
<policy>
{domain_policy}
</policy>
""".strip()


class PolicyAwareAgent(HalfDuplexAgent[LLMAgentState]):
    """An LLM agent with enhanced policy adherence and action discipline."""

    def __init__(
        self,
        tools: List[Tool],
        domain_policy: str,
        llm: str,
        llm_args: Optional[dict] = None,
    ):
        super().__init__(tools=tools, domain_policy=domain_policy)
        self.llm = llm
        self.llm_args = llm_args or {}

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT.format(
            domain_policy=self.domain_policy,
            agent_instruction=POLICY_AWARE_INSTRUCTION,
        )

    def get_init_state(
        self, message_history: Optional[list[Message]] = None
    ) -> LLMAgentState:
        if message_history is None:
            message_history = []
        return LLMAgentState(
            system_messages=[SystemMessage(role="system", content=self.system_prompt)],
            messages=list(message_history),
        )

    def generate_next_message(
        self, message: ValidAgentInputMessage, state: LLMAgentState
    ) -> tuple[AssistantMessage, LLMAgentState]:
        if isinstance(message, MultiToolMessage):
            state.messages.extend(message.tool_messages)
        else:
            state.messages.append(message)

        messages = state.system_messages + state.messages
        assistant_message = generate(
            model=self.llm,
            tools=self.tools,
            messages=messages,
            call_name="policy_aware_response",
            **self.llm_args,
        )
        state.messages.append(assistant_message)
        return assistant_message, state


def create_policy_aware_agent(tools, domain_policy, **kwargs):
    """Factory function for the registry."""
    return PolicyAwareAgent(
        tools=tools,
        domain_policy=domain_policy,
        llm=kwargs.get("llm"),
        llm_args=kwargs.get("llm_args"),
    )
