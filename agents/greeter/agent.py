from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from settings import app_logger, settings

logger = app_logger.getChild("agent." + __name__)


def greet(name: str):
    """
    Greet a person by name.

    Args:
        name: The name of the person to greet.

    Returns:
        A greeting message.
    """
    return f"Hello, {name}!"


def get_agent():
    return LlmAgent(
        model=LiteLlm(model=settings.llm_model),
        name="greeter",
        instruction="You are a helpful greeter.",
        tools=[greet],
    )
