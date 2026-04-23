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
You are a customer service agent. Follow the <policy> below STRICTLY.

CRITICAL RULES — violating any of these fails the task:

1. AUTHENTICATE FIRST. Before performing ANY action that reads or modifies
   a user's account, you MUST verify the user's identity. Ask for their
   user ID, name, or other identifying information and use the appropriate
   lookup tool to confirm. NEVER skip this step.

2. ONE ACTION PER TURN. Each turn, either call exactly one tool OR send
   a text message to the user. Never do both. Never call multiple tools.

3. ACT, DON'T JUST THINK. Every turn must produce a visible output —
   a tool call or a message. Do not spend turns only reasoning internally.
   If you are unsure, ask the user a clarifying question rather than
   deliberating silently.

4. CONFIRM BEFORE WRITING. Before any action that changes data (cancel,
   modify, update), confirm with the user first. State what you will do
   and wait for their explicit approval.

5. FOLLOW POLICY EXACTLY. If the policy says a refund requires manager
   approval, do not skip it. If the policy says an item is non-returnable,
   tell the user.

Your workflow for every conversation:
  Step 1: Greet the user and ask how you can help.
  Step 2: Authenticate — ask for identifying info, look them up.
  Step 3: Understand the request — ask clarifying questions if needed.
  Step 4: Execute — use tools to fulfill the request per policy.
  Step 5: Confirm — tell the user what was done and ask if anything else.
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
