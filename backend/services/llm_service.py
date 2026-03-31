"""LLM service — intent parsing, summarization, and content drafting via OpenRouter."""

import json
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config import get_settings
from backend.schemas import WorkflowPlan, WorkflowStepDef
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class PlanParseError(Exception):
    """Raised when the LLM returns an unparseable or invalid workflow plan."""
    pass


class LLMService:
    """
    Wraps OpenRouter (or any OpenAI-compatible endpoint) for:
    - Intent parsing → WorkflowPlan
    - PR summarization
    - Email / Slack / DM drafting
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENROUTER_MODEL,
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.1,
        )

    async def plan(self, prompt: str, context: dict[str, Any]) -> WorkflowPlan:
        """Parse a user prompt into a structured WorkflowPlan."""
        from backend.agent.prompts import get_planner_prompt
        logger.info(
            "Generating workflow plan",
            extra={
                "data": {
                    "prompt_length": len(prompt),
                    "connected_services": context.get("connected_services", []),
                }
            },
        )

        system_prompt = get_planner_prompt(context)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]

        response = await self.llm.ainvoke(messages)
        raw = response.content

        try:
            # Extract JSON from the response (handle markdown code blocks)
            json_str = raw
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)
            
            # Check if the LLM returned a clarification request instead of a plan
            if "error" in data:
                error_msg = data.get("error", "Unknown error")
                question = data.get("question", "")
                
                # Only raise for truly blocking errors (missing repo)
                if "repository" in question.lower():
                    if question:
                        raise PlanParseError(f"{error_msg}: {question}")
                    else:
                        raise PlanParseError(error_msg)
                
                # For non-blocking clarifications (Slack channel, recipients), return partial plan
                # The executor will emit a clarification_needed event
                logger.info(
                    "LLM needs clarification",
                    extra={"data": {"question": question}}
                )
                raise PlanParseError(f"{error_msg}: {question}")
            
            plan = WorkflowPlan.model_validate(data)
            logger.info(
                "Workflow plan generated",
                extra={"data": {"step_count": len(plan.steps)}},
            )
            return plan

        except json.JSONDecodeError as e:
            logger.error("LLM plan response was invalid JSON", extra={"data": {"error": str(e)}})
            raise PlanParseError(f"LLM returned invalid JSON: {e}")
        except Exception as e:
            logger.error("Failed to parse workflow plan", extra={"data": {"error": str(e)}})
            raise PlanParseError(f"Failed to parse workflow plan: {e}")

    async def summarize_pr(self, pr_data: dict) -> str:
        """Generate a plain-English summary of a pull request."""
        from backend.agent.prompts import get_summarizer_prompt
        logger.info(
            "Generating PR summary",
            extra={"data": {"pr_keys": sorted(pr_data.keys()) if isinstance(pr_data, dict) else []}},
        )

        messages = [
            SystemMessage(content=get_summarizer_prompt()),
            HumanMessage(content=json.dumps(pr_data, indent=2)),
        ]
        response = await self.llm.ainvoke(messages)
        return response.content

    async def draft_email(self, context: dict) -> dict:
        """Generate an email draft (subject + body + recipients)."""
        from backend.agent.prompts import get_drafting_prompt
        logger.info("Generating email draft", extra={"data": {"context_keys": sorted(context.keys())}})

        messages = [
            SystemMessage(content=get_drafting_prompt("email")),
            HumanMessage(content=json.dumps(context, indent=2)),
        ]
        response = await self.llm.ainvoke(messages)

        try:
            raw = response.content
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            return json.loads(raw)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Email draft response was not valid JSON; using fallback")
            return {"subject": "Meeting Notification", "body": response.content, "to": []}

    async def draft_slack(self, context: dict) -> list:
        """Generate Slack Block Kit blocks for a channel message."""
        from backend.agent.prompts import get_drafting_prompt
        logger.info("Generating Slack draft", extra={"data": {"context_keys": sorted(context.keys())}})

        messages = [
            SystemMessage(content=get_drafting_prompt("slack")),
            HumanMessage(content=json.dumps(context, indent=2)),
        ]
        response = await self.llm.ainvoke(messages)

        try:
            raw = response.content
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            return json.loads(raw)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Slack draft response was not valid JSON; using fallback block")
            return [{"type": "section", "text": {"type": "mrkdwn", "text": response.content}}]

    async def draft_dm(self, context: dict, recipient: str) -> str:
        """Generate a personal DM text for a specific recipient."""
        from backend.agent.prompts import get_drafting_prompt
        logger.info(
            "Generating DM draft",
            extra={"data": {"recipient": recipient, "context_keys": sorted(context.keys())}},
        )

        messages = [
            SystemMessage(content=get_drafting_prompt("dm")),
            HumanMessage(content=json.dumps({**context, "recipient": recipient}, indent=2)),
        ]
        response = await self.llm.ainvoke(messages)
        return response.content

    async def generate_summary(self, run_context: dict) -> str:
        """Generate a final run result summary."""
        logger.info("Generating run summary", extra={"data": {"run_context_keys": sorted(run_context.keys())}})
        messages = [
            SystemMessage(content="You are a helpful assistant. Summarize the results of this workflow execution concisely. Include what succeeded, what failed, and any actions the user should take."),
            HumanMessage(content=json.dumps(run_context, indent=2)),
        ]
        response = await self.llm.ainvoke(messages)
        return response.content


# Singleton
llm_service = LLMService()
