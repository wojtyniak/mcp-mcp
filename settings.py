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

# Logging

app_logger = logging.getLogger("mcp-mcp")
app_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
app_logger.propagate = False  # Prevent propagation to root logger

if not app_logger.handlers:
    import sys
    from rich.console import Console
    from rich.logging import RichHandler

    # Create console that uses stderr for MCP compatibility
    stderr_console = Console(file=sys.stderr, force_terminal=True)
    
    handler = RichHandler(
        show_time=False, show_path=False, rich_tracebacks=True, markup=True,
        console=stderr_console
    )
    app_logger.addHandler(handler)
