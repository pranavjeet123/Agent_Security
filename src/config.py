"""Loads and validates environment configuration for the demo."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

REQUIRED_VARS = ["PROJECT_ENDPOINT", "MODEL_DEPLOYMENT_NAME", "SECRET_VALUE"]


@dataclass
class Settings:
    project_endpoint: str
    model_deployment_name: str
    secret_value: str
    target_agent_name: str
    azure_subscription_id: str | None
    azure_resource_group: str | None
    azure_project_name: str | None

    @property
    def hub_project_config(self) -> dict | None:
        """The hub-based azure_ai_project dict, if all three fields are set."""
        if self.azure_subscription_id and self.azure_resource_group and self.azure_project_name:
            return {
                "subscription_id": self.azure_subscription_id,
                "resource_group_name": self.azure_resource_group,
                "project_name": self.azure_project_name,
            }
        return None


def load_settings() -> Settings:
    load_dotenv()

    missing = [name for name in REQUIRED_VARS if not os.environ.get(name)]
    if missing:
        print(
            f"Missing required environment variable(s): {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in the values before running the demo.",
            file=sys.stderr,
        )
        sys.exit(1)

    return Settings(
        project_endpoint=os.environ["PROJECT_ENDPOINT"],
        model_deployment_name=os.environ["MODEL_DEPLOYMENT_NAME"],
        secret_value=os.environ["SECRET_VALUE"],
        target_agent_name=os.environ.get("TARGET_AGENT_NAME", "redteam-demo-target"),
        azure_subscription_id=os.environ.get("AZURE_SUBSCRIPTION_ID") or None,
        azure_resource_group=os.environ.get("AZURE_RESOURCE_GROUP") or None,
        azure_project_name=os.environ.get("AZURE_PROJECT_NAME") or None,
    )
