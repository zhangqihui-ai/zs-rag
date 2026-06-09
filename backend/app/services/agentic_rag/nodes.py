from __future__ import annotations

import json
import re
import time
from typing import Any

from app.core.config import get_settings
from app.schemas.retrieval import KnowledgeSearchRequest
from app.services.chat_service import (
    DEFAULT_CHAT_SYSTEM_PROMPT_GENERAL,
    DEFAULT_CHAT_SYSTEM_PROMPT_RAG,
    should_skip_knowledge_retrieval,
)
from app.services.retrieval_service import search_knowledge_bases_multi

from .prompts import GENERAL_DIRECT_PROMPT, GRADE_PROMPT, REWRITE_PROMPT, ROUTE_PROMPT
from .state import AgenticRAGState

settings = get_settings()


def _trace(state: AgenticRAGState, step: str, detail: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(state.get("trace") or [])
    rows.append({"step": step, "elapsed_ms": detail.pop("elapsed_ms", None), **detail})
    return rows


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        raw = match.group(0)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    match = re.search(r"\[[\s\S]*\]", raw)
    if match:
        raw = match.group(0)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [item for item in obj if isinstance(item, dict)] if isinstance(obj, list) else []


def _extract_assistant_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    msg = first.get("message")
    if isinstance(msg, dict) and msg.get("content") is not None:
        return str(msg.get("content") or "")
    return ""


def _chat_once(state: AgenticRAGState, messages: list[dict[str, str]], *, timeout: float = 45.0) -> str:
    provider = state["llm_provider"]
    resp = provider.chat(
        state["llm_model_name"],
        messages,
        timeout=timeout,
        temperature=state.get("temperature"),
        max_tokens=state.get("max_tokens"),
        top_p=state.get("top_p"),
    )
    if not resp.success:
        return ""
    return _extract_assistant_text(resp.data)


def _parse_route_response(content: str) -> tuple[str, str, str]:
    parsed = _extract_json_object(content)
    decision = str(parsed.get("decision") or "retrieve").strip().lower()
    if decision not in {"retrieve", "direct"}:
        decision = "retrieve"
    reason = str(parsed.get("reason") or "默认进入知识库检索").strip()
    confidence = str(parsed.get("confidence") or "high").strip().lower()
    if confidence not in {"high", "low"}:
        confidence = "high"
    return decision, reason, confidence


def _format_chat_history_for_route(state: AgenticRAGState, *, max_turns: int = 2, max_chars: int = 200) -> str:
    history = list(state.get("chat_history") or [])
    if not history:
        return ""
    tail: list[str] = []
    for item in history[-max_turns * 2 :]:
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        label = "用户" if role == "user" else "助手"
        snippet = content if len(content) <= max_chars else content[: max_chars - 1] + "…"
        tail.append(f"{label}：{snippet}")
    return "\n".join(tail)


def _build_route_user_message(
    state: AgenticRAGState,
    *,
    pre_retrieval_summary: str | None = None,
) -> str:
    question = (state.get("question") or "").strip()
    parts = [f"用户问题：{question}"]
    kb_context = str(state.get("kb_context") or "").strip()
    if kb_context:
        parts.append(f"已选知识库范围：\n{kb_context}")
    history_block = _format_chat_history_for_route(state)
    if history_block:
        parts.append(f"最近对话摘要：\n{history_block}")
    if pre_retrieval_summary:
        parts.append(f"预检索试探结果：\n{pre_retrieval_summary}")
    return "\n\n".join(parts)


def _call_route_llm(state: AgenticRAGState, user_content: str) -> tuple[str, str, str]:
    content = _chat_once(
        state,
        [
            {"role": "system", "content": ROUTE_PROMPT},
            {"role": "user", "content": user_content},
        ],
        timeout=20.0,
    )
    return _parse_route_response(content)


def _format_pre_retrieval_summary(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "（无召回片段）"
    lines: list[str] = []
    for idx, item in enumerate(candidates, start=1):
        doc = str(item.get("document_name") or "文献")
        score = item.get("score")
        preview_raw = item.get("content_preview") or item.get("content") or ""
        preview = str(preview_raw).strip()[:200]
        lines.append(f"[{idx}] 《{doc}》 score={score}\n{preview}")
    return "\n\n".join(lines)


def _run_pre_retrieve(state: AgenticRAGState) -> list[dict[str, Any]]:
    kb_ids = list(state.get("knowledge_base_ids") or [])
    if not kb_ids:
        return []
    query = (state.get("question") or "").strip()
    top_k = int(settings.agentic_route_pre_retrieve_top_k)
    payload = KnowledgeSearchRequest(
        query=query[:2000],
        mode=state.get("retrieval_mode"),
        top_k=top_k,
        score_threshold=state.get("score_threshold"),
        vector_weight=state.get("vector_weight"),
        fusion_method=state.get("fusion_method"),
        include_image_ocr=state.get("include_image_ocr"),
    )
    data = search_knowledge_bases_multi(
        state["db"],
        space_id=int(state["enterprise_space_id"]),
        knowledge_base_ids=kb_ids,
        payload=payload,
    )
    return [dict(item) for item in data.get("results") or []]


def _candidate_chunk_key(item: dict[str, Any]) -> str:
    chunk_id = item.get("chunk_id")
    if chunk_id is not None:
        return f"chunk:{chunk_id}"
    doc_id = item.get("document_id")
    chunk_index = item.get("chunk_index")
    if doc_id is not None and chunk_index is not None:
        return f"doc:{doc_id}:{chunk_index}"
    content = str(item.get("content") or "")[:80]
    doc = str(item.get("document_name") or "")
    return f"fallback:{doc}:{content}"


def _merge_candidates_by_chunk_id(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*secondary, *primary]:
        key = _candidate_chunk_key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))
    return merged


