"""
Provider 适配层 - 用于统一不同厂商的模型服务接口

支持的 Provider 类型:
- openai-compatible: 兼容 OpenAI API 格式的服务
- bailian: 阿里云百炼
- deepseek: 深度求索
- zhipu: 智谱 AI
- kimi: 月之暗面
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from app.models.model_management import ProviderConfig


@dataclass
class ProviderResponse:
    """Provider 响应"""

    success: bool
    message: str
    response_time_ms: float
    model_name: str | None = None
    data: Any | None = None


class BaseProvider(ABC):
    """Provider 基类"""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
        )

    @abstractmethod
    def test_connection(self, model_name: str | None = None) -> ProviderResponse:
        """测试连接"""
        pass

    @abstractmethod
    def chat(self, model_name: str, messages: list[dict]) -> ProviderResponse:
        """聊天接口"""
        pass

    def close(self):
        """关闭客户端"""
        self.client.close()


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI 兼容 Provider"""

    def test_connection(self, model_name: str | None = None) -> ProviderResponse:
        start_time = time.time()
        try:
            # 尝试调用 models 接口
            response = self.client.get("/models")
            response.raise_for_status()
            data = response.json()

            models = data.get("data", [])
            detected_model = models[0]["id"] if models else model_name

            return ProviderResponse(
                success=True,
                message="连接测试成功",
                response_time_ms=(time.time() - start_time) * 1000,
                model_name=detected_model,
            )
        except httpx.HTTPStatusError as e:
            return ProviderResponse(
                success=False,
                message=f"HTTP 错误：{e.response.status_code}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except httpx.RequestError as e:
            return ProviderResponse(
                success=False,
                message=f"请求错误：{str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ProviderResponse(
                success=False,
                message=f"未知错误：{str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
            )

    def chat(self, model_name: str, messages: list[dict]) -> ProviderResponse:
        start_time = time.time()
        try:
            response = self.client.post(
                "/chat/completions",
                json={
                    "model": model_name,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()

            return ProviderResponse(
                success=True,
                message="聊天请求成功",
                response_time_ms=(time.time() - start_time) * 1000,
                model_name=model_name,
                data=data,
            )
        except httpx.HTTPStatusError as e:
            return ProviderResponse(
                success=False,
                message=f"HTTP 错误：{e.response.status_code}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except httpx.RequestError as e:
            return ProviderResponse(
                success=False,
                message=f"请求错误：{str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ProviderResponse(
                success=False,
                message=f"未知错误：{str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
            )


# Provider 类型映射
PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "openai-compatible": OpenAICompatibleProvider,
    "openai": OpenAICompatibleProvider,
    "bailian": OpenAICompatibleProvider,  # 百炼兼容 OpenAI 格式
    "deepseek": OpenAICompatibleProvider,  # DeepSeek 兼容 OpenAI 格式
    "zhipu": OpenAICompatibleProvider,  # 智谱兼容 OpenAI 格式
    "kimi": OpenAICompatibleProvider,  # Kimi 兼容 OpenAI 格式
}


def get_provider(config: ProviderConfig) -> BaseProvider:
    """获取 Provider 实例"""
    provider_class = PROVIDER_REGISTRY.get(config.provider_type, OpenAICompatibleProvider)
    return provider_class(config)


def test_provider_connection(config: ProviderConfig, model_name: str | None = None) -> ProviderResponse:
    """测试 Provider 连接"""
    provider = get_provider(config)
    try:
        return provider.test_connection(model_name)
    finally:
        provider.close()
