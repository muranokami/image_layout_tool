#!/usr/bin/env python3
"""商品画像レイアウト自動合成ツール — バッチ実行スクリプト

使い方:
    python main.py --input data/sample_input.csv --output-dir output
    python main.py --input data/products.xlsx --limit 10 --dry-run
    python main.py --input data/products.xlsx --only-failed
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import yaml
from tqdm import tqdm

from modules.ai_generator import AIGenerator, AIGeneratorError
from modules.compositor import compose, save_output
from modules.data_loader import load_rows
from modules.utils import setup_logger

BASE_DIR = Path(__file__).parent
LOG_CSV = BASE_DIR / "logs" / "run_log.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="商品画像レイアウト自動合成ツール")
    p.add_argument("--input", required=True, help="入力Excel(.xlsx)またはCSVのパス")
    p.add_argument("--output-dir", default="output", help="出力先フォルダ")
    p.add_argument("--settings", default="config/settings.yaml", help="設定ファイルのパス")
    p.add_argument("--templates-dir", default="config/templates", help="テンプレート格納フォルダ")
    p.add_argument("--limit", type=int, default=None, help="先頭N件のみ処理（動作確認用）")
    p.add_argument("--force", action="store_true", help="既存の出力があっても再生成する")
    p.add_argument("--only-failed", action="store_true", help="前回失敗した行だけ再実行する")
    p.add_argument("--dry-run", action="store_true", help="AI生成・合成をせず処理内容だけ表示する")
    return p.parse_args()


def load_settings(path: str) -> dict:
    settings_path = Path(path)
    if not settings_path.exists():
        example = settings_path.with_name("settings.example.yaml")
        raise FileNotFoundError(
            f"設定ファイルが見つかりません: {settings_path}\n"
            f"{example} をコピーして作成してください。"
        )
    with open(settings_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_template(templates_dir: str, template_id: str) -> dict:
    path = Path(templates_dir) / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"テンプレートが見つかりません: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_previous_log() -> dict[str, str]:
    """id -> status('success'/'error') の前回実行結果を読む"""
    if not LOG_CSV.exists():
        return {}
    result: dict[str, str] = {}
    with open(LOG_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            result[row["id"]] = row["status"]
    return result


def append_log(row_id: str, status: str, message: str) -> None:
    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    is_new = not LOG_CSV.exists()
    with open(LOG_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "id", "status", "message"])
        writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), row_id, status, message])


def main() -> int:
    args = parse_args()
    logger = setup_logger()

    try:
        rows = load_rows(args.input)
    except Exception as e:  # noqa: BLE001
        logger.error(f"入力データの読み込みに失敗しました: {e}")
        return 1

    if args.limit:
        rows = rows[: args.limit]

    if args.only_failed:
        prev = read_previous_log()
        rows = [r for r in rows if prev.get(r["id"]) != "success"]

    logger.info(f"処理対象: {len(rows)}件")

    if args.dry_run:
        for r in rows:
            logger.info(f"[dry-run] id={r['id']} template={r['template_id']} -> {r['output_filename']}")
        return 0

    try:
        settings = load_settings(args.settings)
    except Exception as e:  # noqa: BLE001
        logger.error(str(e))
        return 1

    font_dir = settings.get("font_dir", "assets/fonts")
    ai = AIGenerator(settings)

    template_cache: dict[str, dict] = {}
    ok_count = 0
    err_count = 0

    for row in tqdm(rows, desc="合成処理", unit="件"):
        row_id = row["id"]
        output_path = str(Path(args.output_dir) / row["output_filename"])

        if not args.force and Path(output_path).exists():
            logger.info(f"[skip] {row_id}: 出力済みのためスキップ（--forceで再生成）")
            continue

        try:
            if row["template_id"] not in template_cache:
                template_cache[row["template_id"]] = load_template(args.templates_dir, row["template_id"])
            template = template_cache[row["template_id"]]

            if not Path(row["product_image_path"]).exists():
                raise FileNotFoundError(f"商品画像が見つかりません: {row['product_image_path']}")

            # 背景: 既存アセット優先、なければプロンプトからAI生成
            background_image = None
            if row["bg_asset_path"]:
                background_image = __import__("PIL.Image", fromlist=["Image"]).open(row["bg_asset_path"])
            elif row["bg_prompt"]:
                background_image = ai.generate(row["bg_prompt"])

            # イラスト: 既存アセット優先、なければプロンプトからAI生成
            illustration_image = None
            if row["illust_asset_path"]:
                illustration_image = __import__("PIL.Image", fromlist=["Image"]).open(row["illust_asset_path"])
            elif row["illust_prompt"]:
                illustration_image = ai.generate(row["illust_prompt"], transparent=True)

            text_fields = {
                "title_text": row.get("title_text", ""),
                "sub_text": row.get("sub_text", ""),
            }

            final_image = compose(
                template,
                product_image_path=row["product_image_path"],
                background_image=background_image,
                illustration_image=illustration_image,
                text_fields=text_fields,
                font_dir=font_dir,
            )
            save_output(final_image, output_path)

            append_log(row_id, "success", output_path)
            ok_count += 1

        except (AIGeneratorError, FileNotFoundError, ValueError) as e:
            logger.error(f"[error] {row_id}: {e}")
            append_log(row_id, "error", str(e))
            err_count += 1
        except Exception as e:  # noqa: BLE001
            logger.error(f"[error] {row_id}: 予期しないエラー: {e}")
            append_log(row_id, "error", f"unexpected: {e}")
            err_count += 1

    logger.info(f"完了: 成功 {ok_count}件 / 失敗 {err_count}件")
    if err_count:
        logger.info(f"失敗した行は --only-failed で再実行できます（ログ: {LOG_CSV}）")
    return 0 if err_count == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
