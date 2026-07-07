# cockpit-gc

AGI Cockpit のタスク履歴が増えすぎたときに、状態を読み取り、整理候補を分類し、人間が確認しながら片付けるための小さな Python CLI + Codex skill です。

`cockpit-gc` は削除ツールではありません。まず `scan` と `plan` で現状を把握し、必要な場合だけ `--apply` 付きの明示的なフローで選択済みタスクを完了します。

## できること

- `waiting_confirmation` や `needsResume` の件数を集計する
- 古い待機タスク、完了済みタスク、一時 workspace 由来のタスクを分類する
- 完了候補をチェックリスト形式で確認する
- Codex skill として Cockpit backlog の診断手順を呼び出す

## 前提

- macOS
- AGI Cockpit がインストール済み
- `cockpit` CLI が `PATH` から使える
- Python 3.10+
- Cockpit アプリが起動中

Python の外部依存パッケージはありません。

## インストール

```bash
git clone <repo-url>
cd cockpit-gc
```

まずは読み取り専用の scan を実行します。

```bash
PYTHONPATH=src python3 -m cockpit_gc scan
```

Codex skill として使う場合は、skill をローカルにコピーします。

```bash
mkdir -p ~/.codex/skills/cockpit-gc
rsync -a skills/cockpit-gc/ ~/.codex/skills/cockpit-gc/
```

その後、新しい Codex セッションで次のように呼び出します。

```text
$cockpit-gc Cockpit の backlog を確認してください
```

## よく使うコマンド

```bash
PYTHONPATH=src python3 -m cockpit_gc scan
PYTHONPATH=src python3 -m cockpit_gc plan
PYTHONPATH=src python3 -m cockpit_gc review-complete
PYTHONPATH=src python3 -m cockpit_gc review-waiting
```

レポートを `reports/` に保存する場合:

```bash
PYTHONPATH=src python3 -m cockpit_gc scan --write
PYTHONPATH=src python3 -m cockpit_gc plan --write
```

## 安全な整理フロー

最初は必ず読み取り専用で確認します。

```bash
PYTHONPATH=src python3 -m cockpit_gc scan
PYTHONPATH=src python3 -m cockpit_gc plan
```

古い `waiting_confirmation` をチェックリストで確認するだけなら:

```bash
PYTHONPATH=src python3 -m cockpit_gc review-waiting --stale-days 7 --with-snippet --ask
```

選択したタスクを本当に完了する場合だけ `--apply` を付けます。

```bash
PYTHONPATH=src python3 -m cockpit_gc review-waiting --include-needs-resume --ask --apply
```

このコマンドは Cockpit のチェックボックスで選択した task ID だけを `complete` します。

## 安全設計

- デフォルトは読み取り専用です
- Cockpit が起動中か確認してから `cockpit` CLI を呼びます
- `--apply` なしではタスク状態を変更しません
- `cockpit-gc apply` は意図的に未実装です
- orphan process を検出することはありますが、kill はしません
- `remove` は基本的に推奨せず、まず `complete` を優先します

## テスト

```bash
python3 -m unittest discover -s tests
```

## ステータス

これは AGI Cockpit を長く使う中で生まれたローカル運用ツールのコードサンプルです。まだ alpha 品質として扱い、最初は `scan` と `plan` だけで様子を見ることをおすすめします。
