# Orca 複数アカウント設定ガイド

**作成者**: 秘書
**作成日**: 2026-10-11
**対象**: 社長（設定作業は社長のPCで行う）

[Orca](https://onorca.dev/) は、Claude Code や Codex を複数の git worktree で並行して動かせるデスクトップアプリ（ADE）。
パパママ社では「メンバーごとに worktree を分けて並行作業」させ、利用上限に達したら **Claude アカウントを切り替えて作業を続ける** 使い方をする。

> 注意: Orca はまだ更新が速く、画面の名前がバージョンで変わることがある（例: `Settings → Agents → Claude Accounts` と `Settings → AI Provider Accounts` の2通りの表記がある）。見当たらないときは設定画面で「Accounts」を探す。

---

## 1. インストール

| OS | 手順 |
|---|---|
| macOS | `brew install --cask stablyai/orca/orca` |
| Windows / Linux | https://onorca.dev/ からインストーラーをダウンロード |

事前に Claude Code 本体を入れておく（`npm install -g @anthropic-ai/claude-code`）。

## 2. 1つ目のアカウント（メイン）をつなぐ

1. ターミナルで `claude` を起動し、`/login` でメインのアカウントにログインする
2. Orca を起動し、`AI-Company` リポジトリを開く
3. Orca は `~/.claude` を自動で読み込むので、追加設定は不要
4. 任意の worktree でターミナルを開き、エージェント選択から **Claude Code** を選んで起動できれば OK

## 3. 2つ目以降のアカウントを追加する

1. Orca の `Settings → Agents → Claude Accounts`（または `Settings → AI Provider Accounts`）を開く
2. **アカウントを追加** してブラウザでログインする
   - 追加ボタンが見当たらないバージョンでは、ステータスバーの Claude チップ（切り替え画面）から追加する
3. 一覧に出た各アカウントに分かりやすいラベルを付ける

| ラベル例 | 用途 |
|---|---|
| `main` | 社長のメインアカウント。秘書・Planner・FP・Critic などの企画系 |
| `sub` | サブアカウント。Creator・Slide_Designer・Video_Producer などの制作系（重い処理） |

4. 各アカウントの利用状況（5時間・7日の上限）が同じ画面に表示されれば完了

## 4. アカウントの切り替え方

1. 画面下のステータスバーにある **Claude のチップ** をクリック → アカウント切り替え画面が開く
2. 使いたいアカウントを選ぶ（ワンクリック）
3. **切り替え後は、そのメンバーの Claude Code セッションを新しく起動し直す**

ステータスバーに出るのは「今アクティブなアカウント」の使用量だけ。ほかのアカウントの残量は切り替え画面で確認する。

## 5. パパママ社での運用ルール

1. 作業は **メンバー（チケット）ごとに worktree を分ける**。例: `TICKET-009` の制作は1つの worktree にまとめる
2. 企画系（秘書・Planner・FP・Critic）は `main`、制作系（Creator・Slide_Designer・Editor・Video_Producer）は `sub` を基本にする
3. アクティブなアカウントの使用量が上限に近づいたら、秘書が社長に報告 → 社長がもう一方のアカウントに切り替える
4. 切り替えたら、動いているセッションを区切りの良いところで終わらせ、**新しいセッションで再開** する（実行中のセッションは古いアカウントのまま動き続けることがあるため）
5. 同じアカウントを2か所でログインしても上限は増えない。上限を分けたいときは別のアカウントを使う

## 6. 既知の制限（2026年10月時点）

| 制限 | 回避策 |
|---|---|
| worktree ごとにアカウントを固定できない（全体で1つのアカウントを切り替える方式。[stablyai/orca#9496](https://github.com/stablyai/orca/issues/9496) で要望中） | 下の「7. 同時に2アカウントで動かしたい場合」を使う |
| 実行中のセッションには切り替えが届かないことがある（[stablyai/orca#19900](https://github.com/stablyai/orca/issues/19900)） | 切り替えたらセッションを起動し直す |
| スマホから切り替えると、デスクトップの表示が古いアカウントのままになることがある（[stablyai/orca#17261](https://github.com/stablyai/orca/issues/17261)） | 切り替えはデスクトップで行う。表示がおかしいときは Orca を再起動 |
| 切り替えをキーボードショートカットで呼べない（[stablyai/orca#15467](https://github.com/stablyai/orca/issues/15467)） | ステータスバーをクリックする |

## 7. 同時に2アカウントで動かしたい場合（上級者向け）

Orca の切り替えは「全体で1アカウント」なので、企画系と制作系を **同時に別アカウントで** 動かしたいときは、Claude Code の `CLAUDE_CONFIG_DIR` でログイン先のフォルダを分ける。

```bash
# 初回だけ：サブアカウント用のフォルダでログイン
CLAUDE_CONFIG_DIR="$HOME/.claude-sub" claude   # 起動後 /login でサブアカウントにログイン
```

以後、Orca の制作系 worktree のターミナルで次のように起動する。

```bash
CLAUDE_CONFIG_DIR="$HOME/.claude-sub" claude
```

毎回打つのが面倒なら、`~/.zshrc`（または `~/.bashrc`）にエイリアスを追加する。

```bash
alias claude-sub='CLAUDE_CONFIG_DIR="$HOME/.claude-sub" claude'
```

注意:
- 新しいフォルダは空の状態から始まるので、MCP・プラグイン・フックは入れ直しが必要
- この方法で起動したセッションは、Orca のステータスバーの使用量表示には反映されないことがある

---

## 参考

- Orca 公式: https://onorca.dev/
- Claude Code in Orca: https://www.onorca.dev/docs/agents/claude-code
- アカウント切り替え（Codex 版。Claude も同じ流れ）: https://www.onorca.dev/docs/agents/codex-hot-swap
- 使用量の表示: https://www.onorca.dev/docs/agents/usage-tracking
- 参考動画: https://youtu.be/bSlAW71HbBc
