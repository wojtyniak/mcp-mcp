from typing import ClassVar

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from settings import app_logger

logger = app_logger.getChild(__name__)


class AgentManager:
    APP_NAME = "mcp-mcp"
    agents: ClassVar[dict[str, BaseAgent]] = {}
    session_service = InMemorySessionService()

    @classmethod
    def register(cls, agent: BaseAgent):
        cls.agents[agent.name] = agent

    @classmethod
    def get_agent_runner(cls, agent_name: str) -> Runner:
        runner = Runner(
            agent=cls.agents[agent_name],
            app_name=cls.APP_NAME,
            session_service=cls.session_service,
        )
        return runner

    @classmethod
    async def send_message(cls, agent_name: str, message: str):
        """Send a message to an agent."""
        user_id = "user"

        runner = cls.get_agent_runner(agent_name)
        if runner is None:
            raise ValueError("Runner is None")

        # Let ADK create the session with auto-generated ID
        session = await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id=user_id,
        )

        logger.debug(
            f"sending message to agent {agent_name}\nsession:\t{session.id}\nmessage:\t{message}"
        )
        content = types.Content(role="user", parts=[types.Part(text=message)])

        result = None
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            print(event)
            if event.is_final_response():
                result = event.content.parts[0].text
        return result
