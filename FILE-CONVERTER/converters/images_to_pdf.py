"""複数の画像を1つの PDF にまとめる変換機。

画像1枚 -> PDF 1ページの試作（FILE-CONVERTER-next-feature の
ImageToPdfConverter）と、仕様・オプションは同じ。
違いは、入力が複数ファイルで、各画像が PDF 1ページになること。
順番は、ファイル選択ダイアログで選んだ順のまま。
1枚だけ選んだ場合は PDF 1ページになる。

Pillow だけで動き、新しい依存ライブラリはいらない。
透明 PNG は RGB に変換して白背景にのせる。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PIL import Image

from converters.base import Converter, Option, ProgressCallback

# 用紙サイズ（ポイント、1pt = 1/72 inch）。A4 = 595x842pt。
PAGE_SIZES: dict[str, tuple[float, float]] = {
    "A4": (595.27, 841.89),
    "A5": (419.53, 595.27),
    "Letter": (612.0, 792.0),
}


class ImagesToPdfConverter(Converter):
    """画像を複数枚まとめて1つの PDF に変換する。"""

    id = "images_to_pdf"
    display_name = "Images to PDF"
    input_label = "SELECT IMAGE FILES"
    input_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
    input_filetypes = (
        ("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"),
        ("PNG files", "*.png"),
        ("JPEG files", "*.jpg *.jpeg"),
        ("All files", "*.*"),
    )
    options_title = "PDF Settings"
    unit_name = "pages"
    accepts_multiple_inputs = True

    @classmethod
    def options(cls) -> list[Option]:
        return [
            Option(
                name="page_size",
                label="PAGE SIZE:",
                kind="choice",
                default="A4",
                choices=("A4", "A5", "Letter"),
            ),
            Option(
                name="margin",
                label="MARGIN:",
                kind="int",
                default=10,
                min_value=0,
                max_value=50,
                suffix="mm",
            ),
            Option(
                name="fit",
                label="FIT:",
                kind="choice",
                default="fit",
                choices=("fit", "fill"),
            ),
        ]

    def _validate_sources(
        self, sources: list[Path], options: dict[str, Any]
    ) -> dict[str, Any]:
        """オプションと入力ファイル一覧を検証する。

        出力フォルダを作る前に弾くこと。存在しない入力・対応外の
        拡張子・空のリスト・不正な PAGE SIZE は ValueError。
        """
        validated = self.validate_options(options)
        if not sources:
            raise ValueError("No input files selected.")
        for source in sources:
            source = Path(source)
            if not source.is_file():
                raise ValueError(f"Input file not found: {source}")
            if source.suffix.lower() not in self.input_extensions:
                raise ValueError(
                    f"Unsupported image format: {source.suffix}"
                )
        return validated

    def _make_page(
        self,
        img: Image.Image,
        page_w: float,
        page_h: float,
        margin_pt: float,
        fit: str,
    ) -> Image.Image:
        """画像1枚を、白背景の用紙サイズのページ画像にする。"""
        # 描画領域（余白を除いた用紙内側）
        area_w = max(1.0, page_w - 2 * margin_pt)
        area_h = max(1.0, page_h - 2 * margin_pt)
        if fit == "fill":
            scale = max(area_w / img.width, area_h / img.height)
        else:
            scale = min(area_w / img.width, area_h / img.height)
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        # 白背景の用紙サイズ画像に中央配置する。
        # Pillow の PDF 保存は用紙サイズを px 扱いするため、
        # 72dpi で保存すると 1px = 1pt になり、用紙サイズ通りになる。
        page = Image.new("RGB", (int(page_w), int(page_h)), "white")
        offset_x = int((page_w - new_w) / 2)
        offset_y = int((page_h - new_h) / 2)
        page.paste(resized, (offset_x, offset_y))
        return page

    def expected_outputs(
        self,
        source: Path,
        destination: Path,
        prefix: str,
        options: dict[str, Any],
    ) -> list[Path]:
        # 単一版は複数版に委譲する。1枚でも同じ結果になる。
        return self.expected_outputs_for_sources(
            [Path(source)], destination, prefix, options
        )

    def expected_outputs_for_sources(
        self,
        sources: list[Path],
        destination: Path,
        prefix: str,
        options: dict[str, Any],
    ) -> list[Path]:
        self._validate_sources(list(sources), options)
        return [Path(destination) / f"{prefix}.pdf"]

    def convert(
        self,
        source: Path,
        destination: Path,
        prefix: str,
        options: dict[str, Any],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> int:
        # 単一版は複数版に委譲する。1枚でも同じ結果になる。
        return self.convert_sources(
            [Path(source)],
            destination,
            prefix,
            options,
            progress_callback=progress_callback,
        )

    def convert_sources(
        self,
        sources: list[Path],
        destination: Path,
        prefix: str,
        options: dict[str, Any],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> int:
        options = self._validate_sources(list(sources), options)
        sources = [Path(s) for s in sources]
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)

        page_w, page_h = PAGE_SIZES[str(options["page_size"])]
        # mm -> pt (1 inch = 25.4mm = 72pt)
        margin_pt = float(options["margin"]) * 72.0 / 25.4
        fit = str(options["fit"])
        total = len(sources)

        pages: list[Image.Image] = []
        for i, source in enumerate(sources):
            with Image.open(source) as img:
                # 透明 PNG は RGB にして白背景にのせる。
                pages.append(
                    self._make_page(
                        img.convert("RGB"),
                        page_w,
                        page_h,
                        margin_pt,
                        fit,
                    )
                )
            if progress_callback:
                progress_callback(i + 1, total)

        out = destination / f"{prefix}.pdf"
        # 1枚目は save、2枚目以降は append_images で1つの PDF にまとめる。
        pages[0].save(
            out,
            format="PDF",
            resolution=72.0,
            save_all=True,
            append_images=pages[1:],
        )
        return total
