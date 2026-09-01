"""Runtime configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed endpoints, identities, and logical resource names."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_tenant_id: str
    azure_ad_client_id: str
    azure_application_client_id: str | None = None
    azure_search_principal_id: str | None = None
    azure_search_endpoint: str
    azure_search_index: str = "tjx-bvx-products-v1"
    azure_blob_endpoint: str
    azure_blob_container_name: str = "product-images"
    azure_cosmos_endpoint: str
    azure_cosmos_database: str = "retail-search-poc"
    azure_cosmos_container: str = "products"
    azure_openai_endpoint: str
    azure_openai_vision_deployment: str = "gpt-5.4-mini"
    azure_ai_vision_endpoint: str
    entra_api_audience: str
    allowed_hosts: list[str] = Field(default_factory=lambda: ["*"])

    @property
    def issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/v2.0"

    @property
    def token_audiences(self) -> list[str]:
        return list(dict.fromkeys((self.azure_ad_client_id, self.entra_api_audience)))

    @property
    def managed_identity_client_id(self) -> str:
        """Prefer the workload identity while retaining local configuration compatibility."""
        return self.azure_application_client_id or self.azure_ad_client_id


@lru_cache
def get_settings() -> Settings:
    """Load and cache immutable process configuration."""
    return Settings()  # type: ignore[call-arg]
