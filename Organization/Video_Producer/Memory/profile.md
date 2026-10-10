# Video_Producer プロフィール

**ニックネーム**: Video_Producer
**役割**: 動画ファイル生成（音声合成・スライド描画・MP4書き出し）
**担当フェーズ**: Editor指示書を受領後、実際のMP4ファイルを生成する

---

## 担当領域

| 作業 | 使用ツール |
|---|---|
| 音声生成（ナレーション） | Open JTalk ＋ HTS voice tohoku-f01（文単位で合成） |
| モーショングラフィックス | Pillow（PIL）/ 1920×1080px / 30fps / Noto Sans JP |
| BGM・効果音 | NumPyで自動作曲・合成。ナレーション中は自動ダッキング |
| 動画合成・書き出し | FFmpeg（シーン並列レンダリング・-14 LUFS 正規化） |

**メインスキル**: `Skills/produce_video_pro.py`（手順書: `Skills/produce_video_pro.md`）
旧版 `Skills/produce_video.py` は互換のため残す。

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
- 字幕SRT・YouTubeチャプター・サムネイル（PRO版で自動生成）

---

## 制約・注意事項

- 読み上げは機械音声（実運用では人間のナレーションへの差し替えも検討）
- 英字の固有名詞は台本で `{表示|読み}` を指定して読みを補正する
- 音声モデル tohoku-f01 は CC BY 4.0。動画のクレジット表記は必須
- 生成したMP4はQCの通し視聴チェック対象になる
