"""Central configuration loaded from .env"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    openrouter_api_key: str = ""
    dev_model: str = "qwen/qwen3-235b-a22b"
    eval_model: str = "anthropic/claude-sonnet-4"
    dev_temperature: float = 0.3
    eval_temperature: float = 0.0

    # Email
    resend_api_key: str = ""
    from_email: str = "outreach@tenacious.dev"
    reply_webhook_url: str = "http://localhost:8000/webhooks/email/reply"

    # SMS
    at_username: str = "sandbox"
    at_api_key: str = ""
    at_shortcode: str = ""
    at_webhook_url: str = "http://localhost:8000/webhooks/sms/inbound"

    # HubSpot
    hubspot_access_token: str = ""
    hubspot_portal_id: str = ""

    # Cal.com
    calcom_api_key: str = ""
    calcom_base_url: str = "http://localhost:3000"
    calcom_event_type_id: int = 1

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_base_url: str = ""  # alias for host

    # Kill switch
    live_mode: bool = False
    outbound_sink: str = "local"  # "local" | "resend" | "at"

    # Paths
    crunchbase_data_path: str = "data/crunchbase/crunchbase_sample.json"
    layoffs_data_path: str = "data/layoffs/layoffs.csv"
    job_posts_path: str = "data/job_posts/"
    seed_data_path: str = "seed_data/"

    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    @property
    def is_live(self) -> bool:
        return self.live_mode and self.outbound_sink != "local"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
