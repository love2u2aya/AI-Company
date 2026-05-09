# AI-Company

擬似AIスタートアップ企業のエージェント組織構造です。

## 会社概要

**会社名**: AICo株式会社  
**事業内容**: AIソリューション開発・提供  
**設立**: 2024年  

## 組織構成

```
AI-Company/
├── Organization/               # 組織（社員エージェント）
│   ├── CEO/                   # 代表取締役
│   ├── Engineering/           # 開発部門
│   │   ├── EngineeringManager/
│   │   ├── Engineer_Tanaka/
│   │   ├── Engineer_Suzuki/
│   │   └── Engineer_Yamamoto/
│   ├── Sales/                 # 営業部門
│   │   ├── SalesManager/
│   │   ├── Sales_Sato/
│   │   └── Sales_Ito/
│   └── HR/                    # 人事部門
│       ├── HRManager/
│       └── HR_Watanabe/
└── Workspace/                 # 共有作業スペース
    ├── Output/
    │   ├── AgentOutput/       # 各エージェントの中間出力
    │   └── FinalOutput/       # 最終成果物
    └── TicketManagement/      # タスク管理
        ├── ToDo/              # 未着手
        ├── Doing/             # 作業中
        ├── Waiting/           # 待機中
        └── Done/              # 完了
```

## 各フォルダの役割

| フォルダ | 役割 |
|---|---|
| `Memory/` | エージェントの記憶・経験・履歴を保存 |
| `Skills/` | エージェントが持つスキル・手順書を保存 |
| `AgentOutput/` | 各エージェントが生成した中間アウトプット |
| `FinalOutput/` | レビュー済みの最終成果物 |
| `TicketManagement/` | カンバン方式のタスク管理 |
