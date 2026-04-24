import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from typing import Any

PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "adapter": "openai_compatible",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "env_key": "ANTHROPIC_API_KEY",
        "adapter": "anthropic_native",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com",
        "env_key": "GEMINI_API_KEY",
        "adapter": "gemini_native",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "env_key": "DEEPSEEK_API_KEY",
        "adapter": "openai_compatible",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "env_key": "QWEN_API_KEY",
        "adapter": "openai_compatible",
    },
}

TYPE_ORDER = ["llm", "embedding", "rerank", "vlm", "tts", "asr", "ocr", "moderation", "image", "unknown"]



def http_get_json(url: str, headers: dict[str, str], timeout: int = 20):
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"请求失败: {e}") from e



def normalize_model_id(model_id: str) -> str:
    if model_id.startswith("models/"):
        return model_id.split("/", 1)[1]
    return model_id



def sort_model_items(items: list[dict[str, Any]]):
    return sorted(items, key=lambda x: x["id"].lower())



def fetch_openai_compatible(base_url: str, api_key: str):
    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    _, data = http_get_json(url, headers)
    models = data.get("data", [])
    result = []
    for item in models:
        model_id = item.get("id")
        if model_id:
            result.append({"id": normalize_model_id(model_id), "raw": item})
    return sort_model_items(result)



def fetch_anthropic(base_url: str, api_key: str):
    url = base_url.rstrip("/") + "/v1/models"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    _, data = http_get_json(url, headers)
    models = data.get("data", [])
    result = []
    for item in models:
        model_id = item.get("id") or item.get("name")
        if model_id:
            result.append({"id": normalize_model_id(model_id), "raw": item})
    return sort_model_items(result)



def fetch_gemini(base_url: str, api_key: str):
    result = []
    next_token = None

    while True:
        query = {"key": api_key, "pageSize": 1000}
        if next_token:
            query["pageToken"] = next_token
        url = base_url.rstrip("/") + "/v1beta/models?" + urllib.parse.urlencode(query)
        _, data = http_get_json(url, headers={})
        for item in data.get("models", []):
            model_id = item.get("name")
            if model_id:
                result.append({"id": normalize_model_id(model_id), "raw": item})
        next_token = data.get("nextPageToken")
        if not next_token:
            break

    dedup = {item["id"]: item for item in result}
    return sort_model_items(list(dedup.values()))



def fetch_models(provider: str, base_url: str, api_key: str):
    adapter = PROVIDERS[provider]["adapter"]
    if adapter == "openai_compatible":
        return fetch_openai_compatible(base_url, api_key)
    if adapter == "anthropic_native":
        return fetch_anthropic(base_url, api_key)
    if adapter == "gemini_native":
        return fetch_gemini(base_url, api_key)
    raise ValueError(f"不支持的 adapter: {adapter}")



def add_type(types: list[str], model_type: str):
    if model_type not in types:
        types.append(model_type)



def infer_types_from_gemini_metadata(raw: dict[str, Any], types: list[str]):
    methods = [str(x).lower() for x in raw.get("supportedGenerationMethods", [])]
    if any("embed" in m for m in methods):
        add_type(types, "embedding")
    if any(m in methods for m in ["generatecontent", "streamgeneratecontent", "counttokens"]):
        add_type(types, "llm")