def route_node(state: AgenticRAGState) -> dict[str, Any]:
    started = time.perf_counter()
    question = (state.get("question") or "").strip()
    kb_ids = list(state.get("knowledge_base_ids") or [])
    kb_context = str(state.get("kb_context") or "").strip()
    trace_rows = list(state.get("trace") or [])

    if not kb_ids:
        trace_rows.append(
            {
                "step": "route",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "decision": "direct",
                "reason": "未绑定知识库，直接大模型对话",
                "route_pass": 1,
            }
        )
        return {
            "route_decision": "direct",
            "route_reason": "未绑定知识库，直接大模型对话",
            "pre_retrieval_candidates": [],
            "trace": trace_rows,
        }

    if should_skip_knowledge_retrieval(question):
        trace_rows.append(
            {
                "step": "route",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "decision": "direct",
                "reason": "规则命中闲聊/身份类问题，无需检索",
                "route_pass": 1,
            }
        )
        return {
            "route_decision": "direct",
            "route_reason": "规则命中闲聊/身份类问题，无需检索",
            "pre_retrieval_candidates": [],
            "trace": trace_rows,
        }

    pass1_started = time.perf_counter()
    decision, reason, confidence = _call_route_llm(state, _build_route_user_message(state))
    trace_rows.append(
        {
            "step": "route",
            "elapsed_ms": round((time.perf_counter() - pass1_started) * 1000, 2),
            "decision": decision,
            "reason": reason,
            "confidence": confidence,
            "route_pass": 1,
            "kb_context_chars": len(kb_context),
        }
    )

    pre_candidates: list[dict[str, Any]] = []
    pre_enabled = bool(state.get("route_pre_retrieve_enabled", settings.agentic_route_pre_retrieve_enabled))
    need_pre = pre_enabled and decision == "retrieve"

    if need_pre:
        pre_started = time.perf_counter()
        pre_candidates = _run_pre_retrieve(state)
        pre_summary = _format_pre_retrieval_summary(pre_candidates)
        pass2_started = time.perf_counter()
        decision, reason, confidence = _call_route_llm(
            state,
            _build_route_user_message(state, pre_retrieval_summary=pre_summary),
        )
        trace_rows.append(
            {
                "step": "route_refine",
                "elapsed_ms": round((time.perf_counter() - pass2_started) * 1000, 2),
                "decision": decision,
                "reason": reason,
                "confidence": confidence,
                "route_pass": 2,
                "pre_retrieve_total": len(pre_candidates),
                "pre_retrieve_elapsed_ms": round((time.perf_counter() - pre_started) * 1000, 2),
            }
        )

    return {
        "route_decision": decision,
        "route_reason": reason,
        "pre_retrieval_candidates": pre_candidates,
        "trace": trace_rows,
    }


