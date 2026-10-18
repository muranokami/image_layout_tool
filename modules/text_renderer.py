"""テンプレートのtextレイヤーをボックス内に折り返し・整列して描画する"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _load_font(font_dir: str, font_name: str, size: int) -> ImageFont.FreeTypeFont:
    font_path = Path(font_dir) / font_name
    if not font_path.exists():
        raise FileNotFoundError(
            f"フォントが見つかりません: {font_path}\n"
            f"assets/fonts/ に日本語フォント（例: Noto Sans JP）を配置してください。"
        )
    return ImageFont.truetype(str(font_path), size=size)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """日本語は単語区切りが無いため、1文字ずつ幅を測って折り返す。
    改行コード（\\n）は明示的な改行として扱う。
    """
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for ch in paragraph:
            trial = current + ch
            w = draw.textbbox((0, 0), trial, font=font)[2]
            if w > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = trial
        if current:
            lines.append(current)
    return lines


def draw_text_layer(canvas: Image.Image, layer: dict, text: str, font_dir: str) -> None:
    """canvas（RGBA）に対し、layer定義の座標・スタイルでtextを描画する"""
    if not text:
        return

    x1, y1, x2, y2 = layer["box"]
    box_w, box_h = x2 - x1, y2 - y1

    font_size = int(layer.get("font_size", 40))
    font = _load_font(font_dir, layer["font"], font_size)
    color = tuple(layer.get("color", [0, 0, 0, 255]))
    align = layer.get("align", "left")
    valign = layer.get("valign", "top")
    line_spacing = float(layer.get("line_spacing", 1.2))

    draw = ImageDraw.Draw(canvas)
    lines = _wrap_text(draw, text, font, box_w)

    line_height = int(font_size * line_spacing)
    total_h = line_height * len(lines)

    if valign == "middle":
        cursor_y = y1 + max(0, (box_h - total_h) // 2)
    elif valign == "bottom":
        cursor_y = y2 - total_h
    else:
        cursor_y = y1

    for line in lines:
        line_w = draw.textbbox((0, 0), line, font=font)[2]
        if align == "center":
            cursor_x = x1 + max(0, (box_w - line_w) // 2)
        elif align == "right":
            cursor_x = x2 - line_w
        else:
            cursor_x = x1
        draw.text((cursor_x, cursor_y), line, font=font, fill=color)
        cursor_y += line_height
