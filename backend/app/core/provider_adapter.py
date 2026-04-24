from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.provider_templates import MODEL_TYPE_ORDER, get_provider_template, normalize_provider_code
from app.models.model_management import AIModelProvider


@dataclass
class ProviderResponse:
    success: bool
    message: str
    response_time_ms: float
    model_name: str | None = None
    data: Any | None = None


@dataclass
class DiscoveredModel:
    model_code: str
    model_name: str
    model_type: str
    capabilities: list[str]
    raw_payload: dict[str, Any] | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None


class BaseProvider(ABC):
    def __init__(self, config: AIModelProvider):
        self.config = config
        self.client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={"Content-Type": "application/json"},
        )

    @property
    def provider_code(self) -> str:
        return normalize_provider_code(self.config.provider_code)

    @property
    def auth_type(self) -> str:
        return self.config.auth_type or "bearer"

    @property
    def auth_config(self) -> dict[str, Any]:
        raw = self.config.auth_config or {}
        return raw if isinstance(raw, dict) else {}

    @property
    def api_key(self) -> str:
        return (
            str(self.auth_config.get("api_key") or "")
            or str(self.auth_config.get("token") or "")
            or str(self.auth_config.get("access_token") or "")
        )

    @abstractmethod
    def list_models(self) -> list[DiscoveredModel]:
        raise NotImplementedError

    def test_connection(self, model_name: str | None = None) -> ProviderResponse:
        start_time = time.time()
        try:
            models = self.list_models()
            detected_model = model_name or (models[0].model_name if models else None)
            return ProviderResponse(
                success=True,
                message="连接测试成功",
                response_time_ms=(time.time() - start_time) * 1000,
                model_name=detected_model,
                data={"model_count": len(models)},
            )
        except httpx.HTTPStatusError as exc:
            return ProviderResponse(
                success=False,
                message=_http_error_message(exc),
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except httpx.RequestError as exc:
            return ProviderResponse(
                success=False,
                message=f"请求失败：{exc}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as exc:  # pragma: no cover
            return ProviderResponse(
                success=False,
                message=f"连接测试失败：{exc}",
                response_time_ms=(time.time() - start_time) * 1000,
            )

    def chat(self, model_name: str, messages: list[dict[str, Any]]) -> ProviderResponse:
        start_time = time.time()
        try:
            response = self.client.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers={**self.request_headers(), "Content-Type": "application/json"},
                json={"model": model_name, "messages": messages},
            )
            response.raise_for_status()
            return ProviderResponse(
                success=True,
                message="聊天请求成功",
                response_time_ms=(time.time() - start_time) * 1000,
                model_name=model_name,
                data=response.json(),
            )
        except httpx.HTTPStatusError as exc:
            return ProviderResponse(
                success=False,
                message=_http_error_message(exc),
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except httpx.RequestError as exc:
            return ProviderResponse(
                success=False,
                message=f"请求失败：{exc}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as exc:  # pragma: no cover
            return ProviderResponse(
                success=False,
                message=f"聊天请求失败：{exc}",
                response_time_ms=(time.time() - start_time) * 1000,
            )

    def embed(self, model_name: str, inputs: list[str]) -> ProviderResponse:
        start_time = time.time()
        try:
            vectors = self._embed(model_name, inputs)
            return ProviderResponse(
                success=True,
                message="向量化成功",
                response_time_ms=(time.time() - start_time) * 1000,
                model_name=model_name,
                data=vectors,
            )
        except NotImplementedError:
            return ProviderResponse(
                success=False,
                message="当前 Provider 暂不支持 embedding 调用",
                response_time_ms=(time.time() - start_time) * 1000,
                model_name=model_name,
            )
        except httpx.HTTPStatusError as exc:
            return ProviderResponse(
                success=False,
                message=_http_error_message(exc),
                response_time_ms=(time.time() - start_time) * 1000,
                model_name=model_name,
            )
        except httpx.RequestError as exc:
            return ProviderResponse(
                success=False,
                message=f"请求失败：{exc}",
                response_time_ms=(time.time() - start_time) * 1000,
                model_name=model_name,
            )
        except Exception as exc:  # pragma: no cover
            return ProviderResponse(
                success=False,
                message=f"向量化失败：{exc}",
                response_time_ms=(time.time() - start_time) * 1000,
                model_name=model_name,
            )

    def _embed(self, model_name: str, inputs: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def request_headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        if self.auth_type == "basic":
            return {"Authorization": f"Basic {self.api_key}"}
        return {"Authorization": f"Bearer {self.api_key}"}

    def close(self) -> None:
        self.client.close()


class OpenAICompatibleProvider(BaseProvider):
    def list_models(self) -> list[DiscoveredModel]:
        response = self.client.get(
            f"{self.config.base_url.rstrip('/')}/models",
            headers=self.request_headers(),
        )
        response.raise_for_status()
        payload = response.json()
        models = payload.get("data", []) if isinstance(payload, dict) else []
        return [
            _build_discovered_model(self.provider_code, item.get("id"), item)
            for item in models
            if isinstance(item, dict) and item.get("id")
        ]

    def _embed(self, model_name: str, inputs: list[str]) -> list[list[float]]:
        response = self.client.post(
            f"{self.config.base_url.rstrip('/')}/embeddings",
            headers={**self.request_headers(), "Content-Type": "application/json"},
            json={"model": model_name, "input": inputs},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("data", []) if isinstance(payload, dict) else []
        sorted_items = sorted(
            [item for item in items if isinstance(item, dict)],
            key=lambda item: int(item.get("index", 0)),
        )
        vectors = [item.get("embedding") for item in sorted_items]
        if len(vectors) != len(inputs) or any(not isinstance(vector, list) for vector in vectors):
            raise ValueError("embedding 响应格式无效")
        return [[float(value) for value in vector] for vector in vectors]


class QwenProvider(OpenAICompatibleProvider):
    EMBEDDING_CANDIDATES = (
        "text-embedding-v4",
        "text-embedding-v3",
        "text-embedding-v2",
        "text-embedding-v1",
    )
    RERANK_CANDIDATES = (
        "gte-rerank-v2",
        "gte-rerank",
    )

    def list_models(self) -> list[DiscoveredModel]:
        models = super().list_models()
        existing_codes = {item.model_code for item in models}
        models.extend(self._probe_embedding_models(existing_codes))
        existing_codes = {item.model_code for item in models}
        models.extend(self._probe_rerank_models(existing_codes))
        return sorted(models, key=lambda item: item.model_code.lower())

    def _probe_embedding_models(self, existing_codes: set[str]) -> list[DiscoveredModel]:
        discovered: list[DiscoveredModel] = []
        url = f"{self.config.base_url.rstrip('/')}/embeddings"
        headers = {**self.request_headers(), "Content-Type": "application/json"}

        for model_code in self.EMBEDDING_CANDIDATES:
            if model_code in existing_codes:
                continue
            try:
                response = self.client.post(url, headers=headers, json={"model": model_code, "input": "ping"})
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {400, 404}:
                    continue
                raise
            except httpx.RequestError:
                break

            discovered.append(
                DiscoveredModel(
                    model_code=model_code,
                    model_name=model_code,
                    model_type="embedding",
                    capabilities=[],
                    raw_payload={"id": model_code, "source": "qwen_embedding_probe"},
                )
            )
        return discovered

    def _probe_rerank_models(self, existing_codes: set[str]) -> list[DiscoveredModel]:
        discovered: list[DiscoveredModel] = []
        url = f"{self._native_api_base_url()}/api/v1/services/rerank/text-rerank/text-rerank"
        headers = {**self.request_headers(), "Content-Type": "application/json"}

        for model_code in self.RERANK_CANDIDATES:
            if model_code in existing_codes:
                continue
            try:
                response = self.client.post(
                    url,
                    headers=headers,
                    json={"model": model_code, "input": {"query": "ping", "documents": ["ping", "pong"]}},
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {400, 404}:
                    continue
                raise
            except httpx.RequestError:
                break

            discovered.append(
                DiscoveredModel(
                    model_code=model_code,
                    model_name=model_code,
                    model_type="rerank",
                    capabilities=[],
                    raw_payload={"id": model_code, "source": "qwen_rerank_probe"},
                )
            )
        return discovered

    def _native_api_base_url(self) -> str:
        base_url = self.config.base_url.rstrip("/")
        if "/compatible-mode/" in base_url:
            return base_url.split("/compatible-mode/", 1)[0]
        if base_url.endswith("/compatible-mode"):
            return base_url[: -len("/compatible-mode")]
        if base_url.endswith("/api/v1"):
            return base_url[: -len("/api/v1")]
        return base_url


class AnthropicProvider(BaseProvider):
    def request_headers(self) -> dict[str, str]:
        headers = {"anthropic-version": "2023-06-01"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def list_models(self) -> list[DiscoveredModel]:
        response = self.client.get(
            f"{self.config.base_url.rstrip('/')}/v1/models",
            headers=self.request_headers(),
        )
        response.raise_for_status()
        payload = response.json()
        models = payload.get("data", []) if isinstance(payload, dict) else []
        return [
            _build_discovered_model(self.provider_code, item.get("id") or item.get("name"), item)
            for item in models
            if isinstance(item, dict) and (item.get("id") or item.get("name"))
        ]


class GeminiProvider(BaseProvider):
    def list_models(self) -> list[DiscoveredModel]:
        models: dict[str, dict[str, Any]] = {}
        next_page_token: str | None = None

        while True:
            params = {"key": self.api_key, "pageSize": 1000}
            if next_page_token:
                params["pageToken"] = next_page_token
            url = f"{self.config.base_url.rstrip('/')}/v1beta/models?{urlencode(params)}"
            response = self.client.get(url)
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("models", []) if isinstance(payload, dict) else []:
                if isinstance(item, dict) and item.get("name"):
                    model_id = _normalize_model_id(str(item["name"]))
                    models[model_id] = item
            next_page_token = payload.get("nextPageToken") if isinstance(payload, dict) else None
            if not next_page_token:
                break

        return [
            _build_discovered_model(self.provider_code, model_id, item)
            for model_id, item in sorted(models.items(), key=lambda pair: pair[0].lower())
        ]


PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "openai_compatible": OpenAICompatibleProvider,
    "qwen_native": QwenProvider,
    "anthropic_native": AnthropicProvider,
    "gemini_native": GeminiProvider,
}


def _http_error_message(exc: httpx.HTTPStatusError) -> str:
    if exc.response.status_code == 401:
        return "认证失败，请检查 API Key 或认证配置"
    if exc.response.status_code == 429:
        return "请求过于频繁，请稍后重试"
    if exc.response.status_code >= 500:
        return "厂商服务暂时不可用，请稍后重试"
    return f"HTTP 错误：{exc.response.status_code}"


def _normalize_model_id(model_id: str) -> str:
    if model_id.startswith("models/"):
        return model_id.split("/", 1)[1]
    return model_id


def _sorted_model_types(model_types: list[str]) -> list[str]:
    unique_types: list[str] = []
    for model_type in model_types:
        if model_type not in unique_types:
            unique_types.append(model_type)
    return sorted(
        unique_types,
        key=lambda value: MODEL_TYPE_ORDER.index(value) if value in MODEL_TYPE_ORDER else len(MODEL_TYPE_ORDER),
    )


def _extract_capabilities(provider_code: str, model_id: str, raw: dict[str, Any]) -> list[str]:
    text = model_id.lower()
    capabilities: list[str] = []

    methods = [str(item).lower() for item in raw.get("supportedGenerationMethods", [])]
    if any("vision" in method for method in methods) or any(token in text for token in ["vision", "multimodal", "omni"]):
        capabilities.append("vision")
    if any("function" in method for method in methods) or "function" in text:
        capabilities.append("function_call")
    if provider_code == "gemini" and any("streamgeneratecontent" == method for method in methods):
        capabilities.append("streaming")
    return capabilities


def _infer_model_types(provider_code: str, model_id: str, raw: dict[str, Any]) -> list[str]:
    text = model_id.lower()
    model_types: list[str] = []

    methods = [str(item).lower() for item in raw.get("supportedGenerationMethods", [])]
    if any("embed" in method for method in methods):
        model_types.append("embedding")
    if any(method in methods for method in ["generatecontent", "streamgeneratecontent", "counttokens"]):
        model_types.append("llm")

    if provider_code == "anthropic":
        model_types.append("llm")
    if "ocr" in text:
        model_types.append("ocr")
    if "moderation" in text or "guard" in text:
        model_types.append("moderation")
    if "embedding" in text or "embed" in text:
        model_types.append("embedding")
    if "rerank" in text:
        model_types.append("rerank")
    if any(token in text for token in ["transcribe", "transcription", "whisper", "speech-to-text", "asr", "stt"]):
        model_types.append("asr")
    if any(token in text for token in ["text-to-speech", "tts", "speech-"]):
        model_types.append("tts")
    if any(token in text for token in ["vision", "multimodal", "omni", "vl-"]):
        model_types.append("vlm")
    if not model_types and any(
        token in text
        for token in [
            "chat",
            "instruct",
            "turbo",
            "plus",
            "max",
            "reason",
            "coder",
            "math",
            "thinking",
            "gpt",
            "claude",
            "gemini",
            "qwen",
            "deepseek",
            "kimi",
            "glm",
            "llama",
            "grok",
        ]
    ):
        model_types.append("llm")
    if not model_types:
        model_types.append("llm")
    return _sorted_model_types(model_types)


def _build_discovered_model(provider_code: str, model_id: str | None, raw: dict[str, Any]) -> DiscoveredModel:
    if not model_id:
        raise ValueError("模型标识不能为空")
    normalized_id = _normalize_model_id(str(model_id))
    model_types = _infer_model_types(provider_code, normalized_id, raw)
    capabilities = _extract_capabilities(provider_code, normalized_id, raw)

    return DiscoveredModel(
        model_code=normalized_id,
        model_name=normalized_id,
        model_type=model_types[0],
        capabilities=capabilities,
        raw_payload=raw,
        context_window=raw.get("context_window") or raw.get("inputTokenLimit"),
        max_output_tokens=raw.get("max_output_tokens") or raw.get("outputTokenLimit"),
    )


def get_provider(config: AIModelProvider) -> BaseProvider:
    template = get_provider_template(config.provider_code)
    adapter_key = (template or {}).get("discovery_adapter", "openai_compatible")
    provider_class = PROVIDER_REGISTRY.get(adapter_key, OpenAICompatibleProvider)
    return provider_class(config)


def test_provider_connection(config: AIModelProvider, model_name: str | None = None) -> ProviderResponse:
    provider = get_provider(config)
    try:
        return provider.test_connection(model_name)
    finally:
        provider.close()


def fetch_provider_models(config: AIModelProvider) -> list[DiscoveredModel]:
    provider = get_provider(config)
    try:
        return provider.list_models()
    finally:
        provider.close()


def embed_texts(config: AIModelProvider, model_name: str, inputs: list[str]) -> ProviderResponse:
    provider = get_provider(config)
    try:
        return provider.embed(model_name, inputs)
    finally:
        provider.close()
