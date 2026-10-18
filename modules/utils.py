"""共通ユーティリティ関数"""
from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path


def setup_logger(log_dir: str = "logs", name: str = "image_layout_tool") -> logging.Logger:
    """コンソール＋ファイルの両方に出すロガーを作る"""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # 二重登録防止

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(Path(log_dir) / "app.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def prompt_hash(prompt: str, model: str, aspect_ratio: str) -> str:
    """プロンプト＋モデル＋アスペクト比からキャッシュキーを作る"""
    key = f"{model}|{aspect_ratio}|{prompt.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
