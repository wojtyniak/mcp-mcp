import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    debug: bool = Field(default=False, description="Debug mode")

    model_config = SettingsConfigDict(
        env_prefix="MCPMCP_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
app_logger = logging.getLogger("mcp-mcp")
app_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
app_logger.propagate = False  # Prevent propagation to root logger

if not app_logger.handlers:
    from rich.logging import RichHandler
    
    handler = RichHandler(
        show_time=False,
        show_path=False,
        rich_tracebacks=True,
        markup=True
    )
    app_logger.addHandler(handler)
