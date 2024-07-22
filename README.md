[JP](README.md)/[EN](README.en.md)

# Browser Starter

Browser Starterは、指定されたブラウザで複数のURLを簡単に開くためのPythonスクリプトです。

## 特徴

- 複数のブラウザとURLをサポート
- 高速モードと順序保持モードを選択可能
- パラメータファイルを使用した一括設定

## インストール

Poetry を使用してインストールします：

```bash
poetry install
```

## 使用方法

コマンドライン引数を使用してBrowser Starterを実行します:

```bash
python browser_starter.py [OPTIONS] [URLS]
```

オプション:

- -bn, --browser-name: 使用するブラウザの名前（複数指定可）
- -bp, --browser-path: ブラウザ実行ファイルへのパス（複数指定可）
- -pf, --parameter-file: パラメータファイルへのパス
- -f, --fast: 高速モード（順序保証なし）
- -o, --ordered: 順序保持モード（デフォルト、遅い）
- -l, -bl, --browser-list: 利用可能なブラウザ一覧を表示
- -u, --urls: 開くURL（複数指定可、オプション名省略可）

## 設定

~/.browser_starter/browser_starter.jsonにJSON形式で設定を保存できます。

## パラメータファイル

YAML、JSON、またはTOML形式のパラメータファイルを使用して、複数のブラウザとURLの組み合わせを一度に指定できます。

## ログ

ログは~/.browser_starter/log/browser_starter.logに保存されます。

## 貢献

バグ報告や機能リクエストは、GitHubのIssueトラッカーをご利用ください。
