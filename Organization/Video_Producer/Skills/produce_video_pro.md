# Video_Producer スキル（PRO版）：シーン台本 → モーショングラフィックス動画

`produce_video_pro.py` は、JSON形式の「シーン台本」1つから、次をまとめて自動生成する。
ナレーション、アニメーション、字幕、BGM、効果音、サムネイル、YouTubeチャプター。

旧版 `produce_video.py`（静止スライド＋全文一括読み上げ）は互換のため残している。

---

## 旧版との比較

| 項目 | 旧版 produce_video.py | PRO版 produce_video_pro.py |
|---|---|---|
| 音声 | 全文を一括で合成し、尺をスライド数で均等割り | **1文ずつ合成**し、字幕とアニメを発話に合わせる |
| 映像 | 静止画のテキストスライド | **30fpsのアニメーション**（10テンプレート） |
| フォント | DejaVu（日本語が表示されない） | **Noto Sans JP**（Black/Bold/Medium/Regular/Light） |
| 字幕 | なし | 文単位で焼き込み＋`.srt`出力。長さの揃った2行に自動で折り返す |
| BGM・効果音 | なし | BGMを自動作曲し、ナレーション中は自動で音量を下げる。効果音4種を合成 |
| 音量 | 未調整 | YouTube基準の **-14 LUFS** に正規化 |
| 付属物 | なし | サムネイル（1280×720）、YouTubeチャプター、字幕SRT |
| 速度 | 1プロセス | シーン単位で並列レンダリング（4コアで約4分の動画を約4分で生成） |

---

## 作業フロー

1. **初回のみ**: `bash Organization/Video_Producer/Skills/setup_pro.sh` を実行する。
   Open JTalk・Noto Sans CJK・話者モデル tohoku-f01 を導入する。
2. Creatorのナレーション原稿とSlide_Designerのスライドマップをもとに、**シーン台本(JSON)** を作る。
   - 置き場所: `Workspace/Output/AgentOutput/シーン台本_<タイトル>_YYYYMMDD.json`
3. プレビュー確認（任意）: 各シーンの最終フレームを静止画に書き出し、レイアウト崩れを確認する。
4. 本番生成:
   ```bash
   python3 Organization/Video_Producer/Skills/produce_video_pro.py \
       Workspace/Output/AgentOutput/シーン台本_XXX.json <出力ディレクトリ>
   ```
5. 生成物（`<slug>.mp4` / `.srt` / `_chapters.txt` / `_thumbnail.png`）をQCに渡す。
   - MP4は `.gitignore` 対象のため、Google Drive（`SNS_Manager/Skills/drive_upload.py`）で共有する。
   - 記録用のメタデータは `Workspace/Output/FinalOutput/動画_<タイトル>_YYYYMMDD.md` に残す。

---

## シーン台本の書き方

```json
{
  "title": "動画タイトル",
  "slug": "出力ファイル名",
  "channel": "パパママ社",
  "hud": "画面右上に常時表示する番組名",
  "voice": {"model": "tohoku-f01-neutral", "speed": 1.12, "pitch": 0.0},
  "thumbnail": {"big": "大見出し", "sub": "サブ", "badge": "赤バッジ"},
  "scenes": [ { "type": "...", "narration": ["1文目", "2文目"], ... } ]
}
```

### 共通ルール

- **`narration`**: 1要素を1文として書く。文ごとに音声合成し、その長さからシーンの尺を自動で決める。
- **`{表示|読み}`**: 字幕には「表示」を出し、音声は「読み」で読み上げる。
  - 例: `{Claude|クロード}`、`{3〜4か月|さんからよんかげつ}`
  - 英字の固有名詞には必ず付ける。
- **`"cue": n`**: 要素を n番目（0始まり）の文の読み始めに合わせて登場させる。
  - 例: 「Amazonは〜」と読む瞬間にAmazonの棒を伸ばす。
- **`chapter_title`**: このキーを持つシーンの開始時刻が、YouTubeチャプターとして出力される。
- **`source`**: 指定すると画面右上に出典を表示する。数字を出すシーンには必ず付ける。

### シーンテンプレート（デザインシステムとの対応）

| type | 内容 | 主なキー |
|---|---|---|
| `title` | オープニング（タイトルをワイプで表示＋波紋） | kicker, title, subtitle |
| `chapter` | 章扉（Type4 ステップ進行：今の章をゴールドで強調） | current, chapters |
| `impact` | インパクト数字（Type1：カウントアップ＋グロー） | context, value, prefix, suffix, decimals, caption, color |
| `bars` | 横棒グラフ（Type7：棒が伸び、数値もカウント） | title, unit, items[label,value,display,highlight] |
| `cards` | 比較カード（3〜4枚が順に登場） | title, items[tag,head,body,color] |
| `curve` | 成長曲線（対数軸、線が伸びていく描画＋コールアウト） | points[x,y,label,xlabel], log, callout |
| `compare` | ビフォーアフター（Type2：左右パネル） | left/right[head,lines,color] |
| `timeline` | 年表（線が伸び、点がポップ。上下交互にラベル） | items[date,text,color] |
| `list` | まとめリスト（番号付きで順に登場） | title, items[text] |
| `outro` | エンディング（メッセージ＋登録ボタン＋クレジット） | message, cta, credits |

---

## 判断基準・チェックリスト

- [ ] 数字には必ず出典（`source` またはナレーション内）を付ける。概数は「約」「概算」と明記する。
- [ ] 英字の固有名詞には `{表示|読み}` で読みを付ける。数字の読みは Open JTalk の自動変換で概ね正しく読まれる。
- [ ] 1シーンの文は2〜5文に収める。長いとアニメーションが間延びする。
- [ ] クレジットに「HTS voice tohoku-f01（CC BY 4.0 東北大学 伊藤・能勢研究室）」を必ず入れる。ライセンス上の義務。
- [ ] 公開前に必ずQCの通し視聴を通す（機械音声の不自然な読みは `{表示|読み}` で修正する）。

---

## 制約

- 音声は HTS（統計的音声合成）のため、人間のナレーションには及ばない。本番運用では収録音声への差し替えも検討する。
- この環境では、Google TTS や Edge TTS などのクラウド音声合成は外部通信ポリシーで使えない。すべてローカルで動く構成にしている。
