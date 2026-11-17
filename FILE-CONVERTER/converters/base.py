"""変換機の共通の型（converters/base.py）。

core はこのファイルで決めた型だけを知っていればよく、個々の変換の
中身（入力が PDF かどうか、どのライブラリを使うか）は知らない。
新しい変換機は、この Converter を継承して作る。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


# progress_callback(current, total): 変換の進捗を core へ通知する。
ProgressCallback = Callable[[int, int], None]


class EmptyPdfError(ValueError):
    """ページ数 0 の PDF を選んだときの専用例外。

    ValueError のサブクラスなので、従来の `except ValueError` でも
    拾える。core はメッセージ文字列ではなくこの型で判定するため、
    メッセージ文言を将来変えても判定が壊れない。
    """

    pass


@dataclass(frozen=True)
class Option:
    """1つのオプションの仕様。

    GUI はこの一覧を読んでウィジェットを動的に作る。オプションを
    追加するときは、変換機の options() に Option を1行足すだけで、
    core の画面は触らない。

    kind:
        "choice" ... 選択肢から選ぶ（OptionMenu）
        "scale"  ... 数値をスライダで選ぶ（Scale）
        "int"    ... 数値を入力する（Entry）
    enabled_when:
        他のオプションの値によって有効/無効を切り替える条件。
        例: {"format": "JPEG"} なら、format が JPEG のときだけ有効。
        値がリストの場合は、そのいずれかと一致すれば有効。
    suffix:
        ウィジェットの横に表示する単位などの文字列（例: "DPI"）。
    """

    name: str
    label: str
    kind: str  # "choice" | "scale" | "int"
    default: Any
    choices: tuple[str, ...] = ()
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    enabled_when: Optional[dict[str, Any]] = None
    suffix: str = ""

    def is_enabled(self, options: dict[str, Any]) -> bool:
        """現在のオプション値のもとで、このオプションが有効かどうか。"""
        if not self.enabled_when:
            return True
        for key, expected in self.enabled_when.items():
            actual = options.get(key)
            if isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True


class Converter(ABC):
    """すべての変換機が守る共通の型。

    core はこの型だけを使って変換機を扱う。変換機は、自分の
    入力形式・出力形式・オプションを宣言し、実際の変換処理を持つ。
    """

    # 変換機の識別子（registry への登録キー）。
    id: str = ""
    # GUI の変換機選択欄に表示する名前。
    display_name: str = ""
    # 入力ファイル選択欄のラベル（例: "SELECT PDF FILE"）。
    input_label: str = "SELECT INPUT FILE"
    # 受け付ける入力ファイルの拡張子（例: (".pdf",)）。
    input_extensions: tuple[str, ...] = ()
    # ファイル選択ダイアログの filetypes（例: (("PDF files", "*.pdf"),)）。
    input_filetypes: tuple[tuple[str, str], ...] = (("All files", "*.*"),)
    # オプション欄の枠のタイトル（例: "Image Settings"）。
    options_title: str = "Settings"
    # 進捗・完了メッセージで使う変換単位の名前（例: "pages"）。
    unit_name: str = "items"

    @classmethod
    @abstractmethod
    def options(cls) -> list[Option]:
        """この変換機が持つオプションの一覧を返す。"""
        raise NotImplementedError

    @classmethod
    def default_options(cls) -> dict[str, Any]:
        """オプションの初期値だけの辞書を返す。"""
        return {opt.name: opt.default for opt in cls.options()}

    @classmethod
    def validate_options(cls, options: dict[str, Any]) -> dict[str, Any]:
        """オプションを正規化し、不正なら ValueError を返す。

        戻り値は、初期値で補完され、型が整えられたオプション辞書。
        変換機ごとに固有のメッセージが必要な場合は、
        このメソッドをオーバーライドしてから super() を呼ぶこと。
        """
        validated: dict[str, Any] = cls.default_options()
        validated.update(options or {})
        for opt in cls.options():
            value = validated.get(opt.name)
            if opt.kind == "choice":
                if str(value) not in opt.choices:
                    raise ValueError(
                        f"Invalid value for {opt.label}: {value!r}"
                    )
                validated[opt.name] = str(value)
            elif opt.kind in ("scale", "int"):
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Please enter a valid integer for {opt.label}."
                    ) from None
                if opt.min_value is not None and number < opt.min_value:
                    raise ValueError(
                        f"Please enter a value of {opt.min_value} or more "
                        f"for {opt.label}."
                    )
                if opt.max_value is not None and number > opt.max_value:
                    raise ValueError(
                        f"Please enter a value of {opt.max_value} or less "
                        f"for {opt.label}."
                    )
                validated[opt.name] = number
            else:  # pragma: no cover - 未知の kind は設計ミス
                raise ValueError(f"Unknown option kind: {opt.kind!r}")
        return validated

    @abstractmethod
    def expected_outputs(
        self,
        source: Path,
        destination: Path,
        prefix: str,
        options: dict[str, Any],
    ) -> list[Path]:
        """変換で作られる予定の出力ファイルの一覧を返す。

        core はこれを上書き確認と総数表示に使う。変換前に分かる
        不正（ページ数 0 など）があれば、ここで ValueError を返す。
        ページ数 0 の場合は、その専用例外である EmptyPdfError
        （ValueError のサブクラス）を返すこと。
        出力先フォルダの作成はここでは行わない（core が行う）。
        """
        raise NotImplementedError

    @abstractmethod
    def convert(
        self,
        source: Path,
        destination: Path,
        prefix: str,
        options: dict[str, Any],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> int:
        """実際に変換を行う。変換した単位の数（ページ数など）を返す。

        進捗は、1単位終わるごとに progress_callback(current, total)
        を呼んで core へ通知する。destination は作成済みでなくてよい。
        """
        raise NotImplementedError
