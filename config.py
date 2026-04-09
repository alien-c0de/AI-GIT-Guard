"""
config.py — Loads .env, validates settings, and exposes a singleton config object.
All other modules import `settings` from here.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(dotenv_path=Path(__file__).parent / ".env")


class Settings:
    """Central configuration object populated from environment variables."""

    def __init__(self) -> None:
        # --- GitHub ---
        self.GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
        self.GITHUB_ENTERPRISE_URL: str = os.getenv("GITHUB_ENTERPRISE_URL", "")
        self.GITHUB_ORG: str = os.getenv("GITHUB_ORG", "")

        # --- LLM ---
        self.LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").lower()
        self.OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
        self.ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "")
        self.ANTHROPIC_AUTH_TOKEN: str = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
        self.ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "")
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.COPILOT_TOKEN: str = os.getenv("COPILOT_TOKEN", "")

        # GitHub Models (GitHub Marketplace models via Azure AI inference)
        self.GITHUB_MODELS_ENDPOINT: str = os.getenv("GITHUB_MODELS_ENDPOINT", "https://models.inference.ai.azure.com")
        self.GITHUB_MODELS_MODEL: str = os.getenv("GITHUB_MODELS_MODEL", "gpt-5")

        # --- Cache ---
        try:
            self.CACHE_TTL_MINUTES: int = int(os.getenv("CACHE_TTL_MINUTES", "30"))
        except (ValueError, TypeError):
            logging.getLogger(__name__).warning(
                "Invalid CACHE_TTL_MINUTES value — defaulting to 30 minutes."
            )
            self.CACHE_TTL_MINUTES = 30

        # --- Output ---
        self.OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./reports"))
        self.DEFAULT_OUTPUT_FORMAT: str = os.getenv("DEFAULT_OUTPUT_FORMAT", "text")

        # --- Logging ---
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    def detect_available_providers(self) -> list[dict[str, str]]:
        """Return a list of LLM providers that have valid credentials configured.

        Each entry is a dict with 'id' (internal name) and 'label' (display name).
        Ollama is detected by checking if the server is reachable.
        """
        available = []

        # Ollama — check if the local server responds
        if self.OLLAMA_BASE_URL:
            try:
                import httpx
                r = httpx.get(f"{self.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=3)
                if r.is_success:
                    available.append({"id": "ollama", "label": f"Ollama (local -- {self.OLLAMA_MODEL})"})
            except Exception:
                pass

        # Claude / Anthropic
        if self.ANTHROPIC_API_KEY or self.ANTHROPIC_AUTH_TOKEN:
            label = f"Claude ({self.ANTHROPIC_MODEL})" if self.ANTHROPIC_MODEL else "Claude (Anthropic)"
            available.append({"id": "claude", "label": label})

        # OpenAI — reject obvious placeholder values
        if self.OPENAI_API_KEY and len(self.OPENAI_API_KEY) > 10 and not self.OPENAI_API_KEY.startswith("sk-xxxx"):
            available.append({"id": "openai", "label": "OpenAI GPT"})

        # GitHub Models (uses GITHUB_TOKEN as API key)
        if self.GITHUB_TOKEN:
            available.append({"id": "github_models", "label": f"GitHub Models ({self.GITHUB_MODELS_MODEL})"})

        # Copilot
        if self.COPILOT_TOKEN:
            available.append({"id": "copilot", "label": "GitHub Copilot"})

        return available

    def validate(self) -> None:
        """Raise ValueError for critical missing settings."""
        errors = []
        if not self.GITHUB_TOKEN:
            errors.append("GITHUB_TOKEN is required. Set it in your .env file.")
        if not self.GITHUB_ORG:
            errors.append("GITHUB_ORG is required. Set it in your .env file.")
        if errors:
            raise ValueError("Configuration errors:\n  - " + "\n  - ".join(errors))

    def warn_cloud_llm(self, console=None) -> None:
        """Print a data-privacy warning when a cloud LLM is configured."""
        if self.LLM_PROVIDER in ("claude", "openai", "copilot", "github_models"):
            msg = (
                f"LLM_PROVIDER='{self.LLM_PROVIDER}' will send alert data "
                "to a third-party cloud API.\n"
                "Review your organisation's data-sharing policy before proceeding."
            )
            if console:
                from rich.panel import Panel
                console.print(Panel(
                    f"[yellow]{msg}[/yellow]",
                    title="[bold yellow]Data Privacy Notice[/bold yellow]",
                    border_style="yellow",
                ))
            else:
                import warnings
                warnings.warn(f"[AI Git Guard] {msg}", stacklevel=2)

    def setup_logging(self) -> None:
        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL, logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        # Silence noisy third-party loggers unless in DEBUG mode
        if self.LOG_LEVEL != "DEBUG":
            for _name in (
                "httpx", "httpcore", "urllib3",
                "openai", "openai._base_client",
                "github.client",
            ):
                logging.getLogger(_name).setLevel(logging.WARNING)
        # Ensure reports directory exists
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Singleton — import this everywhere
settings = Settings()