def retrieve_node(state: AgenticRAGState) -> dict[str, Any]:
    started = time.perf_counter()
    query = (state.get("current_query") or state.get("question") or "").strip()
    kb_ids = list(state.get("knowledge_base_ids") or [])
    iterations = int(state.get("iterations") or 0) + 1
    if not kb_ids:
        return {
            "current_query": query,
            "candidates": [],
            "iterations": iterations,
            "trace": _trace(
                state,
                "retrieve",
                {
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "query": query,
                    "total": 0,
                    "iteration": iterations,
                },
            ),
        }
    payload = KnowledgeSearchRequest(
        query=query[:2000],
        mode=state.get("retrieval_mode"),
        top_k=int(state.get("top_k") or 8),
        score_threshold=state.get("score_threshold"),
        vector_weight=state.get("vector_weight"),
        fusion_method=state.get("fusion_method"),
        include_image_ocr=state.get("include_image_ocr"),
    )
    data = search_knowledge_bases_multi(
        state["db"],
        space_id=int(state["enterprise_space_id"]),
        knowledge_base_ids=list(state.get("knowledge_base_ids") or []),
        payload=payload,
    )
    candidates = [dict(item) for item in data.get("results") or []]
    if iterations == 1:
        pre_candidates = list(state.get("pre_retrieval_candidates") or [])
        if pre_candidates:
            candidates = _merge_candidates_by_chunk_id(candidates, pre_candidates)
    return {
        "current_query": query,
        "candidates": candidates,
        "iterations": iterations,
        "trace": _trace(
            state,
            "retrieve",
            {
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "query": query,
                "total": len(candidates),
                "iteration": iterations,
            },
        ),
    }


def grade_node(state: AgenticRAGState) -> dict[str, Any]:
    started = time.perf_counter()
    question = (state.get("question") or "").strip()
    candidates = list(state.get("candidates") or [])
    if not candidates:
        return {
            "graded_docs": [],
            "relevant_docs": [],
            "trace": _trace(
                state,
                "grade",
                {
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "relevant_count": 0,
                    "total": 0,
                },
            ),
        }

    blocks: list[str] = []
    for idx, item in enumerate(candidates, start=1):
        doc = str(item.get("document_name") or "文献")
        content = str(item.get("content") or "")[:900]
        score = item.get("score")
        blocks.append(f"[{idx}] 文档：{doc}\n检索分：{score}\n片段：{content}")
    raw = _chat_once(
        state,
        [
            {"role": "system", "content": GRADE_PROMPT},
            {"role": "user", "content": f"用户问题：{question}\n\n候选片段：\n" + "\n\n".join(blocks)},
        ],
        timeout=45.0,
    )
    grade_rows = _extract_json_array(raw)
    by_index: dict[int, dict[str, Any]] = {}
    for row in grade_rows:
        try:
            index = int(row.get("index"))
        except (TypeError, ValueError):
            continue
        by_index[index] = row

    graded_docs: list[dict[str, Any]] = []
    relevant_docs: list[dict[str, Any]] = []
    for idx, item in enumerate(candidates, start=1):
        row = by_index.get(idx) or {}
        score_raw = row.get("score")
        try:
            grade_score = int(score_raw)
        except (TypeError, ValueError):
            grade_score = 1 if float(item.get("score") or 0) >= 0.3 else 0
        relevant = bool(row.get("relevant")) or grade_score >= 1
        merged = dict(item)
        merged["agentic_grade"] = {
            "relevant": relevant,
            "score": max(0, min(2, grade_score)),
            "reason": str(row.get("reason") or "").strip(),
        }
        graded_docs.append(merged)
        if relevant:
            relevant_docs.append(merged)

    return {
        "graded_docs": graded_docs,
        "relevant_docs": relevant_docs,
        "trace": _trace(
            state,
            "grade",
            {
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "relevant_count": len(relevant_docs),
                "total": len(candidates),
            },
        ),
    }


