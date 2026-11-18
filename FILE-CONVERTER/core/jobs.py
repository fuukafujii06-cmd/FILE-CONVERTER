"""変換ジョブの実行（core/jobs.py）。

GUI を使わない、変換の準備と実行だけの部分。tkinter に依存しないので、
GUI なしのテストからも呼べる。変換の中身は知らず、Converter の型
（expected_outputs / convert）だけを使う。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from converters.base import Converter, ProgressCallback

# ファイル名に使えない文字（元の converter-main.py と同じ）。
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def validate_prefix(prefix: str) -> str:
    """出力ファイル名の前半分を検証し、前後の空白を除いたものを返す。

    空、または使えない文字を含む場合は ValueError。
    メッセージは元の GUI と同じものを使う。
    """
    cleaned = (prefix or "").strip()
    if not cleaned:
        raise ValueError("Please enter a valid file name.")
    if _INVALID_FILENAME_CHARS.search(cleaned):
        raise ValueError("File name contains invalid characters.")
    return cleaned


def build_destination(output_dir: str | Path, source: str | Path) -> Path:
    """保存先フォルダを決める。元の動作：出力先 / 入力ファイルの stem。"""
    return Path(output_dir) / Path(source).stem


def find_existing(paths: list[Path]) -> list[Path]:
    """すでに存在する出力ファイルだけを返す（上書き確認用）。"""
    return [path for path in paths if path.exists()]


def prepare_conversion_for_sources(
    converter: Converter,
    sources: list[str | Path],
    output_dir: str | Path,
    prefix: str,
    options: dict[str, Any],
) -> tuple[Path, list[Path]]:
    """複数入力版の prepare_conversion()。

    保存先は、既存の build_destination の流儀を保つ
    （output_dir / 最初の入力ファイルの stem）。出力は
    変換機が返す一覧（Images to PDF なら PDF 1ファイル）。
    不正があれば ValueError を返す。
    """
    cleaned_prefix = validate_prefix(prefix)
    validated_options = converter.validate_options(options)
    source_paths = [Path(s) for s in sources]
    if not source_paths:
        raise ValueError("No input files selected.")
    destination = build_destination(output_dir, source_paths[0])
    expected = converter.expected_outputs_for_sources(
        source_paths, destination, cleaned_prefix, validated_options
    )
    destination.mkdir(parents=True, exist_ok=True)
    return destination, expected


def run_conversion_for_sources(
    converter: Converter,
    sources: list[str | Path],
    destination: str | Path,
    prefix: str,
    options: dict[str, Any],
    progress_callback: Optional[ProgressCallback] = None,
) -> int:
    """複数入力版の run_conversion()。変換した単位の数を返す。"""
    return converter.convert_sources(
        sources=[Path(s) for s in sources],
        destination=Path(destination),
        prefix=prefix,
        options=options,
        progress_callback=progress_callback,
    )


def prepare_conversion(
    converter: Converter,
    source: str | Path,
    output_dir: str | Path,
    prefix: str,
    options: dict[str, Any],
) -> tuple[Path, list[Path]]:
    """変換の準備をする。

    1. ファイル名を検証する
    2. オプションを検証・正規化する
    3. 保存先フォルダを作る
    4. 変換機に、作られる予定の出力ファイル一覧を聞く

    戻り値は (保存先フォルダ, 出力ファイルの一覧)。
    不正があれば ValueError を返す。ページ数 0 の場合は、その専用
    例外である EmptyPdfError（ValueError のサブクラス）が返る。
    単一入力のラッパー。中身は prepare_conversion_for_sources。
    """
    return prepare_conversion_for_sources(
        converter, [source], output_dir, prefix, options
    )


def run_conversion(
    converter: Converter,
    source: str | Path,
    destination: str | Path,
    prefix: str,
    options: dict[str, Any],
    progress_callback: Optional[ProgressCallback] = None,
) -> int:
    """変換機に変換を実行させ、変換した単位の数を返す。

    単一入力のラッパー。中身は run_conversion_for_sources。
    """
    return run_conversion_for_sources(
        converter,
        [source],
        destination,
        prefix,
        options,
        progress_callback=progress_callback,
    )
