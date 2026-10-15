# 動画制作手順｜ElevenLabs「パパの声」でナレーション＋テロップ動画（3本）

**作成日**: 2026-10-15
**作成者**: 秘書（Video_Producer向け）
**実行場所**: 社長のローカルPC（クラウド環境からはElevenLabsにつながらないため）
**関連チケット**: TICKET-011

---

## 作る動画

| # | 原稿 | 段落 | 文字数 | 尺の目安 |
|---|---|---|---|---|
| 1 | `ナレーション原稿_iDeCo改正前編_20261015.md` | 82 | 約2,790字 | 約9〜10分 |
| 2 | `ナレーション原稿_iDeCo改正後編_20261015.md` | 76 | 約2,820字 | 約9〜10分 |
| 3 | `ナレーション原稿_iDeCoネタ帳_8つのポイント_20261015.md` | 48 | 約2,020字 | 約6〜7分 |

尺の目安は無音の確認版（1秒5.5文字）で測ったもの。実際の長さは声の速さで変わる。

## 準備（最初の1回だけ）

1. ffmpeg を入れる（Mac：`brew install ffmpeg`／Windows：`winget install ffmpeg`）
2. Pillow を入れる：`pip install pillow`
3. ElevenLabs の API キーを環境変数に入れる
   - ElevenLabs のサイト → 右上のアカウント → API Keys で作成（Text to Speech と Voices の読み取りを許可）
   - Mac：`export ELEVENLABS_API_KEY=...`／Windows：`setx ELEVENLABS_API_KEY ...`
   - キーはチャットやファイルに貼らない

## 手順

1. 「パパ」の声を探す
   ```
   python3 Organization/Video_Producer/Skills/produce_video_elevenlabs.py --list-voices
   ```
   - 一覧に出た名前とIDを確認する。名前に「パパ」が入っていればそのまま使える
   - 見つからなければ、ElevenLabs のサイトの「My Voices」で名前を確認し、`--voice-id` で指定する
2. お試し（最初の5段落だけ。声と速さを確認）
   ```
   python3 Organization/Video_Producer/Skills/produce_video_elevenlabs.py \
     Workspace/Output/AgentOutput/ナレーション原稿_iDeCo改正前編_20261015.md \
     Workspace/Output/FinalOutput --voice-name パパ --limit 5
   ```
   - 速さは `--speed 0.9〜1.1` で調整。声が不安定なら `--stability 0.6`
   - お試しの音声は `_work/audio/` に残るので、設定を変えたらそのフォルダを消してから作り直す
3. 本番（3本）
   ```
   for f in iDeCo改正前編_20261015 iDeCo改正後編_20261015 iDeCoネタ帳_8つのポイント_20261015; do
     python3 Organization/Video_Producer/Skills/produce_video_elevenlabs.py \
       Workspace/Output/AgentOutput/ナレーション原稿_$f.md Workspace/Output/FinalOutput --voice-name パパ
   done
   ```
   - 途中で止まっても、もう一度同じコマンドを実行すれば続きから作る

## できあがるもの（`Workspace/Output/FinalOutput/`）

- `動画_iDeCo改正前編_20261015.mp4` ほか2本（1920×1080・30fps）
- 同じ名前の `.srt`（字幕。YouTubeにそのまま入れられる）
- `動画_…_work/`（音声・画像の作業フォルダ。完成後は消してよい）
- mp4・mp3 は `.gitignore` 対象なのでコミットされない。完成したら「動画_…md」に尺・保存場所を記録してコミットする

## 画面の作り

- 上：セクション名（例「① 一番のポイントは『今年の税金が減る』」）とチャンネル名
- 中央：スライドの見出し（S01はタイトル）
- 下：今読んでいる文のテロップ（白帯・黒文字。長い段落は句点で区切って切り替え）
- 見本：`テロップ見本_20261015/`

## 注意

- 図や表の入ったスライド（Slide_Designer担当）はまだない。今回は「見出し＋テロップ」の仮版。スライド完成後に差し替える
- ネタ帳編の原稿には、FP未確認の箇所が2つある（原稿の制作メモ参照）。公開前にFPが確認する
- ElevenLabs の文字数クレジットを使う（3本で約7,600字）。残量を確認してから本番を作る
- 公開前に QC のチェックと社長承認②（非公開プレビュー）が必要
