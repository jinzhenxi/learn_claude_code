"""配置层：从同目录 .env 读取 base_url / api_key / model_id。"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).with_name(".env")


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str
    model_id: str

    @classmethod
    def load(cls, env_path: Path = ENV_PATH) -> "Config":
        # override=True：以 .env 为准，避免 shell 里残留的同名变量干扰
        load_dotenv(env_path, override=True)
        return cls(
            base_url=os.environ["ANTHROPIC_BASE_URL"],
            api_key=os.environ["ANTHROPIC_API_KEY"],
            model_id=os.environ["MODEL_ID"],
        )
