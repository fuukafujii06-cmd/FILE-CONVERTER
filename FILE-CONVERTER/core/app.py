"""GUI（core/app.py）。

不変の部分：画面の枠、ファイル選択、保存先、進捗表示、スレッド処理、
バリデーション、エラー表示、変換ジョブの実行。
変換の中身は知らない。変換機の種類やオプションは、converters の
registry と各変換機の options() 宣言から動的に取得する。

このモジュールを import しても画面は開かない（Tk() は main() で作る）。
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Optional

from converters.base import Converter, EmptyPdfError, Option
from converters.registry import (
    default_converter_id,
    get_converter,
    list_converters,
)
from core import jobs


def default_output_dir() -> str:
    """出力先フォルダの初期値。

    ホームディレクトリを基準に `Pictures/After-Conversion` を作る。
    pathlib を使うため Windows / Mac / Linux で動く。Pictures
    フォルダがまだなくても、変換の準備時に mkdir(parents=True)
    で作られる。
    """
    return str(Path.home() / "Pictures" / "After-Conversion")


class ConverterApp(tk.Tk):
    """FILE-CONVERTER のメインウィンドウ。"""

    def __init__(self) -> None:
        super().__init__()
        self.title("CONVERTER")
        # 変換機の選択欄が1行増えた分だけ、元の 580x620 から高くした。
        self.geometry("580x660")
        self.resizable(False, False)

        # --- 変換機の選択 ---
        self._converters = list_converters()
        self._converter_by_display = {
            cls.display_name: cls for cls in self._converters
        }
        default_cls = get_converter(default_converter_id())
        self.converter_name = tk.StringVar(value=default_cls.display_name)

        # --- 入出力 ---
        self.input_path = tk.StringVar()
        # 複数入力の変換機で選んだファイル一覧。単一入力のときは
        # 0件か1件。表示用の input_path とは別に持つ。
        self.input_paths: list[Path] = []
        self.output_path = tk.StringVar(value=default_output_dir())
        self.filename = tk.StringVar()

        # --- 動的オプション ---
        # name -> tk.Variable / widget
        self.option_vars: dict[str, tk.Variable] = {}
        self.option_widgets: dict[str, tk.Widget] = {}
        self._option_specs: list[Option] = []

        # --- 動作状況 ---
        self.busy = False
        self.current_destination = ""

        self._build_static_widgets()
        self._rebuild_options()

    # -- 変換機 ---------------------------------------------------------
    @property
    def converter(self) -> Converter:
        """現在選ばれている変換機のインスタンス。"""
        cls = self._converter_by_display[self.converter_name.get()]
        return cls()

    def _on_converter_changed(self, *args: Any) -> None:
        """変換機が切り替わったら、入力欄とオプション欄を作り直す。"""
        converter = self.converter
        self.input_label_var.set(converter.input_label)
        # 単一→複数・複数→単一の切り替えで古い入力が残らないように、
        # 入力欄とファイル名をクリアする。
        self.input_paths = []
        self.input_path.set("")
        self.filename.set("")
        # LabelFrame に textvariable は使えないため、text を直接変える。
        self.settings.configure(text=converter.options_title)
        self._rebuild_options()

    # -- 画面の構築（静的な部分） ---------------------------------------
    def _build_static_widgets(self) -> None:
        title_label = tk.Label(
            self, text="CONVERTER", font=("Meiryo", 17, "bold")
        )
        title_label.pack(pady=18)

        # 変換機の選択（core が registry から動的に作る）
        converter_row = tk.Frame(self)
        converter_row.pack(fill="x", padx=30, pady=5)
        tk.Label(converter_row, text="CONVERTER:", width=15, anchor="w").pack(
            side="left"
        )
        tk.OptionMenu(
            converter_row,
            self.converter_name,
            *[cls.display_name for cls in self._converters],
        ).pack(side="left")
        self.converter_name.trace_add("write", self._on_converter_changed)

        # 入力ファイル選択
        self.input_label_var = tk.StringVar(
            value=self.converter.input_label
        )
        tk.Label(self, textvariable=self.input_label_var).pack(
            anchor="w", padx=30
        )
        frame1 = tk.Frame(self)
        frame1.pack(fill="x", padx=30, pady=5)
        tk.Entry(frame1, textvariable=self.input_path).pack(
            side="left", fill="x", expand=True
        )
        tk.Button(frame1, text="Reference", command=self.select_input).pack(
            side="right"
        )

        # 出力先選択
        tk.Label(self, text="SELECT OUTPUT DIRECTORY").pack(
            anchor="w", padx=30
        )
        frame2 = tk.Frame(self)
        frame2.pack(fill="x", padx=30, pady=5)
        tk.Entry(frame2, textvariable=self.output_path).pack(
            side="left", fill="x", expand=True
        )
        tk.Button(frame2, text="Reference", command=self.select_output).pack(
            side="right"
        )

        # ファイル名
        tk.Label(self, text="OUTPUT FILE NAME").pack(anchor="w", padx=30)
        tk.Entry(self, textvariable=self.filename).pack(
            fill="x", padx=30, pady=5
        )

        # 画像設定（中身は変換機のオプション宣言から動的に作る。
        # 枠のタイトルは変換機の options_title。LabelFrame に
        # textvariable は使えないので、切替時は configure で変える。）
        self.settings = tk.LabelFrame(
            self, text=self.converter.options_title, padx=15, pady=12
        )
        self.settings.pack(fill="x", padx=30, pady=5)

        # 進捗表示
        self.progress_label = tk.Label(
            self, text="Conversion ready.", font=("Meiryo", 10)
        )
        self.progress_label.pack(pady=(12, 5))
        self.progress_bar = ttk.Progressbar(
            self, orient="horizontal", length=500,
            mode="determinate", maximum=100,
        )
        self.progress_bar.pack(pady=5)

        # 変換ボタン
        self.convert_button = tk.Button(
            self,
            text="CONVERT",
            font=("Meiryo", 12, "bold"),
            width=20,
            height=2,
            command=self.start_conversion,
        )
        self.convert_button.pack(pady=15)

    # -- 動的オプション欄 ----------------------------------------------
    def _rebuild_options(self) -> None:
        """変換機の options() 宣言から、設定欄のウィジェットを作り直す。"""
        for child in self.settings.winfo_children():
            child.destroy()
        self.option_vars = {}
        self.option_widgets = {}
        converter = self.converter
        self._option_specs = converter.options()

        for spec in self._option_specs:
            row = tk.Frame(self.settings)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=spec.label, width=15, anchor="w").pack(
                side="left"
            )
            widget = self._build_option_widget(row, spec)
            widget.pack(side="left")
            if spec.suffix:
                tk.Label(row, text=spec.suffix).pack(side="left", padx=5)

        self.refresh_option_states()

    def _build_option_widget(self, parent: tk.Widget, spec: Option) -> tk.Widget:
        """Option 1件分のウィジェットを作り、変数を登録して返す。"""
        if spec.kind == "choice":
            var = tk.StringVar(value=str(spec.default))
            widget = tk.OptionMenu(parent, var, *spec.choices)
        elif spec.kind == "scale":
            var = tk.IntVar(value=int(spec.default))
            widget = tk.Scale(
                parent,
                variable=var,
                from_=spec.min_value if spec.min_value is not None else 0,
                to=spec.max_value if spec.max_value is not None else 100,
                orient="horizontal",
                length=220,
            )
        elif spec.kind == "int":
            var = tk.StringVar(value=str(spec.default))
            widget = tk.Entry(parent, textvariable=var)
        else:  # pragma: no cover - base.validate_options でも弾かれる
            raise ValueError(f"Unknown option kind: {spec.kind!r}")

        self.option_vars[spec.name] = var
        self.option_widgets[spec.name] = widget
        # 他のオプションに依存する表示切替のため、すべての変数を監視する。
        var.trace_add("write", lambda *args: self.refresh_option_states())
        return widget

    def get_options(self) -> dict[str, Any]:
        """画面の現在のオプション値を、名前 -> 値の辞書で返す。"""
        values: dict[str, Any] = {}
        for spec in self._option_specs:
            var = self.option_vars[spec.name]
            values[spec.name] = var.get()
        return values

    def refresh_option_states(self) -> None:
        """enabled_when の条件に従い、各オプションの有効/無効を切り替える。"""
        try:
            current = self.get_options()
        except tk.TclError:
            return
        for spec in self._option_specs:
            widget = self.option_widgets.get(spec.name)
            if widget is None:
                continue
            state = "normal" if spec.is_enabled(current) else "disabled"
            widget.configure(state=state)

    # -- ファイル選択 ----------------------------------------------------
    def select_input(self) -> None:
        converter = self.converter
        if converter.accepts_multiple_inputs:
            paths = filedialog.askopenfilenames(
                title=converter.input_label,
                filetypes=list(converter.input_filetypes),
            )
            if paths:
                self.input_paths = [Path(p) for p in paths]
                if len(paths) == 1:
                    self.input_path.set(paths[0])
                else:
                    # 最初のファイル + 残りの枚数が分かる表示にする。
                    self.input_path.set(
                        f"{paths[0]} (+{len(paths) - 1} files)"
                    )
                self.filename.set(Path(paths[0]).stem)
            return
        path = filedialog.askopenfilename(
            title=converter.input_label,
            filetypes=list(converter.input_filetypes),
        )
        if path:
            self.input_paths = [Path(path)]
            self.input_path.set(path)
            self.filename.set(Path(path).stem)

    def select_output(self) -> None:
        path = filedialog.askdirectory(title="SELECT OUTPUT DIRECTORY")
        if path:
            self.output_path.set(path)

    # -- 変換処理 --------------------------------------------------------
    def convert_worker(
        self,
        converter: Converter,
        source: Path,
        destination: Path,
        prefix: str,
        options: dict[str, Any],
    ) -> None:
        """別スレッドで変換を実行し、結果を GUI スレッドへ返す。

        単一入力のラッパー。中身は convert_worker_for_sources。
        """
        self.convert_worker_for_sources(
            converter, [source], destination, prefix, options
        )

    def convert_worker_for_sources(
        self,
        converter: Converter,
        sources: list[Path],
        destination: Path,
        prefix: str,
        options: dict[str, Any],
    ) -> None:
        """別スレッドで変換を実行し、結果を GUI スレッドへ返す。"""
        try:
            total = jobs.run_conversion_for_sources(
                converter,
                sources,
                destination,
                prefix,
                options,
                progress_callback=lambda current, total: self.after(
                    0,
                    self.update_progress,
                    current,
                    total,
                    current / total * 100 if total else 0,
                ),
            )
            self.after(0, self.conversion_complete, total)
        except Exception as e:  # noqa: BLE001 - エラー表示のため全例外を拾う
            self.after(0, self.conversion_error, str(e))

    def update_progress(self, current: int, total: int, progress: float) -> None:
        self.progress_bar["value"] = progress
        unit = self.converter.unit_name
        self.progress_label.config(
            text=f"Converting... {current}/{total} {unit} ({progress:.1f}%)"
        )

    def conversion_complete(self, total: int) -> None:
        self.busy = False
        unit = self.converter.unit_name
        self.progress_bar["value"] = 100
        self.progress_label.config(
            text=f"Conversion completed {total} {unit} converted."
        )
        self.convert_button.config(state="normal")
        messagebox.showinfo(
            "Completed",
            f"{total} {unit} converted successfully.\n\n"
            f"Save location:\n{self.current_destination}",
        )

    def conversion_error(self, error_message: str) -> None:
        self.busy = False
        self.convert_button.config(state="normal")
        self.progress_label.config(text="Conversion failed.")
        messagebox.showerror(
            "Error", f"An error occurred during conversion:\n{error_message}"
        )

    def start_conversion(self) -> None:
        """CONVERT ボタンが押されたときの処理（元の流れを保つ）。"""
        if self.busy:
            return
        converter = self.converter

        # 入力チェック
        if not self.input_path.get():
            messagebox.showwarning("Confirmation", converter.input_label)
            return
        # 保存先チェック
        if not self.output_path.get():
            messagebox.showwarning("Confirmation", "SELECT OUTPUT DIRECTORY")
            return

        # ファイル名チェック（core/jobs が行う）
        try:
            prefix = jobs.validate_prefix(self.filename.get())
        except ValueError as e:
            messagebox.showwarning("Confirmation", str(e))
            return

        # オプションの検証（変換機が決めたルールで行う）
        try:
            options = converter.validate_options(self.get_options())
        except ValueError as e:
            messagebox.showwarning("Confirmation", str(e))
            return

        # 変換の準備（保存先作成・出力一覧の取得）
        # 複数入力の変換機は選んだファイル一覧をそのまま使う。
        # 単一入力の変換機は入力欄の1ファイルを使う。
        if converter.accepts_multiple_inputs:
            sources = list(self.input_paths)
        elif self.input_paths:
            sources = list(self.input_paths)
        else:
            sources = [Path(self.input_path.get())]
        try:
            if converter.accepts_multiple_inputs:
                destination, expected = jobs.prepare_conversion_for_sources(
                    converter,
                    sources,
                    self.output_path.get(),
                    prefix,
                    options,
                )
            else:
                destination, expected = jobs.prepare_conversion(
                    converter,
                    sources[0],
                    self.output_path.get(),
                    prefix,
                    options,
                )
        except EmptyPdfError as e:
            # ページ数 0 は、元と同じく警告だけ出して中断する。
            # 型で判定するため、メッセージ文言を変えても壊れない。
            messagebox.showwarning("Confirmation", str(e))
            return
        except ValueError as e:
            messagebox.showerror(
                "Error",
                f"An error occurred while preparing for conversion:\n{e}",
            )
            return
        except Exception as e:  # noqa: BLE001 - 準備中の想定外エラーも表示する
            messagebox.showerror(
                "Error",
                f"An error occurred while preparing for conversion:\n{e}",
            )
            return

        self.current_destination = str(destination)
        # 進捗の総数：複数入力なら選んだ枚数、単一入力なら出力ファイル数。
        total = len(sources) if converter.accepts_multiple_inputs else len(expected)
        unit = converter.unit_name

        # 上書き確認
        if jobs.find_existing(expected):
            answer = messagebox.askyesno(
                "Confirmation",
                "Some output files already exist. Do you want to overwrite them?",
            )
            if not answer:
                return

        # 変換開始（スレッドで実行）
        self.busy = True
        self.convert_button.config(state="disabled")
        self.progress_bar["value"] = 0
        self.progress_label.config(
            text=f"Starting conversion...:0/{total} {unit}"
        )
        thread = threading.Thread(
            target=self.convert_worker_for_sources,
            args=(converter, sources, destination, prefix, options),
            daemon=True,
        )
        thread.start()


def main() -> None:
    """アプリを起動する。"""
    app = ConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
