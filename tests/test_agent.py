"""tests/test_agent.py"""
import pytest
from unittest.mock import MagicMock, patch



from pydantic import SecretStr

class TestCreateLLM:
    @patch("rag_forge.agent.agent.ChatDeepSeek")
    @patch("rag_forge.agent.agent.settings")
    def test_create_llm_with_defaults(self, mock_settings, mock_chat):
        """只传 api_key → 参数走 settings 默认值"""
        mock_settings.LLM_MODEL = "deepseek-chat"
        mock_settings.LLM_TEMPERATURE = 0.7
        mock_settings.LLM_TIMEOUT = 30
        mock_settings.LLM_MAX_RETRIES = 3

        from rag_forge.agent.agent import create_llm
        create_llm(api_key="test_key")

        mock_chat.assert_called_once_with(
            api_key=SecretStr("test_key"),
            model="deepseek-chat",
            temperature=0.7,
            timeout=30,
            max_retries=3,
        )

    @patch("rag_forge.agent.agent.ChatDeepSeek")
    @patch("rag_forge.agent.agent.settings")
    def test_create_llm_with_overrides(self, mock_settings, mock_chat):
        """显式传参 → 覆盖 settings 默认值"""
        mock_settings.LLM_MODEL = "deepseek-chat"
        mock_settings.LLM_TEMPERATURE = 0.7
        mock_settings.LLM_TIMEOUT = 30
        mock_settings.LLM_MAX_RETRIES = 3

        from rag_forge.agent.agent import create_llm
        create_llm(api_key="test_key", model="gpt-4", temperature=0.0, timeout=60, max_retries=5)

        mock_chat.assert_called_once_with(
            api_key=SecretStr("test_key"),
            model="gpt-4",
            temperature=0.0,
            timeout=60,
            max_retries=5,
        )

    @patch("rag_forge.agent.agent.ChatDeepSeek")
    def test_create_llm_secret_key(self, mock_chat):
        """验证 api_key 被 SecretStr 包裹"""
        from rag_forge.agent.agent import create_llm
        create_llm(api_key="my_key")

        _, kwargs = mock_chat.call_args
        assert isinstance(kwargs["api_key"], SecretStr)


class TestBuildAgent:
    @patch("langchain.agents.create_agent")
    def test_build_agent_with_tools(self, mock_create_agent):
        from rag_forge.agent.agent import build_agent

        mock_llm = MagicMock()
        mock_tools = [MagicMock(), MagicMock()]
        build_agent(mock_llm, mock_tools, system_prompt="你是一个助手")

        mock_create_agent.assert_called_once_with(
            mock_llm, mock_tools, system_prompt="你是一个助手"
        )


















