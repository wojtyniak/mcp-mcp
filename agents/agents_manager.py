import uuid
from typing import ClassVar

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from settings import app_logger

logger = app_logger.getChild(__name__)


class AgentManager:
    agents: ClassVar[dict[str, BaseAgent]] = {}
    session_service = InMemorySessionService()

    @classmethod
    def register(cls, agent: BaseAgent):
        cls.agents[agent.name] = agent

    @classmethod
    def get_agent_runner(cls, agent_name: str, app_name: str) -> Runner:
        runner = Runner(
            agent=cls.agents[agent_name],
            app_name=app_name,
            session_service=cls.session_service,
        )
        return runner


async def send_message(runner: Runner, message: str):
    logger.info(f"sending message: {message}")
    user_id = "user"
    session_id = f"{user_id}-{uuid.uuid4()}"
    logger.info(f"session: {session_id}")
    content = types.Content(role="user", parts=[types.Part(text=message)])
    if runner is None:
        raise ValueError("Runner is None")
    await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id,
    )
    result = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        print(event)
        if event.is_final_response():
            result = event.content.parts[0].text
    return result

