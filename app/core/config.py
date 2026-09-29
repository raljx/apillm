from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AzureFoundryConfig:
    endpoint: str
    api_key: str
    deployment_name: str

    @classmethod
    def from_env(cls) -> "AzureFoundryConfig":
        return cls(
            endpoint=os.getenv(
                "AZURE_OPENAI_ENDPOINT",
                "",
            ).strip(),
            api_key=os.getenv(
                "AZURE_OPENAI_API_KEY",
                "",
            ).strip(),
            deployment_name=os.getenv(
                "AZURE_OPENAI_DEPLOYMENT",
                "",
            ).strip(),
        )

    def is_valid(self) -> bool:
        return all(
            [
                self.endpoint,
                self.api_key,
                self.deployment_name,
            ]
        )