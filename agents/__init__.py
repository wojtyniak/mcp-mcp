import importlib
import pkgutil
from pathlib import Path

from .agents_manager import AgentManager

# Auto-discover and register all agents
agents_dir = Path(__file__).parent
for module_info in pkgutil.iter_modules([str(agents_dir)]):
    if module_info.name != "agents_manager":
        try:
            module = importlib.import_module(f"agents.{module_info.name}.agent")
            if hasattr(module, "get_agent"):
                agent = module.get_agent()
                AgentManager.register(agent)
        except ImportError:
            # Skip if no agent.py in subdirectory
            pass
    
__all__ = ["AgentManager"]
