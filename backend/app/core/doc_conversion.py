"""Legacy Word (.doc) → .docx conversion via LibreOffice headless."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from app.core.document_parser import UnsupportedDocumentError

logger = logging.getLogger(__name__)

_DOC_CONVERT_TIMEOUT_SEC = 120
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP_MAGIC = b"PK\x03\x04"
_DOCX_FILTERS = ("docx", "docx:MS Word 2007 XML", "docx:Office Open XML Text")


def _find_soffice_binary() -> str | None:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    return None


def libreoffice_available() -> bool:
    return _find_soffice_binary() is not None


def detect_doc_container(file_bytes: bytes) -> str:
    """Detect on-disk container for a file uploaded with a .doc extension."""
    if not file_bytes:
        return "empty"
    if file_bytes.startswith(_ZIP_MAGIC):
        return "docx_zip"
    if file_bytes[:8] == _OLE_MAGIC:
        return "ole"
    head = file_bytes.lstrip()[:16]
    if head.lower().startswith(b"{\\rtf"):
        return "rtf"
    sample = file_bytes[:512].lstrip().lower()
    if sample.startswith(b"<html") or sample.startswith(b"<!doctype") or b"<html" in sample[:256]:
        return "html"
    return "unknown"


def _source_suffix_for_container(container: str) -> str:
    return {"rtf": "rtf", "html": "html"}.get(container, "doc")


def _lo_combined_output(proc: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (proc.stdout, proc.stderr) if part).strip()


def _lo_error_lines(text: str) -> list[str]:
    errors: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"(?i)^error:", stripped):
            errors.append(stripped)
    return errors


def _pick_docx_output(tmp_path: Path, expected: Path) -> Path | None:
    if expected.is_file() and expected.stat().st_size > 0:
        return expected
    candidates = [
        path
        for path in tmp_path.rglob("*.docx")
        if path.is_file() and path.stat().st_size > 0
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _resolve_java_home() -> str | None:
    for candidate in (
        os.environ.get("JAVA_HOME"),
        "/opt/java",
        "/usr/lib/jvm/default-java",
    ):
        if not candidate:
            continue
        java_bin = Path(candidate) / "bin" / "java"
        if java_bin.is_file():
            return candidate
    return None


def _build_libreoffice_env(*, work_dir: Path, profile_dir: Path) -> dict[str, str]:
    """Headless LibreOffice 在容器内需要稳定的 HOME / Java / VCL 配置。"""
    env = os.environ.copy()
    env["HOME"] = str(work_dir / "lo-home")
    env.setdefault("LANG", "C.UTF-8")
    env.setdefault("LC_ALL", "C.UTF-8")
    # svp：无 GUI 的 VCL 插件，Docker 内比默认 headless 更稳
    env.setdefault("SAL_USE_VCLPLUGIN", "svp")
    env.setdefault("SAL_DISABLE_OPENCL", "1")
    java_home = _resolve_java_home()
    if java_home:
        env["JAVA_HOME"] = java_home
        env["PATH"] = f"{Path(java_home) / 'bin'}:{env.get('PATH', '')}"
    return env


def _run_soffice_convert(
    *,
    soffice: str,
    src: Path,
    out_dir: Path,
    env: dict[str, str],
    profile_uri: str,
    convert_filter: str,
    timeout_sec: int,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        soffice,
        "--headless",
        "--invisible",
        "--norestore",
        "--nolockcheck",
        "--nodefault",
        f"-env:UserInstallation={profile_uri}",
        "--convert-to",
        convert_filter,
        "--outdir",
        str(out_dir),
        str(src),
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        env=env,
        check=False,
    )


def _failure_hint(container: str, lo_errors: list[str]) -> str:
    joined = " ".join(lo_errors).lower()
    if "could not be loaded" in joined or "source file could not be loaded" in joined:
        return "LibreOffice 无法打开该文件，可能已损坏、受密码保护，或并非 Word 文档。请本地用 Word/WPS 打开并另存为 .docx 后重试。"
    if "no export filter" in joined:
        return "该 .doc 可能为网页/HTML 伪装的 Word 文件，LibreOffice 无法导出 docx。请另存为 .docx 后上传。"
    if container == "unknown":
        return "文件头不是常见 Word 格式（OLE/RTF/docx/HTML）。请确认扩展名与内容一致。"
    return "请用 Word/WPS 打开后另存为 .docx 再上传。"


def convert_doc_to_docx_bytes(
    file_bytes: bytes,
    *,
    source_name: str = "document.doc",
    log: Callable[[str], None] | None = None,
    timeout_sec: int = _DOC_CONVERT_TIMEOUT_SEC,
) -> bytes:
    """Convert binary .doc to .docx bytes using `soffice --headless`."""
    if not file_bytes:
        raise UnsupportedDocumentError(".doc 文件为空，无法转换")

    soffice = _find_soffice_binary()
    if not soffice:
        raise UnsupportedDocumentError(
            "未安装 LibreOffice（soffice），无法解析 .doc。"
            "请在 backend 镜像中安装 libreoffice-writer-nogui，或将文件另存为 .docx。"
        )

    safe_stem = Path(source_name).stem or "document"
    if not safe_stem.strip():
        safe_stem = "document"

    def _emit(msg: str) -> None:
        if log:
            log(msg)
        else:
            logger.info(msg)

    with tempfile.TemporaryDirectory(prefix="zs-rag-doc-convert-") as tmp:
        tmp_path = Path(tmp)
        container = detect_doc_container(file_bytes)
        if container == "docx_zip":
            _emit("检测到内容为 docx（ZIP）格式，跳过 LibreOffice 转换")
            return file_bytes

        source_suffix = _source_suffix_for_container(container)
        src = tmp_path / f"source.{source_suffix}"
        expected_out = tmp_path / f"source.docx"
        src.write_bytes(file_bytes)
        profile_dir = tmp_path / "lo-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "lo-home").mkdir(parents=True, exist_ok=True)
        env = _build_libreoffice_env(work_dir=tmp_path, profile_dir=profile_dir)
        profile_uri = profile_dir.resolve().as_uri()

        _emit(
            f"LibreOffice：正在将 .doc 转为 docx（格式={container}，超时 {timeout_sec}s）…"
        )
        last_output = ""
        last_errors: list[str] = []
        last_returncode = 0
        out: Path | None = None

        for convert_filter in _DOCX_FILTERS:
            try:
                proc = _run_soffice_convert(
                    soffice=soffice,
                    src=src,
                    out_dir=tmp_path,
                    env=env,
                    profile_uri=profile_uri,
                    convert_filter=convert_filter,
                    timeout_sec=timeout_sec,
                )
            except subprocess.TimeoutExpired as exc:
                raise UnsupportedDocumentError(f".doc 转 docx 超时（>{timeout_sec}s）") from exc

            last_returncode = proc.returncode
            last_output = _lo_combined_output(proc)
            last_errors = _lo_error_lines(last_output)
            out = _pick_docx_output(tmp_path, expected_out)
            if out is not None and last_returncode == 0 and not last_errors:
                break
            if out is not None and last_returncode == 0:
                break

        if out is None:
            detail = last_output[:500] if last_output else ""
            hint = _failure_hint(container, last_errors)
            err_msg = f".doc 转 docx 失败：未生成 docx 输出文件（文件「{safe_stem}」）"
            if last_errors:
                err_msg += "：" + "；".join(last_errors[:3])
            elif detail:
                err_msg += f"：{detail}"
            err_msg += f"。{hint}"
            raise UnsupportedDocumentError(err_msg)

        if last_returncode != 0:
            detail = last_output[:500] if last_output else ""
            raise UnsupportedDocumentError(
                f".doc 转 docx 失败（LibreOffice exit={last_returncode}，文件「{safe_stem}」）"
                + (f"：{detail}" if detail else "")
            )

        docx_bytes = out.read_bytes()
        if not docx_bytes:
            raise UnsupportedDocumentError(".doc 转 docx 失败：输出 docx 为空")
        _emit(f"LibreOffice：转换完成，docx 大小 {len(docx_bytes)} 字节")
        return docx_bytes