def rewrite_node(state: AgenticRAGState) -> dict[str, Any]:
    started = time.perf_counter()
    question = (state.get("question") or "").strip()
    current_query = (state.get("current_query") or question).strip()
    candidates = list(state.get("candidates") or [])[:5]
    snippets = "\n\n".join(
        f"- {str(item.get('document_name') or '文献')}：{str(item.get('content') or '')[:260]}"
        for item in candidates
    )
    rewritten = _chat_once(
        state,
        [
            {"role": "system", "content": REWRITE_PROMPT},
            {
                "role": "user",
                "content": (
                    f"原始问题：{question}\n当前查询：{current_query}\n"
                    f"上一轮弱相关片段：\n{snippets or '无'}"
                ),
            },
        ],
        timeout=30.0,
    ).strip()
    rewritten = re.sub(r"^['\"“”]+|['\"“”]+$", "", rewritten).strip() or current_query
    return {
        "current_query": rewritten[:2000],
        "candidates": [],
        "graded_docs": [],
        "relevant_docs": [],
        "trace": _trace(
            state,
            "rewrite",
            {
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "from": current_query,
                "to": rewritten[:2000],
            },
        ),
    }


def _build_citations(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for ref, item in enumerate(docs, start=1):
        cite_raw = item.get("citation")
        cite = cite_raw if isinstance(cite_raw, dict) else {}
        citations.append(
            {
                "ref": ref,
                "document_name": str(item.get("document_name") or cite.get("document_name") or "文献"),
                "page_no": cite.get("page_no"),
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "chunk_index": item.get("chunk_index"),
                "knowledge_base_id": item.get("knowledge_base_id"),
                "score": round(float(item.get("score") or 0), 4),
                "source": "agentic",
                "content": item.get("content"),
                "agentic_grade": item.get("agentic_grade"),
            }
        )
    return citations


def _knowledge_block(docs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for ref, item in enumerate(docs, start=1):
        doc = str(item.get("document_name") or "文献")
        content = str(item.get("content") or "").strip()
        parts.append(f"[{ref}] 《{doc}》\n{content}")
    return "\n\n---\n\n".join(parts)


def generate_node(state: AgenticRAGState) -> dict[str, Any]:
    started = time.perf_counter()
    relevant_docs = list(state.get("relevant_docs") or [])
    citations = _build_citations(relevant_docs)
    knowledge = _knowledge_block(relevant_docs)
    question = (state.get("question") or "").strip()
    if knowledge:
        system_prompt = DEFAULT_CHAT_SYSTEM_PROMPT_RAG.strip().replace("{knowledge}", knowledge)
    elif not list(state.get("knowledge_base_ids") or []):
        system_prompt = DEFAULT_CHAT_SYSTEM_PROMPT_GENERAL.strip()
    else:
        system_prompt = GENERAL_DIRECT_PROMPT
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for item in list(state.get("chat_history") or []):
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})

    provider = state["llm_provider"]
    parts: list[str] = []
    for chunk in provider.chat_stream_chunks(
        state["llm_model_name"],
        messages,
        temperature=state.get("temperature"),
        max_tokens=state.get("max_tokens"),
        top_p=state.get("top_p"),
    ):
        parts.append(str(chunk))
    answer = "".join(parts).strip()
    return {
        "answer": answer,
        "citations": citations,
        "trace": _trace(
            state,
            "generate",
            {
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "citation_count": len(citations),
                "answer_chars": len(answer),
            },
        ),
    }


def should_retrieve_after_route(state: AgenticRAGState) -> str:
    return "retrieve" if state.get("route_decision") == "retrieve" else "generate"


def should_rewrite_or_generate(state: AgenticRAGState) -> str:
    relevant_count = len(state.get("relevant_docs") or [])
    min_relevant = int(state.get("min_relevant_docs") or 1)
    iterations = int(state.get("iterations") or 0)
    max_iterations = int(state.get("max_iterations") or 2)
    if relevant_count >= min_relevant:
        return "generate"
    if iterations < max_iterations:
        return "rewrite"
    return "generate"
