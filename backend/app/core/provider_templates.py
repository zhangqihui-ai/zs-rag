from __future__ import annotations

from copy import deepcopy
from typing import Any

MODEL_TYPE_ORDER = [
    "llm",
    "embedding",
    "rerank",
    "tts",
    "asr",
    "vlm",
    "moderation",
    "ocr",
]
MODEL_TYPE_SET = set(MODEL_TYPE_ORDER)

PROVIDER_TEMPLATES: list[dict[str, Any]] = [
    {
        "provider_code": "openai",
        "provider_name": "OpenAI",
        "deployment_type": "public",
        "default_base_url": "https://api.openai.com/v1",
        "supported_types": ["llm", "embedding", "tts", "moderation"],
        "auth_type": "bearer",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
        ],
        "discovery_adapter": "openai_compatible",
    },
    # {
    #     "provider_code": "anthropic",
    #     "provider_name": "Anthropic",
    #     "deployment_type": "public",
    #     "default_base_url": "https://api.anthropic.com",
    #     "supported_types": ["llm"],
    #     "auth_type": "api_key",
    #     "auth_fields": [
    #         {"key": "api_key", "label": "API Key", "type": "password", "required": True},
    #     ],
    #     "discovery_adapter": "anthropic_native",
    # },
    # {
    #     "provider_code": "gemini",
    #     "provider_name": "Gemini",
    #     "deployment_type": "public",
    #     "default_base_url": "https://generativelanguage.googleapis.com",
    #     "supported_types": ["llm", "embedding", "vlm"],
    #     "auth_type": "api_key",
    #     "auth_fields": [
    #         {"key": "api_key", "label": "API Key", "type": "password", "required": True},
    #     ],
    #     "discovery_adapter": "gemini_native",
    # },
    {
        "provider_code": "deepseek",
        "provider_name": "DeepSeek",
        "deployment_type": "public",
        "default_base_url": "https://api.deepseek.com",
        "supported_types": ["llm", "embedding"],
        "auth_type": "bearer",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
        ],
        "discovery_adapter": "openai_compatible",
    },
    {
        "provider_code": "qwen",
        "provider_name": "阿里百炼 (DashScope)",
        "deployment_type": "public",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "supported_types": ["llm", "embedding", "rerank", "tts", "asr", "vlm"],
        "auth_type": "bearer",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
        ],
        "discovery_adapter": "qwen_native",
    },
    {
        "provider_code": "dashscope_coding",
        "provider_name": "阿里云 Coding Plan",
        "deployment_type": "public",
        "default_base_url": "https://coding.dashscope.aliyuncs.com/v1",
        "supported_types": ["llm", "vlm"],
        "auth_type": "bearer",
        "auth_fields": [
            {"key": "api_key", "label": "Coding Plan API Key (sk-sp-)", "type": "password", "required": True},
        ],
        "discovery_adapter": "dashscope_coding",
    },
    {
        "provider_code": "moonshot",
        "provider_name": "月之暗面",
        "deployment_type": "public",
        "default_base_url": "https://api.moonshot.cn/v1",
        "supported_types": ["llm", "embedding", "vlm"],
        "auth_type": "bearer",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
        ],
        "discovery_adapter": "openai_compatible",
    },
    {
        "provider_code": "zhipu",
        "provider_name": "智谱AI (Zhipu)",
        "deployment_type": "public",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "supported_types": ["llm", "embedding", "asr", "moderation"],
        "auth_type": "bearer",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
        ],
        "discovery_adapter": "openai_compatible",
    },
    {
        "provider_code": "ollama",
        "provider_name": "Ollama（本地部署）",
        "deployment_type": "private",
        "default_base_url": "http://127.0.0.1:11434/v1",
        "supported_types": ["llm", "embedding", "vlm"],
        "auth_type": "bearer",
        "auth_fields": [
            {"key": "api_key", "label": "API Key / Token", "type": "password", "required": False},
        ],
        "discovery_adapter": "openai_compatible",
    },
    {
        "provider_code": "gpustack",
        "provider_name": "GPUStack（私有部署）",
        "deployment_type": "private",
        "default_base_url": "http://127.0.0.1/v1",
        "supported_types": ["llm", "embedding", "asr", "vlm"],
        "auth_type": "bearer",
        "auth_fields": [
            {"key": "api_key", "label": "API Key / Token", "type": "password", "required": False},
        ],
        "discovery_adapter": "openai_compatible",
    },
    {
        "provider_code": "custom_openai",
        "provider_name": "自定义 OpenAI 兼容服务",
        "deployment_type": "private",
        "default_base_url": "http://127.0.0.1:8000/v1",
        "supported_types": ["llm", "embedding", "rerank", "tts", "asr", "vlm", "moderation", "ocr"],
        "auth_type": "bearer",
        "auth_fields": [
            {"key": "api_key", "label": "API Key / Token", "type": "password", "required": False},
        ],
        "discovery_adapter": "openai_compatible",
    },
]

PROVIDER_TEMPLATE_MAP = {
    item["provider_code"]: item
    for item in PROVIDER_TEMPLATES
}

PROVIDER_CODE_ALIASES = {
    "openai-compatible": "custom_openai",
    "bailian": "qwen",
    "kimi": "moonshot",
    "coding-plan": "dashscope_coding",
    "dashscope-coding": "dashscope_coding",
}

SUPPORTED_PROVIDER_CODES = set(PROVIDER_TEMPLATE_MAP) | set(PROVIDER_CODE_ALIASES)


def normalize_provider_code(provider_code: str) -> str:
    return PROVIDER_CODE_ALIASES.get(provider_code, provider_code)



def get_provider_template(provider_code: str) -> dict[str, Any] | None:
    normalized_code = normalize_provider_code(provider_code)
    template = PROVIDER_TEMPLATE_MAP.get(normalized_code)
    return deepcopy(template) if template else None



def list_provider_templates(*, model_type: str | None = None, keyword: str | None = None) -> list[dict[str, Any]]:
    templates = [deepcopy(item) for item in PROVIDER_TEMPLATES]
    if model_type:
        templates = [item for item in templates if model_type in item["supported_types"]]
    if keyword:
        lowered = keyword.lower()
        templates = [
            item
            for item in templates
            if lowered in item["provider_name"].lower() or lowered in item["provider_code"].lower()
        ]
    return templates
