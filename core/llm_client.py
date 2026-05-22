import json
import os
from abc import ABC, abstractmethod
from typing import Iterator

import requests

import config


class BaseLLMClient(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        ...

    @abstractmethod
    def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        ...


class OllamaClient(BaseLLMClient):
    """本地模型客户端，数据不出本机。"""

    def __init__(self):
        self.base_url = config.OLLAMA_BASE_URL
        self.model = config.OLLAMA_MODEL

    def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "stream": True,
            "options": {"num_predict": max_tokens},
        }
        with requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=120,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content

    def _build_messages(self, messages: list[dict], system_prompt: str) -> list[dict]:
        result = []
        if system_prompt:
            result.append({"role": "system", "content": system_prompt})
        result.extend(messages)
        return result


class ClaudeClient(BaseLLMClient):
    """云端Claude客户端，发送前自动脱敏。"""

    def __init__(self):
        try:
            import anthropic
        except ImportError:
            raise ImportError("使用Claude云端模式需要安装anthropic: pip install anthropic")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 环境变量未设置")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = config.CLAUDE_MODEL

    def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        # 脱敏处理
        messages, system_prompt = self._desensitize(messages, system_prompt)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text

    def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        # 脱敏处理
        messages, system_prompt = self._desensitize(messages, system_prompt)

        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def _desensitize(self, messages: list[dict], system_prompt: str) -> tuple:
        """发送云端前自动脱敏。"""
        if not config.DESENSITIZE_ENABLED:
            return messages, system_prompt

        from utils.desensitizer import desensitize_text

        clean_messages = []
        for msg in messages:
            clean_msg = {"role": msg["role"], "content": desensitize_text(msg["content"])}
            clean_messages.append(clean_msg)

        clean_system = desensitize_text(system_prompt)
        return clean_messages, clean_system


# Global client instance
_client: BaseLLMClient | None = None


def get_client() -> BaseLLMClient:
    """根据配置返回对应的LLM客户端。ollama=本地不出网，claude=云端脱敏。"""
    global _client
    if _client is not None:
        return _client

    provider = config.LLM_PROVIDER.lower()
    if provider == "ollama":
        _client = OllamaClient()
    elif provider == "claude":
        _client = ClaudeClient()
    else:
        raise ValueError(f"不支持的LLM_PROVIDER: {provider}，请使用 'ollama' 或 'claude'")

    return _client


def reset_client():
    """重置客户端实例（切换provider后调用）。"""
    global _client
    _client = None