def infer_types_from_name(provider: str, model_id: str, raw: dict[str, Any]):
    text = model_id.lower()
    types: list[str] = []

    if provider == "anthropic":
        add_type(types, "llm")

    infer_types_from_gemini_metadata(raw, types)

    if "ocr" in text:
        add_type(types, "ocr")
    if "moderation" in text or "guard" in text:
        add_type(types, "moderation")
    if "embedding" in text or re.search(r"(^|[-_/])embed(ding)?($|[-_/])", text):
        add_type(types, "embedding")
    if "rerank" in text:
        add_type(types, "rerank")
    if any(k in text for k in ["transcribe", "transcription", "whisper", "speech-to-text", "asr", "stt"]):
        add_type(types, "asr")
    if any(k in text for k in ["text-to-speech", "tts", "speech-"]):
        add_type(types, "tts")
    if re.search(r"(^|[-_/])vl($|[-_/])", text) or any(k in text for k in ["vision", "multimodal", "omni"]):
        add_type(types, "vlm")
    if "image" in text and "ocr" not in text and not re.search(r"(^|[-_/])vl($|[-_/])", text):
        add_type(types, "image")

    if not types and any(
        k in text
        for k in [
            "chat",
            "instruct",
            "turbo",
            "plus",
            "max",
            "reason",
            "coder",
            "math",
            "longcontext",
            "thinking",
            "gpt",
            "claude",
            "gemini",
            "qwen",
            "deepseek",
            "kimi",
            "glm",
            "llama",
        ]
    ):
        add_type(types, "llm")

    if not types and provider in {"openai", "anthropic", "deepseek", "qwen", "gemini"}:
        add_type(types, "llm")

    return types or ["unknown"]



def classify_models(provider: str, model_items: list[dict[str, Any]]):
    result = []
    for item in model_items:
        model_id = item["id"]
        raw = item.get("raw", {})
        inferred_types = infer_types_from_name(provider, model_id, raw)
        result.append({"id": model_id, "types": inferred_types})
    return result



def print_result(provider: str, base_url: str, models: list[dict[str, Any]], group_by_type: bool):
    print(f"\n=== {provider} ===")
    print(f"base_url: {base_url}")
    print(f"model_count: {len(models)}")
    print("type_note: 模型类型为“元数据优先 + 名称规则兜底”的推断结果，不保证 100% 准确")

    if not group_by_type:
        for item in models:
            print(f"- {item['id']} [{', '.join(item['types'])}]")
        return

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in models:
        grouped[item["types"][0]].append(item)

    for model_type in TYPE_ORDER:
        if model_type not in grouped:
            continue
        print(f"\n[{model_type}] count={len(grouped[model_type])}")
        for item in grouped[model_type]:
            extra_types = item["types"][1:]
            suffix = f" ({', '.join(extra_types)})" if extra_types else ""
            print(f"- {item['id']}{suffix}")



def resolve_api_key(provider: str, cli_api_key: str | None):
    if cli_api_key:
        return cli_api_key
    env_key = PROVIDERS[provider]["env_key"]
    return os.getenv(env_key)



def run_one(provider: str, base_url: str | None, api_key: str | None, group_by_type: bool):
    actual_base_url = base_url or PROVIDERS[provider]["base_url"]
    actual_api_key = resolve_api_key(provider, api_key)

    if not actual_api_key:
        env_key = PROVIDERS[provider]["env_key"]
        print(f"[SKIP] {provider}: 未提供 API Key，请先设置环境变量 {env_key} 或使用 --api-key")
        return 2

    try:
        model_items = fetch_models(provider, actual_base_url, actual_api_key)
        classified_models = classify_models(provider, model_items)
        print_result(provider, actual_base_url, classified_models, group_by_type)
        return 0
    except Exception as e:
        print(f"[FAIL] {provider}: {e}")
        return 1



def main():
    parser = argparse.ArgumentParser(description="测试厂商 URL 是否能返回模型列表，并按模型类型进行推断分类")
    parser.add_argument(
        "--provider",
        required=True,
        choices=[*PROVIDERS.keys(), "all"],
        help="要测试的厂商，或使用 all 测试全部",
    )
    parser.add_argument("--api-key", help="单次测试时直接传入 API Key，可覆盖环境变量", default=None)
    parser.add_argument("--base-url", help="覆盖默认 base_url，仅对单个 provider 生效", default=None)
    parser.add_argument(
        "--flat",
        action="store_true",
        help="不按类型分组，直接打印“模型名 [推断类型]”",
    )
    args = parser.parse_args()

    if args.provider == "all":
        exit_code = 0
        for provider in PROVIDERS:
            code = run_one(provider, None, None, not args.flat)
            if code == 1:
                exit_code = 1
        sys.exit(exit_code)

    sys.exit(run_one(args.provider, args.base_url, args.api_key, not args.flat))


if __name__ == "__main__":
    main()
