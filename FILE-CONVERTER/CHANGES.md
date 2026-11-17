# FILE-CONVERTER リファクタリング記録

目的：機能の拡張性を上げるため、**不変の core** と **変換機・オプション** に分離する。
合意した設計どおりに分け直した。GitHub への push はしていない。
作業元：`https://github.com/fuukafujii06-cmd/FILE-CONVERTER`（main ブランチ、2026-11-17 時点）

## 2026-11-18 の小さな改善（EmptyPdfError とホーム基準の出力先）

藤井の提案で、0ページエラーの判定を文字列比較から型による判定に変え、
出力先の初期値をホームディレクトリ基準で動的に生成するようにした。
GitHub への push はしていない。

### 改善1：0ページエラーを型で判定する（EmptyPdfError）

- `converters/base.py`（約14行目付近）に専用例外を追加した。
  ```python
  class EmptyPdfError(ValueError):
      """ページ数 0 の PDF を選んだときの専用例外。"""
      pass
  ```
  `ValueError` のサブクラスなので、従来の `except ValueError` でも拾える。
  `Converter.expected_outputs()` の docstring にも「ページ数 0 の場合は
  EmptyPdfError を返すこと」と追記した。
- `converters/pdf_to_image.py` の `expected_outputs()`（約108行目）で、
  `raise ValueError("The selected PDF file has no pages.")` を
  `raise EmptyPdfError("The selected PDF file has no pages.")` に変えた。
  メッセージ文言自体は変えていない。
- `converters/pdf_to_image.py` の `convert()`（約148行目）にも同じ
  チェックを追加した。`expected_outputs()` 経由では先に弾かれるのが
  通常だが、`convert()` や旧ラッパー `PDFconversion()` を直接呼んだ
  場合も、型で判定できるようにするため。
- `core/app.py` の `start_conversion()`（約352行目付近）で、文字列比較
  `if str(e) == "The selected PDF file has no pages.":` を削除し、
  次のように型で受ける順序に変えた（サブクラスを先に書くのが要点）。
  ```python
  except EmptyPdfError as e:
      messagebox.showwarning("Confirmation", str(e))
      return
  except ValueError as e:
      messagebox.showerror(
          "Error",
          f"An error occurred while preparing for conversion:\n{e}",
      )
      return
  ```
  これで、将来メッセージ文言を変えても判定が壊れない。
  他の変換機でも、ページ数 0 のような「警告で中断する」場合は
  同じ EmptyPdfError を使い回せる。
- `core/jobs.py` の `prepare_conversion()` の docstring に、ページ数 0 の
  場合は EmptyPdfError（ValueError のサブクラス）が返ることを追記した。
- 旧ラッパー `PDFconversion()` の動きは保った。0ページ PDF では
  EmptyPdfError が投げられ、従来の `except ValueError` でも拾える。

### 改善2：出力先の初期値をホームディレクトリ基準で動的に生成する

- `core/app.py`（約28行目付近）に `default_output_dir()` を追加し、
  `__init__` の出力先初期値をそこから取るようにした。
  ```python
  def default_output_dir() -> str:
      return str(Path.home() / "Pictures" / "After-Conversion")
  ```
  `pathlib` を使うため Windows / Mac / Linux で動く。Windows では
  `C:\Users\<ユーザー名>\Pictures\After-Conversion`、Mac / Linux では
  `~/Pictures/After-Conversion` になる。
