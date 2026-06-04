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

    @abstractmethod
    def chat_with_image(
        self,
        messages: list[dict],
        image_b64: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
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
        model: str = None,
    ) -> str:
        payload = {
            "model": model or self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=600,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str = None,
    ) -> Iterator[str]:
        payload = {
            "model": model or self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "stream": True,
            "options": {"num_predict": max_tokens},
        }
        with requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=600,
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

    def chat_with_image(
        self,
        messages: list[dict],
        image_b64: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        built = self._build_messages(messages, system_prompt)
        if built and built[-1]["role"] == "user":
            built[-1]["images"] = [image_b64]
        else:
            built.append({"role": "user", "content": "", "images": [image_b64]})
        payload = {
            "model": config.OLLAMA_VISION_MODEL,
            "messages": built,
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


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI 兼容 API 客户端，支持 DeepSeek、通义千问、Kimi、智谱等国内云端模型。
    发送前自动脱敏。"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = config.OPENAI_BASE_URL
        self.model = config.OPENAI_MODEL
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 环境变量未设置，请在 .env 中配置")

    def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str = None,
    ) -> str:
        messages, system_prompt = self._desensitize(messages, system_prompt)
        built = self._build_messages(messages, system_prompt)

        payload = {
            "model": model or self.model,
            "messages": built,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            return "请求超时，请稍后重试。"
        result = response.json()
        msg = result["choices"][0]["message"]
        return msg.get("content") or msg.get("reasoning_content", "（无回复）")

    def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str = None,
    ) -> Iterator[str]:
        messages, system_prompt = self._desensitize(messages, system_prompt)
        built = self._build_messages(messages, system_prompt)

        payload = {
            "model": model or self.model,
            "messages": built,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            stream=True,
            timeout=120,
        ) as response:
            response.raise_for_status()
            in_reasoning = False
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        reasoning = delta.get("reasoning_content", "")
                        content = delta.get("content", "")
                        if reasoning:
                            if not in_reasoning:
                                in_reasoning = True
                                yield "​🤔 思考中...\n\n"
                            in_reasoning = True
                        if content:
                            if in_reasoning:
                                in_reasoning = False
                                yield "\n---\n\n"
                            yield content
                    except json.JSONDecodeError:
                        continue

    def _build_messages(self, messages: list[dict], system_prompt: str) -> list[dict]:
        # Merge system messages from conversation into the system prompt
        result = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"] + "\n\n" + system_prompt
            else:
                result.append(msg)
        result.insert(0, {"role": "system", "content": system_prompt})

        # Zhipu API requires at least one non-system message
        if len(result) < 2:
            result.append({"role": "user", "content": "请根据以上要求进行分析和回复。"})

        return result

    def chat_with_image(
        self,
        messages: list[dict],
        image_b64: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        built = list(messages)
        image_content = {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
        }
        if built and built[-1]["role"] == "user":
            original_text = built[-1]["content"]
            built[-1] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": original_text},
                    image_content,
                ],
            }
        else:
            built.append({
                "role": "user",
                "content": [image_content, {"type": "text", "text": ""}],
            })
        messages, system_prompt = self._desensitize(built, system_prompt)
        final = self._build_messages(messages, system_prompt)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": final,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _desensitize(self, messages: list[dict], system_prompt: str) -> tuple:
        """发送云端前自动脱敏。"""
        if not config.DESENSITIZE_ENABLED:
            return messages, system_prompt

        from utils.desensitizer import desensitize_text

        clean_messages = []
        for msg in messages:
            content = msg["content"]
            if isinstance(content, str):
                content = desensitize_text(content)
            elif isinstance(content, list):
                # Multi-modal content
                content = [
                    {"type": c.get("type", "text"), "text": desensitize_text(c.get("text", ""))}
                    if c.get("type") == "text" else c
                    for c in content
                ]
            clean_messages.append({"role": msg["role"], "content": content})

        clean_system = desensitize_text(system_prompt)
        return clean_messages, clean_system


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
        model: str = None,
    ) -> str:
        messages, system_prompt = self._desensitize(messages, system_prompt)

        response = self.client.messages.create(
            model=model or self.model,
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
        model: str = None,
    ) -> Iterator[str]:
        messages, system_prompt = self._desensitize(messages, system_prompt)

        with self.client.messages.stream(
            model=model or self.model,
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

    def chat_with_image(
        self,
        messages: list[dict],
        image_b64: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        built = list(messages)
        image_content = {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64},
        }
        if built and built[-1]["role"] == "user":
            original_text = built[-1]["content"]
            built[-1] = {
                "role": "user",
                "content": [
                    image_content,
                    {"type": "text", "text": original_text},
                ],
            }
        else:
            built.append({
                "role": "user",
                "content": [image_content, {"type": "text", "text": ""}],
            })
        messages, system_prompt = self._desensitize(built, system_prompt)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text


# Global client instance
_client: BaseLLMClient | None = None


def get_client() -> BaseLLMClient:
    """根据配置返回对应的LLM客户端。ollama=本地不出网，openai=国内云端脱敏，claude=海外云端脱敏。"""
    global _client
    if _client is not None:
        return _client

    provider = config.LLM_PROVIDER.lower()
    if provider == "ollama":
        _client = OllamaClient()
    elif provider == "openai":
        _client = OpenAICompatibleClient()
    elif provider == "claude":
        _client = ClaudeClient()
    else:
        raise ValueError(f"不支持的LLM_PROVIDER: {provider}，请使用 'ollama'、'openai' 或 'claude'")

    return _client


def reset_client():
    """重置客户端实例（切换provider后调用）。"""
    global _client
    _client = None
