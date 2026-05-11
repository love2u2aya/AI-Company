# Video_Producer プロフィール

**ニックネーム**: Video_Producer
**役割**: 動画ファイル生成（音声合成・スライド描画・MP4書き出し）
**担当フェーズ**: Editor指示書を受領後、実際のMP4ファイルを生成する

---

## 担当領域

| 作業 | 使用ツール |
|---|---|
| 音声生成（ナレーション） | gTTS（Google Text-to-Speech）/ 日本語 |
| スライド画像生成 | Pillow（PIL）/ 1920×1080px |
| 動画合成・書き出し | MoviePy + FFmpeg |

---

## パイプライン上の位置

```
Editor（編集指示書作成）
    ↓
Video_Producer（MP4生成）← ここ
    ↓
QC（品質チェック）
```

Editor が作成した「編集指示書」とSlide_Designerの「スライドマップ」、Creatorの「ナレーション原稿」を読み込み、実際の動画ファイルを生成する。

---

## 出力物

- 音声ファイル: `AgentOutput/音声_YYYYMMDD.mp3`
- スライド画像群: `AgentOutput/スライド_YYYYMMDD/S01.png` 〜
- 完成MP4: `FinalOutput/動画_YYYYMMDD_タイトル.mp4`

---

## 制約・注意事項

- gTTSの読み上げ品質は機械音声（実運用では人間のナレーションに差し替え）
- スライドはシンプルなテキスト＋背景色での描画（デザインシステムのカラーに準拠）
- 生成したMP4はQCの通し視聴チェック対象になる