- 以前の初期値 `r"C:\Pictures\After-Conversion"` は削除した。コード内の
  他のハードコードされた `C:\` パスを grep で確認したところ、コード
  （`*.py`）には他になかった（`CHANGES.md` の旧記録の記述のみ）。
- Pictures フォルダがまだなくても問題ない。変換の準備時に
  `mkdir(parents=True)` で保存先が作られる流れは変えていない。
  ユーザーが出力先を選び直せば、初期値は上書きされる。

### 今回の変更で変わった点・変わらない点

- 変わった点：
  - 出力先の初期値が `C:\Pictures\After-Conversion` 固定から、
    ホーム基準の `Pictures/After-Conversion` になった（下の「以前の
    記録」の「変わらない点」にあった出力先の初期値の記述は、この改善で
    変わった。Windows では `C:\Users\<ユーザー名>\Pictures\...` になる）。
  - 0ページ PDF の判定が、メッセージ文字列の完全一致から
    EmptyPdfError の型による判定になった。画面の挙動（警告だけ出して
    中断）は変わらない。
- 変わらない点：
  - PDF→PNG/JPEG の変換結果、出力名 `prefix_001.png` / `.jpg`、
    DPI・形式・色・品質のオプションと初期値、上書き確認、進捗表示、
    完了・失敗時のメッセージの流れ。
  - 0ページ PDF を選んだとき、警告「The selected PDF file has no pages.」
    だけ出して中断する点（文言は同じ）。

### 今回のテスト結果

テスト環境：Python 3.12.3、PyMuPDF、Pillow。GUI のテストは Xvfb 上で実施。
テスト用スクリプトは成果物には含めていない（`/tmp/test_fc2.py`、`/tmp/test_gui2.py`）。

- `python -m py_compile`：全ファイル OK（`converter-main.py`、`core/*`、
  `converters/*`、`FILE-CONVERTER.spec`）。
- 変換のテスト（GUI なし、22件、全て PASS）：
  - 2ページのサンプル PDF（A4）で PDF→PNG（DPI 300・RGB）と
    PDF→JPEG（DPI 600・GRAY・品質 50）を確認。出力2件ずつ、PNGはRGB・
    DPI 約300・幅 2480px、JPEGはGRAY（L）・DPI 600・幅 4959px、
    進捗 `(1, 2)`、`(2, 2)`。
  - 0ページ PDF（生の PDF バイトで作成。PyMuPDF は0ページの保存を
    拒否するため）で、`expected_outputs()`・`convert()`・
    `prepare_conversion()`・旧ラッパー `PDFconversion()` のいずれも
    EmptyPdfError を投げること、EmptyPdfError が ValueError の
    サブクラスであることを確認。
  - メッセージ文言を変えた EmptyPdfError（例：「ページがありません」）
    を `except EmptyPdfError` で拾えること、旧方式の文字列比較では
    その文言は拾えないことを確認。`core/app.py` に文字列比較が
    残っていないことも grep で確認。
  - `default_output_dir()` が `Path.home() / "Pictures" / "After-Conversion"`
    と一致し、絶対パスで、`C:` を含まないことを確認（この環境では
    `/home/hatch/Pictures/After-Conversion`）。
- GUI のテスト（Xvfb 上で実ウィンドウを作成、9件、全て PASS）：
  - ウィンドウが開くこと、出力先の初期値がホーム基準になっていること、
    変換機の初期選択が「PDF to Image」、進捗ラベルの初期表示が
    「Conversion ready.」であること、品質スライダが PNG で無効・
    JPEG で有効・PNG に戻すと再び無効になることを確認。
- 未確認の点：実際の Windows での exe の起動と画面操作は、この環境では
  確認していない。`python converter-main.py` での起動確認を推奨する。
  Windows でのホーム基準パスの実際の値（`C:\Users\<ユーザー名>\Pictures\...`）
  も、Windows 環境での確認がまだ。


## 変えた部分の一覧

### 追加したファイル

| ファイル | 内容 |
|---|---|
| `core/__init__.py` | core パッケージの入口 |
| `core/app.py` | GUI。画面の枠、ファイル選択、変換機の選択、動的オプション欄、進捗表示、スレッド処理、バリデーション、エラー表示 |
| `core/jobs.py` | GUI を使わない変換ジョブの実行。ファイル名の検証、保存先の決定、変換の準備・実行 |
| `converters/__init__.py` | converters パッケージの入口 |
| `converters/base.py` | 変換機の共通の型（`Converter`）とオプションの仕様（`Option`） |
| `converters/registry.py` | 変換機の一覧・登録 |
| `converters/pdf_to_image.py` | PDF→PNG/JPEG の変換機（`PdfToImageConverter`）。元の処理をここに移した |
| `.gitignore` | `build/`、`dist/`、`__pycache__/`、`*.pyc` などを除外 |
| `README.md` | 構成と使い方の説明 |
| `CHANGES.md` | このファイル |

### 変更したファイル

| ファイル | 変更内容 |
|---|---|
| `converter-main.py` | GUI と変換処理が一体だった 8.3KB のファイルから、起動だけの薄い入口にした（`core.app.main()` を呼ぶだけ）。`if __name__ == "__main__"` で守り、import しても mainloop は走らない |
| `FILE-CONVERTER.spec` | 入口は `converter-main.py` のまま変更なし。組み込みの変換機を `hiddenimports` に明示し、更新理由をコメントで記載した（詳細は後述） |

### 削除したファイル

| ファイル | 備考 |
|---|---|
| `converter/PDFconversion.py` | 処理は `converters/pdf_to_image.py` に移した。旧関数 `PDFconversion()` は後方互換のラッパーとして新しい場所に残してある（`from converters.pdf_to_image import PDFconversion`） |
| `converter/__init__.py` | `converter/` パッケージごと削除。`converters/` パッケージに置き換えた |
| `build/`、`dist/FILE-CONVERTER.exe`、`converter/__pycache__/` | ビルド成果物・キャッシュ。成果物には含めない（`.gitignore` で除外）。`converter.ico` は spec が使うため残した |

## 不変の core が何をするか

`core/` は変換の中身（PDF かどうか、どのライブラリを使うか）を知らない。
`converters/base.py` で決めた型だけを使って動く。

- `core/app.py`
  - ウィンドウの枠（タイトル `CONVERTER`、変換機の選択欄、入力・出力・ファイル名の欄、進捗バー、CONVERT ボタン）
  - ファイル選択ダイアログ（表示する形式は変換機の宣言から取得）
  - 変換機の `options()` 宣言を読んで、設定欄のウィジェットを動的に作る
  - `enabled_when` に従い、オプションの有効/無効を切り替える（例：品質は JPEG のときだけ有効）
  - 入力・保存先・ファイル名のチェック、オプションの検証、上書き確認、エラーメッセージの表示
  - 変換を別スレッドで実行し、進捗を GUI スレッドへ返す
- `core/jobs.py`（tkinter に依存しない）
  - ファイル名の検証（空・使えない文字 `< > : " / \ | ? *`）
  - 保存先フォルダの決定（出力先 / 入力ファイルの stem）
  - 変換の準備（保存先の作成、出力ファイル一覧の取得）と実行
  - すでに存在する出力ファイルの検出（上書き確認用）

## 変換機・オプションの追加方法

### 変換機を追加する（例：画像→PDF）

1. `converters/` にファイルを1つ作り、`Converter` を継承する。

```python
# converters/image_to_pdf.py
from converters.base import Converter, Option

class ImageToPdfConverter(Converter):
    id = "image_to_pdf"
    display_name = "Image to PDF"
    input_label = "SELECT IMAGE FILE"
    input_extensions = (".png", ".jpg")
    input_filetypes = (("Image files", "*.png *.jpg"),)
    options_title = "PDF Settings"
    unit_name = "files"

    @classmethod
    def options(cls):
        return [
            Option(name="page_size", label="PAGE SIZE:", kind="choice",
                   default="A4", choices=("A4", "A5", "Letter")),
        ]

    def expected_outputs(self, source, destination, prefix, options):
        return [destination / f"{prefix}.pdf"]

    def convert(self, source, destination, prefix, options,
                progress_callback=None):
        # ここに変換処理を書く。終わったら progress_callback(1, 1) を呼ぶ。
        ...
        return 1
```

2. `converters/registry.py` の `_BUILTIN_CONVERTERS` に1行足す。

```python
_BUILTIN_CONVERTERS = (
    PdfToImageConverter,
    ImageToPdfConverter,  # 追加
)
```

3. これだけ。`core/` の画面は触らない。起動すると変換機の選択欄に「Image to PDF」が増える。

### オプションを追加する（例：PDF→画像に「余白」を足す）

`converters/pdf_to_image.py` の `options()` に `Option` を1行足し、`convert()` で `options["margin"]` を使うだけ。

```python
Option(name="margin", label="MARGIN:", kind="int",
       default=0, min_value=0, max_value=100),
```

画面はこの宣言を読んで入力欄を自動で作る。`core/app.py` の変更はいらない。
種類は `choice`（選択肢）、`scale`（スライダ）、`int`（数値入力）の3つ。
`enabled_when={"format": "JPEG"}` のように、他のオプションの値で有効/無効も切り替えられる。

## 今の動きで変わった点・変わらない点

### 変わらない点

- PDF→PNG/JPEG の変換結果。出力名は `prefix_001.png` / `.jpg` のまま。
- オプションと初期値：DPI 300/600/900/1200（初期値 600）、形式 PNG/JPEG（初期値 PNG）、色 RGB/GRAY（初期値 RGB）、品質 1–100（初期値 100、JPEG のときだけ有効）。
- DPI・色・品質が変換結果に反映されること。ファイル名・DPI のバリデーション、上書き確認、進捗表示（`Converting... 1/2 pages` など）、完了・失敗時のメッセージの流れ。
- 出力先の初期値（2026-11-18 の改善前は `C:\Pictures\After-Conversion`。現在はホーム基準の `Pictures/After-Conversion` に変更）と、保存先が「出力先 / 入力ファイル名のフォルダ」になる点。
- 0ページの PDF を選んだとき、警告「The selected PDF file has no pages.」だけ出して中断する点。

### 変わった点

- ウィンドウの一番上に「CONVERTER:」の変換機選択欄が増えた（今は「PDF to Image」のみ）。その分、ウィンドウの高さを 580x620 から 580x660 にした。
- 設定欄（DPI・形式・色・品質）が、変換機のオプション宣言から動的に作られるようになった。見た目と初期値は元と同じ。
- 内部で使うライブラリの読み込みを `import pymupdf`（フォールバックで `fitz`）に統一した。動作は同じ。
- 直接コードから呼ぶ場合の細かい挙動：形式に `PNG` / `JPEG` 以外を渡すと、元は黙って PNG 扱いになっていたが、今は `ValueError` になる。GUI からは選べる値しか渡らないので、画面からの操作では変わらない。
- `from converter.PDFconversion import PDFconversion` は使えなくなった。代わりに `from converters.pdf_to_image import PDFconversion`（同じ引数で動くラッパー）か、`PdfToImageConverter` を使う。

### FILE-CONVERTER.spec について

入口は `converter-main.py` のままで、`core` / `converters` は静的に import されるため、spec の対象ファイルは変える必要がなかった。
`hiddenimports` に `converters.pdf_to_image` を明示したのは、将来、変換機を動的に読み込むようになった場合にも exe に確実に含まれるようにするため。exe の再ビルドはこの環境では行っていない（`build/`・`dist/` は成果物に含めていない）。

## テスト結果

テスト環境：Python 3.12.3、PyMuPDF、Pillow。GUI のテストは Xvfb 上で実施。
テスト用スクリプトは成果物には含めていない（`/tmp/test_fc.py`、`/tmp/test_gui.py`）。

- `python -m py_compile`：全ファイル OK（`converter-main.py`、`core/*`、`converters/*`、`FILE-CONVERTER.spec`）。
- 変換のテスト（GUI なし、29件、全て PASS）：
  - 2ページのサンプル PDF を作り、PDF→PNG（DPI 300・RGB）と PDF→JPEG（DPI 600・GRAY・品質 50）で変換。出力は `sample_001` / `sample_002` が各2件ずつできた。
  - PNG は RGB、JPEG は GRAY（`L`）になること、画像の DPI が 300 / 600 になること、画像幅が DPI 相当（300dpi で約 833px、600dpi で約 1666px）になることを確認。
  - JPEG の品質 50 のファイルが品質 100 より小さいこと、進捗コールバックが `(1, 2)`、`(2, 2)` と呼ばれることを確認。
  - 旧関数 `PDFconversion()` のラッパーが同じ引数で動くこと、ファイル名のバリデーション（空・使えない文字）、上書き検出（変換前は 0件、変換後は 2件）、0ページ PDF で元のメッセージが出ることを確認。
- 動的オプション生成のテスト（GUI なし・あり）：
  - registry から変換機が取得でき、オプション一覧が `dpi / format / color / quality`、初期値が `600 / PNG / RGB / 100` であること。
  - `quality` が JPEG のときだけ有効になること、DPI=0 で元のメッセージの `ValueError` になること。
  - Xvfb 上でウィンドウを実際に作り、品質スライダが PNG では無効・JPEG では有効になること、入力欄ラベル・設定枠タイトル・進捗ラベルの初期表示が元と同じであることを確認（10件、全て PASS）。
  - `converter-main.py` の import では mainloop が走らないこと、`core.app` の import だけでは画面が開かないことも確認。
- GUI テスト中に見つかった不具合と修正：`tk.LabelFrame` は `textvariable` に対応しておらず、最初はウィンドウ作成時に `TclError` が出た。枠のタイトルは `configure(text=...)` で変えるよう修正し、再テストで PASS を確認した。
- 未確認の点：実際の Windows での exe の起動と画面操作は、この環境では確認していない。`python converter-main.py` での起動確認を推奨する。
