from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from settings import app_logger, settings

logger = app_logger.getChild("agent." + __name__)


def get_agent():
    return LlmAgent(
        model=LiteLlm(model=settings.llm_model),
        name="template",
        instruction="You are a helpful assistant.",
    )