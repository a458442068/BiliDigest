import os
import pytest


class TestConfig:
    def test_config_has_defaults(self):
        from src.config import settings

        assert settings.port == 8000
        assert settings.log_level == "info"
        assert settings.llm_provider == "openai"
