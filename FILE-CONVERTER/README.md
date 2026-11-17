# FILE-CONVERTER

ファイルを別の形式に変換するアプリ。

## 使い方

```bash
python converter-main.py
```

1. 変換機を選ぶ（今は「PDF to Image」のみ）。
2. 入力ファイルと出力先フォルダ、出力ファイル名を指定する。
   出力先の初期値は、ホームディレクトリの `Pictures/After-Conversion`
   （Windows では `C:\Users\<ユーザー名>\Pictures\After-Conversion`）。
3. オプションを選んで CONVERT を押す。

## 構成

- `converter-main.py` … 起動だけの薄い入口
- `core/` … 不変の部分。画面の枠、ファイル選択、進捗表示、スレッド処理、
  バリデーション、エラー表示、変換ジョブの実行。変換の中身は知らない。
- `converters/` … 変換機。`base.py` で共通の型（名前・入力形式・
  出力形式・オプション一覧・`convert()`）を決め、`registry.py` で一覧を管理する。
  `pdf_to_image.py` は PDF を PNG / JPEG に変換する。
- `FILE-CONVERTER.spec` … PyInstaller 用の設定。入口は `converter-main.py` のまま。

詳しい変更内容と、変換機・オプションの追加方法は `CHANGES.md` を参照。

## exe にする（Windows）

PyInstaller はホスト OS 用のバイナリしか作れないため、Windows の
exe は Windows で作る。Linux では作れない（この環境で作ると
Linux 用の実行ファイルになる）。

### 方法1：GitHub Actions（おすすめ）

1. このリポジトリを GitHub に push する（`.github/workflows/` を含む）。
2. GitHub の Actions タブで「Build Windows exe」を開き、「Run workflow」を押す。
   main への push や `v*` タグでも自動で動く。
3. 完了したら、その実行結果の Artifacts から `FILE-CONVERTER-windows` を
   ダウンロードする。中に `dist/FILE-CONVERTER.exe` が入っている。

### 方法2：手元の Windows で作る

1. Python 3.12 を入れる（`https://www.python.org/`）。
2. `build.bat` をダブルクリックする（中では次のことをしている）。
   ```bat
   pip install pymupdf pillow pyinstaller
   pyinstaller --clean --noconfirm FILE-CONVERTER.spec
   ```
3. `dist\FILE-CONVERTER.exe` ができる。

spec で束ねているもの：入口は `converter-main.py`、アイコンは
`converter.ico`（本物の ICO 形式、16/32/48/256px）、
`hiddenimports` に `converters.pdf_to_image` を明示（`core/` と
`converters/` は静的 import で自動収集される）。
