"""生成一张包含中文标题+正文的测试图，供 MinerU OCR/版面分析联调使用。"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

OUT = "/tmp/test_image.png"
CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def main() -> None:
    img = Image.new("RGB", (900, 640), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype(CJK, 42)
    mid = ImageFont.truetype(CJK, 28)
    sml = ImageFont.truetype(CJK, 22)

    lines: list[tuple[int, int, str, ImageFont.FreeTypeFont]] = [
        (40, 30, "第一章 系统概述", big),
        (60, 110, "1.1 架构设计", mid),
        (60, 160, "本系统采用微服务架构，核心模块包括用户、知识库、检索服务。", sml),
        (60, 200, "检索支持向量、全文、混合三种模式。", sml),
        (40, 290, "第二章 接入流程", big),
        (60, 370, "2.1 注册与鉴权", mid),
        (60, 420, "用户注册后通过 JWT 获取 API Token。", sml),
        (60, 460, "所有业务请求需携带 Authorization 头。", sml),
    ]
    for x, y, text, font in lines:
        d.text((x, y), text, fill=(0, 0, 0), font=font)
    img.save(OUT)
    print("saved:", OUT, "size:", img.size)


if __name__ == "__main__":
    main()
