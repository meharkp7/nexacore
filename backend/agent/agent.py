"""
agent.py
─────────
The central AI orchestrator for the Ramp onboarding assistant.

Workflow:
  OnboardingRequest
      │
      ▼
  ContextBuilder  ──► team_resolver + exception_tagger + memory retrieval (P3)
      │
      ▼
  PromptBuilder   ──► system prompt + human prompt with full context
      │
      ▼
  LLM (Groq)      ──► bound with tools
      │
      ▼
  Tool Execution  ──► raise_ticket / send_reminder / log_blocker (if needed)
      │
      ▼
  AgentResponse
"""

import logging
import os
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.interfaces import (
    AgentResponse,
    ContextBlock,
    MemoryItem,
    OnboardingRequest,
    TeamPath,
    UserProfile,
)
from backend.agent.prompt_builder import build_system_prompt, build_human_prompt
from backend.agent.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# LLM factory
# ─────────────────────────────────────────────

def _build_llm() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set. Check your .env file.")
    return ChatGroq(
        api_key=api_key,
        model=os.getenv("GROQ_MODEL", "llama3-70b-8192"),
        temperature=0.3,
        max_tokens=1024,
        timeout=30,
    )


# ─────────────────────────────────────────────
# Agent class
# ─────────────────────────────────────────────

class RampAgent:
    """
    Main orchestrator. Instantiate once at startup via get_agent().
    """

    def __init__(self) -> None:
        self.llm = _build_llm()
        self.llm_with_tools = self.llm.bind_tools(TOOL_REGISTRY)
        self._tool_map: dict = {t.name: t for t in TOOL_REGISTRY}
        logger.info(
            "RampAgent initialized | model=%s | tools=%s",
            os.getenv("GROQ_MODEL", "llama3-70b-8192"),
            list(self._tool_map.keys()),
        )

    # ── Public entry point ──────────────────────────────────────────────

    async def run(self, request: OnboardingRequest) -> AgentResponse:
        """Full pipeline: context → prompt → LLM → tools → AgentResponse."""
        logger.info(
            "Agent run | user=%s | team=%s | query=%.80s",
            request.name, request.team, request.query,
        )

        # Step 1: Build context (P3's module)
        ctx = await self._build_context(request)

        # Step 2: Build prompts
        system_msg = SystemMessage(content=build_system_prompt())
        human_msg = HumanMessage(content=build_human_prompt(ctx))

        # Step 3: Call LLM
        messages = [system_msg, human_msg]
        ai_message = await self._call_llm_with_retry(messages)
        messages.append(ai_message)

        # Step 4: Handle tool calls if any
        actions_taken: list[str] = []
        if ai_message.tool_calls:
            messages, actions_taken = await self._execute_tool_calls(ai_message, messages)
            final_message = await self._call_llm_with_retry(messages)
            answer = final_message.content
        else:
            answer = ai_message.content

        return AgentResponse(
            message=answer,
            memories_used=ctx.memories,
            suggested_actions=actions_taken,
        )

    # ── Context building ─────────────────────────────────────────────────

    async def _build_context(self, request: OnboardingRequest) -> ContextBlock:
        """
        Calls P3's context_builder. Falls back to a stub if not yet implemented.
        """
        try:
            from backend.context.context_builder import build_context
            return await build_context(request)
        except (ImportError, NotImplementedError):
            logger.warning("context_builder not available — using stub context")
            return self._stub_context(request)

    def _stub_context(self, request: OnboardingRequest) -> ContextBlock:
        """Minimal stub — keeps the agent running while P3 delivers context_builder."""
        user = UserProfile(
            name=request.name,
            team_name=request.team,
            employment_type=request.employee_type,
            role_title=request.role or None,
        )
        team_path = TeamPath(
            ids=["company", request.team.lower().replace(" ", "_")],
            names=["Company", request.team],
        )
        return ContextBlock(
            user=user,
            team_path=team_path,
            memories=[],
            exception_notes=["Contractor workflow applies"] if request.employee_type == "contractor" else [],
        )

    # ── LLM call with retry ──────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _call_llm_with_retry(self, messages: list) -> AIMessage:
        try:
            return await self.llm_with_tools.ainvoke(messages)
        except Exception as e:
            logger.warning("LLM call failed, retrying... error=%s", str(e))
            raise

    # ── Tool execution ───────────────────────────────────────────────────

    async def _execute_tool_calls(
        self, ai_message: AIMessage, messages: list
    ) -> tuple[list, list[str]]:
        actions_taken: list[str] = []
        for tool_call in ai_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            logger.info("Executing tool: %s | args=%s", tool_name, tool_args)
            if tool_name not in self._tool_map:
                result = f"Error: tool '{tool_name}' not registered."
                logger.error(result)
            else:
                try:
                    result = self._tool_map[tool_name].invoke(tool_args)
                    actions_taken.append(f"{tool_name}: {result}")
                except Exception as e:
                    result = f"Tool '{tool_name}' failed: {e}"
                    logger.error(result)
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))
        return messages, actions_taken


# ─────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────

_agent_instance: Optional[RampAgent] = None


def get_agent() -> RampAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = RampAgent()
    return _agent_instance
