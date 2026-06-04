"""知识库按文件类型的解析器配置与入库增强配置。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.errors import AppError

PDF_ENGINES = frozenset({"opendataloader", "mineru", "docling"})
PDF_RUNTIME_ENGINES = frozenset({"opendataloader", "mineru", "pypdf", "pypdf_fallback"})
PDF_FALLBACK_SEQUENCE = ("opendataloader", "mineru", "pypdf")
DOCX_ENGINES = frozenset({"python-docx", "mineru"})
EXCEL_ENGINES = frozenset({"html_table", "tsv", "mineru"})
CSV_ENGINES = frozenset({"standard", "mineru"})
TEXT_ENGINES = frozenset({"native", "mineru"})

DEFAULT_PARSERS: dict[str, dict[str, Any]] = {
    "pdf": {"engine": "opendataloader", "hybrid": False},
    "docx": {"engine": "python-docx"},
    "excel": {"engine": "html_table"},
    "csv": {"engine": "standard"},
    "text": {"engine": "native"},
}

DEFAULT_ENRICHMENT: dict[str, Any] = {
    "enabled": False,
    "llm_id": None,
    "generate_keywords": True,
    "generate_questions": True,
    "max_questions": 3,
}


@dataclass(frozen=True)
class ParserOptions:
    pdf_engine: str
    pdf_hybrid: bool
    docx_engine: str
    excel_engine: str
    csv_engine: str
    text_engine: str


@dataclass(frozen=True)
class EnrichmentOptions:
    enabled: bool
    llm_id: int | None
    generate_keywords: bool
    generate_questions: bool
    max_questions: int


def _merge_parser_section(defaults: dict[str, Any], override: Any) -> dict[str, Any]:
    merged = dict(defaults)
    if isinstance(override, dict):
        merged.update(override)
    return merged


def kb_config_for_pdf_legacy(kb_config: dict[str, Any] | None) -> dict[str, Any]:
    """将 config.parsers.pdf 同步到 resolve_pdf_parser 可读的顶层键（读路径兼容）。"""
    cfg = dict(kb_config or {})
    parsers = cfg.get("parsers")
    if isinstance(parsers, dict):
        pdf = parsers.get("pdf")
        if isinstance(pdf, dict):
            engine = pdf.get("engine")
            if isinstance(engine, str) and engine.strip():
                cfg["pdf_parser"] = engine.strip().lower()
            if pdf.get("hybrid") is True:
                cfg["pdf_parser_hybrid"] = True
            elif pdf.get("hybrid") is False:
                cfg["pdf_parser_hybrid"] = False
    return cfg


def resolve_parsers(kb_config: dict[str, Any] | None) -> ParserOptions:
    cfg = kb_config if isinstance(kb_config, dict) else {}
    parsers_raw = cfg.get("parsers")
    parsers: dict[str, Any] = {}
    if isinstance(parsers_raw, dict):
        parsers = parsers_raw

    docx_cfg = _merge_parser_section(DEFAULT_PARSERS["docx"], parsers.get("docx"))
    excel_cfg = _merge_parser_section(DEFAULT_PARSERS["excel"], parsers.get("excel"))
    csv_cfg = _merge_parser_section(DEFAULT_PARSERS["csv"], parsers.get("csv"))
    text_cfg = _merge_parser_section(DEFAULT_PARSERS["text"], parsers.get("text"))

    from app.core.opendataloader_gateway import resolve_pdf_parser, resolve_pdf_parser_hybrid

    legacy_cfg = kb_config_for_pdf_legacy(cfg)
    pdf_engine = resolve_pdf_parser(legacy_cfg)
    pdf_hybrid = resolve_pdf_parser_hybrid(legacy_cfg) if pdf_engine == "opendataloader" else False

    docx_engine = str(docx_cfg.get("engine") or DEFAULT_PARSERS["docx"]["engine"]).strip().lower()
    excel_engine = str(excel_cfg.get("engine") or DEFAULT_PARSERS["excel"]["engine"]).strip().lower()
    csv_engine = str(csv_cfg.get("engine") or DEFAULT_PARSERS["csv"]["engine"]).strip().lower()
    text_engine = str(text_cfg.get("engine") or DEFAULT_PARSERS["text"]["engine"]).strip().lower()

    if docx_engine not in DOCX_ENGINES:
        docx_engine = DEFAULT_PARSERS["docx"]["engine"]
    if excel_engine not in EXCEL_ENGINES:
        excel_engine = DEFAULT_PARSERS["excel"]["engine"]
    if csv_engine not in CSV_ENGINES:
        csv_engine = DEFAULT_PARSERS["csv"]["engine"]
    if text_engine not in TEXT_ENGINES:
        text_engine = DEFAULT_PARSERS["text"]["engine"]

    return ParserOptions(
        pdf_engine=pdf_engine,
        pdf_hybrid=pdf_hybrid,
        docx_engine=docx_engine,
        excel_engine=excel_engine,
        csv_engine=csv_engine,
        text_engine=text_engine,
    )


def resolve_pdf_fallback_chain(primary: str | None) -> list[str]:
    """
    PDF 解析降级顺序：首选配置引擎，再按 opendataloader → mineru → pypdf 尝试。
    docling 尚未接入运行时，跳过。
    """
    from app.core.config import get_settings

    norm = (primary or "opendataloader").strip().lower()
    if norm not in PDF_ENGINES and norm != "pypdf":
        norm = "opendataloader"

    settings = get_settings()
    chain: list[str] = []
    for eng in (norm, *PDF_FALLBACK_SEQUENCE):
        if eng == "docling":
            continue
        if eng in chain:
            continue
        if eng == "mineru" and not settings.mineru_enabled:
            continue
        if eng == "opendataloader" and not settings.odl_enabled:
            continue
        chain.append(eng)
    if "pypdf" not in chain:
        chain.append("pypdf")
    return chain


def parser_engine_display_name(engine: str | None, *, fallback: bool = False) -> str:
    key = (engine or "").strip().lower()
    labels = {
        "opendataloader": "OpenDataLoader",
        "mineru": "MinerU",
        "docling": "Docling",
        "pypdf": "pypdf",
        "pypdf_fallback": "pypdf",
        "python-docx": "python-docx",
        "html_table": "HTML 表格",
        "tsv": "TSV",
        "standard": "CSV",
        "native": "文本",
    }
    label = labels.get(key, key.upper() if key else "—")
    if fallback and key in {
        "mineru",
        "pypdf",
        "pypdf_fallback",
        "opendataloader",
        "html_table",
        "tsv",
    }:
        return f"{label}（降级）"
    return label


def resolve_enrichment(kb_config: dict[str, Any] | None) -> EnrichmentOptions:
    cfg = kb_config if isinstance(kb_config, dict) else {}
    raw = cfg.get("enrichment")
    merged = dict(DEFAULT_ENRICHMENT)
    if isinstance(raw, dict):
        merged.update(raw)

    enabled = merged.get("enabled") is True
    llm_id_raw = merged.get("llm_id")
    llm_id: int | None = None
    if llm_id_raw is not None and str(llm_id_raw).strip() != "":
        try:
            llm_id = int(llm_id_raw)
        except (TypeError, ValueError):
            llm_id = None

    max_q = merged.get("max_questions", DEFAULT_ENRICHMENT["max_questions"])
    try:
        max_questions = max(1, min(5, int(max_q)))
    except (TypeError, ValueError):
        max_questions = int(DEFAULT_ENRICHMENT["max_questions"])

    return EnrichmentOptions(
        enabled=enabled,
        llm_id=llm_id,
        generate_keywords=merged.get("generate_keywords") is not False,
        generate_questions=merged.get("generate_questions") is not False,
        max_questions=max_questions,
    )


def validate_parsers_patch(parsers: dict[str, Any]) -> None:
    for key, allowed in (
        ("pdf", PDF_ENGINES),
        ("docx", DOCX_ENGINES),
        ("excel", EXCEL_ENGINES),
        ("csv", CSV_ENGINES),
        ("text", TEXT_ENGINES),
    ):
        section = parsers.get(key)
        if not isinstance(section, dict):
            continue
        engine = section.get("engine")
        if engine is not None:
            norm = str(engine).strip().lower()
            if norm not in allowed:
                raise AppError(
                    status_code=400,
                    code="INVALID_PARSER_ENGINE",
                    message=f"parsers.{key}.engine 须为 {', '.join(sorted(allowed))} 之一",
                )
            if norm == "mineru":
                from app.core.config import get_settings

                if not get_settings().mineru_enabled:
                    raise AppError(
                        status_code=400,
                        code="MINERU_NOT_ENABLED",
                        message="MinerU 未启用。请在 .env 中设置 MINERU_ENABLED=true 并启动 mineru 服务后再选择 MinerU 解析器。",
                    )
        if key == "pdf" and section.get("hybrid") is not None and not isinstance(section.get("hybrid"), bool):
            raise AppError(status_code=400, code="INVALID_PARSER_CONFIG", message="parsers.pdf.hybrid 须为 boolean")


def validate_enrichment_patch(enrichment: dict[str, Any]) -> None:
    if enrichment.get("enabled") is not None and not isinstance(enrichment.get("enabled"), bool):
        raise AppError(status_code=400, code="INVALID_ENRICHMENT_CONFIG", message="enrichment.enabled 须为 boolean")
    llm_id = enrichment.get("llm_id")
    if llm_id is not None and str(llm_id).strip() != "":
        try:
            int(llm_id)
        except (TypeError, ValueError):
            raise AppError(status_code=400, code="INVALID_ENRICHMENT_CONFIG", message="enrichment.llm_id 须为整数或 null")
    max_q = enrichment.get("max_questions")
    if max_q is not None:
        try:
            q = int(max_q)
        except (TypeError, ValueError):
            raise AppError(status_code=400, code="INVALID_ENRICHMENT_CONFIG", message="enrichment.max_questions 须为整数")
        if q < 1 or q > 5:
            raise AppError(status_code=400, code="INVALID_ENRICHMENT_CONFIG", message="enrichment.max_questions 须在 1–5 之间")
