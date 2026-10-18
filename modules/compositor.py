"""テンプレート定義に従い、背景・イラスト・商品写真・テキストを合成するモジュール"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .text_renderer import draw_text_layer


def _fit_image(img: Image.Image, box_w: int, box_h: int, fit: str) -> Image.Image:
    """box(幅box_w,高さbox_h)に対し、cover(はみ出しを切る)/contain(全体を収める)でリサイズ"""
    img = img.convert("RGBA")
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    box_ratio = box_w / box_h

    if fit == "cover":
        if src_ratio > box_ratio:
            new_h = box_h
            new_w = int(box_h * src_ratio)
        else:
            new_w = box_w
            new_h = int(box_w / src_ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - box_w) // 2
        top = (new_h - box_h) // 2
        return resized.crop((left, top, left + box_w, top + box_h))

    # contain（デフォルト）：アスペクト比を保ったまま収める。余白は透明
    if src_ratio > box_ratio:
        new_w = box_w
        new_h = int(box_w / src_ratio)
    else:
        new_h = box_h
        new_w = int(box_h * src_ratio)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    offset = ((box_w - new_w) // 2, (box_h - new_h) // 2)
    canvas.paste(resized, offset, resized)
    return canvas


def compose(
    template: dict,
    *,
    product_image_path: str,
    background_image: Image.Image | None,
    illustration_image: Image.Image | None,
    text_fields: dict[str, str],
    font_dir: str,
) -> Image.Image:
    """1件分の最終画像を合成して返す（RGBA）"""
    canvas_cfg = template["canvas"]
    W, H = canvas_cfg["width"], canvas_cfg["height"]
    bg_color = tuple(canvas_cfg.get("background_color", [255, 255, 255, 255]))
    canvas = Image.new("RGBA", (W, H), bg_color)

    product_img = Image.open(product_image_path).convert("RGBA")

    layers = sorted(template["layers"], key=lambda ly: ly.get("z", 0))

    for layer in layers:
        ltype = layer["type"]
        x1, y1, x2, y2 = layer["box"]
        box_w, box_h = x2 - x1, y2 - y1

        if ltype == "background":
            if background_image is None:
                continue
            fitted = _fit_image(background_image, box_w, box_h, layer.get("fit", "cover"))
            canvas.alpha_composite(fitted, (x1, y1))

        elif ltype == "illustration":
            if illustration_image is None:
                continue
            fitted = _fit_image(illustration_image, box_w, box_h, layer.get("fit", "cover"))
            opacity = float(layer.get("opacity", 1.0))
            if opacity < 1.0:
                alpha = fitted.getchannel("A").point(lambda a: int(a * opacity))
                fitted.putalpha(alpha)
            canvas.alpha_composite(fitted, (x1, y1))

        elif ltype == "product_image":
            fitted = _fit_image(product_img, box_w, box_h, layer.get("fit", "contain"))
            canvas.alpha_composite(fitted, (x1, y1))

        elif ltype == "text":
            field = layer.get("field", "")
            text = text_fields.get(field, "")
            draw_text_layer(canvas, layer, text, font_dir)

        else:
            raise ValueError(f"未知のレイヤータイプです: {ltype}")

    return canvas


def save_output(image: Image.Image, output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "PNG")
