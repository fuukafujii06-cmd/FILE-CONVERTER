"""変換機の一覧・登録（converters/registry.py）。

新しい変換機を追加するときは、converters/ にファイルを作り、
_BUILTIN_CONVERTERS にクラスを1行足すだけ。core はここ経由でしか
変換機を見ないので、core の画面を触る必要はない。
"""

from __future__ import annotations

from converters.base import Converter
from converters.images_to_pdf import ImagesToPdfConverter
from converters.pdf_to_image import PdfToImageConverter


# 起動時に読み込む変換機の一覧。新しい変換機はここに足す。
_BUILTIN_CONVERTERS: tuple[type[Converter], ...] = (
    PdfToImageConverter,
    ImagesToPdfConverter,
)

_REGISTRY: dict[str, type[Converter]] = {}


def register(converter_cls: type[Converter]) -> type[Converter]:
    """変換機クラスを登録する。デコレータとしても使える。"""
    if not converter_cls.id:
        raise ValueError("Converter must define a non-empty id.")
    _REGISTRY[converter_cls.id] = converter_cls
    return converter_cls


for _converter_cls in _BUILTIN_CONVERTERS:
    register(_converter_cls)


def list_converters() -> list[type[Converter]]:
    """登録済みの変換機クラスを、登録順に返す。"""
    return list(_REGISTRY.values())


def get_converter(converter_id: str) -> type[Converter]:
    """id から変換機クラスを返す。なければ ValueError。"""
    try:
        return _REGISTRY[converter_id]
    except KeyError:
        raise ValueError(f"Unknown converter: {converter_id!r}") from None


def default_converter_id() -> str:
    """起動時に選ばれる変換機の id。"""
    return _BUILTIN_CONVERTERS[0].id
