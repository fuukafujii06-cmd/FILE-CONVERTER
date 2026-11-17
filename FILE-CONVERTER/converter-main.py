"""FILE-CONVERTER の起動入口（薄いラッパー）。

画面や変換の実体は core / converters にある。ここは main() を呼ぶだけ。
PyInstaller の Analysis もこのファイルを指定したまま使える。
"""

from core.app import main

if __name__ == "__main__":
    main()
