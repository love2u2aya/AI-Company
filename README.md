# パパママ社

動画配信の広告収益で稼ぐ擬似会社のエージェント組織です。

## 会社概要

**会社名**: パパママ社  
**事業内容**: 動画配信・広告収益最大化  
**目標**: バズる動画を継続的に量産し、広告収益とスポンサー収益を伸ばす

## 指揮系統

```
社長（あなた）
    ↓ 指示・方針
   秘書
    ↓ タスク分解・割り振り・進捗管理
┌──────────────────────────────┐
Planner  Creator  Editor  Designer  SNS_Manager
```

## 組織構成

```
AI-Company/
├── Organization/
│   ├── 社長/          # あなた（指示を出す側）
│   ├── 秘書/          # 全体コーディネーター
│   │   ├── Memory/
│   │   └── Skills/
│   ├── Planner/       # バズる動画の企画担当
│   │   ├── Memory/
│   │   └── Skills/
│   ├── Creator/       # 動画クリエイター（撮影・素材制作）
│   │   ├── Memory/
│   │   └── Skills/
│   ├── Editor/        # 動画編集者
│   │   ├── Memory/
│   │   └── Skills/
│   ├── Designer/      # サムネイル・グラフィックデザイナー
│   │   ├── Memory/
│   │   └── Skills/
│   └── SNS_Manager/   # SNS運用・広告収益管理
│       ├── Memory/
│       └── Skills/
└── Workspace/
    ├── Output/
    │   ├── AgentOutput/   # 各メンバーの中間成果物
    │   └── FinalOutput/   # 完成・確定した成果物
    └── TicketManagement/  # カンバン式タスク管理
        ├── ToDo/
        ├── Doing/
        ├── Waiting/
        └── Done/
```

## 各フォルダの役割

| フォルダ | 役割 |
|---|---|
| `Memory/` | そのメンバーの役割・担当・過去履歴 |
| `Skills/` | 作業手順・判断基準・チェックリスト |
| `AgentOutput/` | 企画書・素材一覧・分析レポートなど中間成果物 |
| `FinalOutput/` | 完成動画情報・採用サムネイル・確定案件記録など |
| `TicketManagement/` | ToDo→Doing→Waiting→Done でステータス管理 |
