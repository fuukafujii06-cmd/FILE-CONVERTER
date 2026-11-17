"""PDF を画像（PNG / JPEG）に変換する変換機。

元の converter/PDFconversion.py の処理を、そのままこの変換機に移した
もの。PDFconversion() 関数は後方互換のための薄いラッパーとして残す。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

try:
    import pymupdf
except ImportError:  # pragma: no cover - 古い環境向けのフォールバック
    import fitz as pymupdf

from PIL import Image

from converters.base import Converter, EmptyPdfError, Option, ProgressCallback


class PdfToImageConverter(Converter):
    """PDF の各ページを画像ファイルに変換する。"""

    id = "pdf_to_image"
    display_name = "PDF to Image"
    input_label = "SELECT PDF FILE"
    input_extensions = (".pdf",)
    input_filetypes = (("PDF files", "*.pdf"),)
    options_title = "Image Settings"
    unit_name = "pages"

    @classmethod
    def options(cls) -> list[Option]:
        # オプションを追加するときは、ここに Option を1行足すだけ。
        # GUI はこの一覧を読んでウィジェットを自動で作る。
        return [
            Option(
                name="dpi",
                label="RESOLUTION:",
                kind="choice",
                default="600",
                choices=("300", "600", "900", "1200"),
                suffix="DPI",
            ),
            Option(
                name="format",
                label="FORMAT:",
                kind="choice",
                default="PNG",
                choices=("PNG", "JPEG"),
            ),
            Option(
                name="color",
                label="COLOR:",
                kind="choice",
                default="RGB",
                choices=("RGB", "GRAY"),
            ),
            Option(
                name="quality",
                label="QUALITY:",
                kind="scale",
                default=100,
                min_value=1,
                max_value=100,
                enabled_when={"format": "JPEG"},
            ),
        ]

    @classmethod
    def validate_options(cls, options: dict[str, Any]) -> dict[str, Any]:
        # DPI だけは、元のメッセージを保つために先に検証する。
        raw = dict(options or {})
        dpi_raw = raw.get("dpi", cls.default_options()["dpi"])
        try:
            dpi = int(dpi_raw)
            if dpi <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError(
                "Please enter a valid positive integer for DPI."
            ) from None
        validated = super().validate_options(raw)
        validated["dpi"] = dpi
        # 形式・色は大文字に正規化する（元の動作と同じ扱い）。
        validated["format"] = str(validated["format"]).upper()
        validated["color"] = str(validated["color"]).upper()
        return validated

    def _extension(self, options: dict[str, Any]) -> str:
        return "png" if options["format"] == "PNG" else "jpg"

    def _page_count(self, source: Path) -> int:
        with pymupdf.open(str(source)) as doc:
            return len(doc)

    def expected_outputs(
        self,
        source: Path,
        destination: Path,
        prefix: str,
        options: dict[str, Any],
    ) -> list[Path]:
        options = self.validate_options(options)
        total = self._page_count(Path(source))
        if total == 0:
            raise EmptyPdfError("The selected PDF file has no pages.")
        extension = self._extension(options)
        return [
            Path(destination) / f"{prefix}_{i + 1:03d}.{extension}"
            for i in range(total)
        ]

    def convert(
        self,
        source: Path,
        destination: Path,
        prefix: str,
        options: dict[str, Any],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> int:
        """PDF を PNG または JPEG に変換する。

        source: 読み込むPDF
        destination: 保存先フォルダ
        prefix: 出力ファイル名
        options: validate_options() 済みのオプション辞書
            （dpi: 解像度、format: PNG / JPEG、color: RGB / GRAY、
             quality: JPEG品質）
        progress_callback: 進捗通知用関数
        """
        options = self.validate_options(options)
        source = Path(source)
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)

        dpi = options["dpi"]
        image_format = options["format"]
        color_mode = options["color"]
        quality = options["quality"]

        with pymupdf.open(str(source)) as doc:
            total = len(doc)
            if total == 0:
                # expected_outputs() 経由で先に弾かれるのが通常だが、
                # convert() を直接呼んだ場合も型で判定できるようにする。
                raise EmptyPdfError("The selected PDF file has no pages.")
            for i, page in enumerate(doc):
                # 色空間
                if color_mode == "GRAY":
                    colorspace = pymupdf.csGRAY
                    mode = "L"
                else:
                    colorspace = pymupdf.csRGB
                    mode = "RGB"

                # PDFページを画像化
                pix = page.get_pixmap(
                    dpi=dpi,
                    colorspace=colorspace,
                    alpha=False,
                )
                image = Image.frombytes(
                    mode,
                    (pix.width, pix.height),
                    pix.samples,
                )

                # ファイル名（元の形式： prefix_001.png / .jpg）
                extension = self._extension(options)
                save_file = (
                    destination / f"{prefix}_{i + 1:03d}.{extension}"
                )

                # 保存
                if image_format == "PNG":
                    image.save(
                        save_file,
                        format="PNG",
                        dpi=(dpi, dpi),
                    )
                elif image_format == "JPEG":
                    image.save(
                        save_file,
                        format="JPEG",
                        quality=quality,
                        dpi=(dpi, dpi),
                    )
                else:  # pragma: no cover - validate_options で弾かれる
                    raise ValueError(
                        "Invalid image format. Please choose 'PNG' or 'JPEG'."
                    )

                # 進捗通知
                if progress_callback:
                    progress_callback(i + 1, total)

        return total


def PDFconversion(
    source,
    destination,
    prefix,
    dpi=600,
    image_format="PNG",
    color_mode="RGB",
    quality=100,
    progress_callback=None,
):
    """後方互換のためのラッパー（元の converter/PDFconversion.py と同じ引数）。

    新しいコードは PdfToImageConverter を使うこと。ここは、元の関数を
    呼んでいた場所がそのまま動くように残してある。
    """
    converter = PdfToImageConverter()
    options = {
        "dpi": dpi,
        "format": image_format,
        "color": color_mode,
        "quality": quality,
    }
    return converter.convert(
        source=source,
        destination=destination,
        prefix=prefix,
        options=options,
        progress_callback=progress_callback,
    )
