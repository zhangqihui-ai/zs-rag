"""验证：关闭 MinerU 时解析图片应直接抛出 UnsupportedDocumentError（不产出空 doc）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import mineru_gateway as mg  # noqa: E402
from app.core.document_parser import UnsupportedDocumentError, parse_document  # noqa: E402


def log(msg: str) -> None:
    print(msg, flush=True)


def main(image_path: str) -> None:
    with open(image_path, "rb") as f:
        data = f.read()

    # 强制覆盖单例为 enabled=False，模拟 MINERU_ENABLED=false 场景
    mg._gateway_singleton = mg.MineruGateway(
        enabled=False,
        base_url="",
        backend="pipeline",
        lang="ch",
        timeout=10,
        format_whitelist=set(),
    )

    try:
        parse_document(image_path.rsplit("/", 1)[-1], data, log=log)
    except UnsupportedDocumentError as e:
        log(f"[OK] 命中 UnsupportedDocumentError：{e.message}")
        return
    except Exception as e:  # pragma: no cover
        log(f"[FAIL] 异常类型错误：{type(e).__name__}: {e}")
        sys.exit(1)

    log("[FAIL] 没有抛出异常")
    sys.exit(1)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test_image.png"
    main(path)
