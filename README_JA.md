# cockpit-gc

AGI Cockpit のタスク履歴が増えすぎたときに、状態を読み取り、整理候補を分類し、人間が確認しながら片付けるための小さな Python CLI + Codex skill です。

`cockpit-gc` は削除ツールではありません。まず `scan` と `plan` で現状を把握します。対話的な整理は `cockpit ask` が非同期で解決されるため、`--ask` でダイアログをスケジュールし、後から届く `cockpit.ask.resolved` イベントを `resolve-ask` に渡す2段階フローです。

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
PYTHONPATH=src python3 -m cockpit_gc review-remove
PYTHONPATH=src python3 -m cockpit_gc resolve-ask ASK_ID --answers-json '...'
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
PYTHONPATH=src python3 -m cockpit_gc review-waiting --stale-days 7 --with-snippet
```

選択ダイアログをスケジュールするフェーズ1は `--ask` で実行します。

```bash
PYTHONPATH=src python3 -m cockpit_gc review-waiting --include-needs-resume --ask
```

コマンドは `askId` を表示し、提示したラベルを
`.cockpit_gc_state/pending_asks/<askId>.json` に保存して即終了します。
このプロセス自身は後から届くイベントを受け取れません。呼び出し元の
エージェントに `cockpit.ask.resolved` が新しいターンとして届いたら、
そのJSON全体（または `answers` 配列）をフェーズ2へ渡します。

```bash
PYTHONPATH=src python3 -m cockpit_gc resolve-ask ask_xxx \
  --answers-json '{"event":"cockpit.ask.resolved","ask_id":"ask_xxx","outcome":"answered","answers":[{"type":"choices","values":["..."]}]}'
```

`resolve-ask` は、その `askId` の状態に保存されたラベルだけを task ID に
変換します。`dismissed` の場合は何も変更しません。状態ファイルは、
dismissed または選択タスクの処理後に削除されます。

`review-complete` は `safe-to-complete` の候補、`review-waiting` は古い
`waiting_confirmation` の候補を扱います。どちらも `--ask` はスケジュール
だけを行い、実際の `complete` は `resolve-ask` が担当します。

`review-remove` は `safe-to-remove` 候補を扱います。`--apply` フラグは
存在せず、`--ask` → 明示的な選択イベント → `resolve-ask` の流れだけで
`remove` を実行します。

## 安全設計

- デフォルトは読み取り専用です
- Cockpit が起動中か確認してから `cockpit` CLI を呼びます
- `review-* --ask` は非同期 ask のスケジュールと状態保存だけを行います
- `resolve-ask` は answered イベントに含まれ、保存済み候補にも一致するラベルだけを処理します
- `cockpit-gc apply` は意図的に未実装です
- orphan process を検出することはありますが、kill はしません
- `remove` は基本的に推奨せず、まず `complete` を優先します。明示的な選択なしには実行しません

## テスト

```bash
python3 -m pytest
```

## ステータス

これは AGI Cockpit を長く使う中で生まれたローカル運用ツールのコードサンプルです。まだ alpha 品質として扱い、最初は `scan` と `plan` だけで様子を見ることをおすすめします。
