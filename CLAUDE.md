# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## リポジトリの目的

これは **AICo株式会社** という擬似AIスタートアップのエージェント組織シミュレーションリポジトリです。実際のアプリケーションコードではなく、AIエージェントが「社員」として振る舞うためのフォルダ・ドキュメント構造です。

## アーキテクチャ

### Organization/ — 社員エージェント

各社員は `Organization/<部門>/<社員名>/` 以下に2つのフォルダを持つ：

- **`Memory/`** — 個人の経歴・過去の作業履歴・意思決定の記録を格納
- **`Skills/`** — その社員が実行できる手順書・ロールプレイのスクリプトを格納

現在の組織：
- `CEO/` — 木村誠一郎（全社方針・意思決定）
- `Engineering/` — 中村（EM）・田中（BE）・鈴木（FE）・山本（ML）
- `Sales/` — 高橋（SM）・佐藤（インサイド）・伊藤（フィールド）
- `HR/` — 渡辺京子（HRM）・渡辺真琴（採用担当）

### Workspace/ — 共有作業スペース

エージェント間の成果物受け渡しとタスク管理を担う：

- **`Output/AgentOutput/`** — 各エージェントが生成した中間成果物を置く場所
- **`Output/FinalOutput/`** — レビュー済み・完成した最終成果物
- **`TicketManagement/`** — カンバン方式。チケットファイルをフォルダ間で移動してステータスを管理

## チケット管理の運用ルール

チケットファイルのフォーマット（`TICKET-XXX_タイトル.md`）：

```
**ステータス**: ToDo | Doing | Waiting | Done
**優先度**: 高 | 中 | 低
**担当者**: <社員フォルダ名>
**作成者**: <社員フォルダ名>
**作成日**: YYYY-MM-DD
```

ステータス変更 = ファイルをフォルダ間で移動 + ファイル内の `**ステータス**` フィールドを更新。

## 新規社員・部門の追加パターン

```bash
mkdir -p Organization/<部門>/<社員名>/{Memory,Skills}
```

- `Memory/profile.md` に氏名・役職・経歴・担当領域を記載
- `Skills/<役割>.md` にスキルセットと作業フロー（番号付きステップ）を記載

## 成果物の格納先ルール

| 誰が | どこに |
|---|---|
| 各エージェントが作業中に生成したもの | `Workspace/Output/AgentOutput/` |
| 完成・承認済みの最終納品物 | `Workspace/Output/FinalOutput/` |
