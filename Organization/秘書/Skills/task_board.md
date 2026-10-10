# 秘書スキル：やることボード（全セッション横断の未解決タスク一覧）

各セッションで出た「未解決のこと」「後でやること」を **1か所** に集める仕組み。
社長はスマホ・PCどちらからでも、ここを見れば全部わかる。

- **ボード本体**: https://claude.ai/artifact/JKbSyQhWamQ3VXADR7x6GX （非公開。社長本人だけが開ける）
- **データ**: ボードの `tasks` コレクション（ArtifactData ツールで読み書き）
- **Google Tasks**: リスト名「やることボード」と双方向同期（`gtasks_sync.py`）

> このリポジトリは公開リポジトリなので、タスクの中身（個人・他案件の情報）は**リポジトリに書かない**。
> 書き込み先は必ずボード（Artifact）にする。

---

## 1件のデータ形式（`tasks/<id>`）

| フィールド | 内容 |
|---|---|
| `title` | やること（1行・動詞で終える） |
| `project` | パパママ社YouTube / 社長と娘アニメ / 杉並5団 / セカプラ / IFA・FP業務 / アウェアネス / ふるさと納税 / 開発環境・ツール / 個人・家庭 / その他 |
| `status` | `open` / `done` |
| `priority` | 高 / 中 / 低 |
| `due` | `YYYY-MM-DD`（無ければ空文字） |
| `owner` | 自分 / Claude |
| `note` | 経緯・選択肢・補足 |
| `source` / `sessionId` | 出どころのセッション名とID |
| `createdAt` / `updatedAt` / `completedAt` | ISO8601（UTC） |
| `gtaskId` | Google Tasks 側のID（同期で自動付与） |

ID はプロジェクトの頭文字＋連番（`pm-23`、`sg-12` など）。既存IDは `list` で確認してから採番する。

---

## 作業フロー

### A. セッションの終わりに未解決を登録する
1. その会話で「終わっていないこと」「ユーザーの返事待ち」「後でやると言ったこと」を洗い出す
2. ボードを `list` して、同じ内容が既にあれば `update`（note に追記）、無ければ `set` で新規追加
3. 片付いたものは `status: "done"` と `completedAt` を `update`
4. 書き込みは `batch` で1回にまとめる。既存ドキュメントには必ず `if_version` を付ける

### B. 「やることボード見せて」「今日なにやる？」と言われたら
1. `list`（`query.limit: 1000`）で全件取得
2. 期限切れ → 7日以内 → 優先度「高」の順に要約して返す
3. ボードのURLを添える

### C. 「タスク同期して」（Google Tasks 双方向同期）
1. `ArtifactData` の `list`（`collection: tasks`, `query.limit: 1000`, `out_dir: <作業用ディレクトリ>`）で書き出す
2. 実行:
   ```bash
   python3 Organization/秘書/Skills/gtasks_sync.py <作業用ディレクトリ>/tasks client_secret.json
   ```
3. 標準出力の `boardOps` を `ArtifactData` の `batch` でボードへ反映（`set` は新規、`update` は `if_version` 付き）
4. 結果（Google側の作成・更新件数、ボード側の変更件数）を社長に一行で報告

同期ルール:
- ボードの未完了タスク → Google Tasks に「[プロジェクト] 件名」で作成
- 両方にあるもの → 更新日時が新しい側が勝つ（タイトル・期限・完了状態・メモ）
- スマホの Google Tasks で追加したもの → ボードに追加（「[杉並5団] ○○」と書けばそのプロジェクトへ。無ければ「受信箱」）
- Google Tasks で削除したもの → ボード側は完了扱い

---

## Google Tasks 同期の初回設定（社長の手作業・1回だけ）

YouTube／Drive のアップロードで使っている Google Cloud プロジェクト（`client_secret.json`）をそのまま使う。

1. Google Cloud Console →「APIとサービス」→「ライブラリ」→ **Google Tasks API** を有効にする
2. 「OAuth同意画面」→ スコープに `https://www.googleapis.com/auth/tasks` を追加
   （同意画面が「テスト」のままだと約7日でトークンが切れる。「本番環境」にしておく）
3. 手元のPCで実行:
   ```bash
   pip install google-api-python-client google-auth-oauthlib
   python3 Organization/秘書/Skills/gtasks_sync.py <書き出し先>/tasks client_secret.json
   ```
   表示されたURLを開いて「許可」→ 開けなかったページのURL全体をコピーし、
   ```bash
   python3 Organization/秘書/Skills/gtasks_sync.py <書き出し先>/tasks client_secret.json --redirected-url "<URL>"
   ```
4. `gtasks_token.json` が同じフォルダにできれば完了（`.gitignore` 済み・コミットしない）
5. クラウドのセッションでも同期したい場合は、トークンJSONの中身を環境のシークレット `GTASKS_TOKEN_JSON` に登録する

### Google Keep について
Keep の公式APIは Google Workspace（法人）アカウント専用で、個人の Gmail アカウントからは使えない。
2023年以降 Keep の「リマインダー」は Google Tasks に統合されたため、Tasks と同期する形にしている。
Google Tasks は Gmail・カレンダーの右サイドバーと、スマホの Google Tasks アプリから見られる。

---

## 全セッションで自動登録させる（各PCで1回）

このリポジトリ以外のセッション（Win・Mac のローカル作業）でも登録させるには、
各PCの `~/.claude/CLAUDE.md`（全プロジェクト共通の指示）に次を追記する:

```markdown
## やることボード
- 未解決のこと・後でやること・ユーザーの返事待ちが残ったら、会話の最後に
  やることボード https://claude.ai/artifact/JKbSyQhWamQ3VXADR7x6GX の tasks コレクションへ
  ArtifactData で登録する（既存と重複するものは update、片付いたものは status を done に）。
- 形式と手順は love2u2aya/AI-Company の Organization/秘書/Skills/task_board.md に従う。
```
