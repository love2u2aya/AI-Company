#!/usr/bin/env python3
"""
SNS_Managerスキル：YouTube非公開アップロード

使い方:
    python3 youtube_upload.py <動画ファイル.mp4> <client_secret.json>

例:
    python3 Organization/SNS_Manager/Skills/youtube_upload.py \
        "Workspace/Output/FinalOutput/動画_第5弾_20260511.mp4" \
        client_secret.json

初回実行時にブラウザでOAuth認証が必要です。
認証後はトークンが token.json に保存され、次回から自動認証します。
"""

import sys
import os
import json
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
TOKEN_PATH = Path(__file__).parent / "token.json"


def get_credentials(client_secret_path: str) -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            # ポート8080でローカルサーバーを起動してOAuthコードを受け取る
            creds = flow.run_local_server(port=8080, open_browser=True)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def upload_video(video_path: str, client_secret_path: str) -> str:
    creds = get_credentials(client_secret_path)
    youtube = build("youtube", "v3", credentials=creds)

    # FinalOutputのメタデータファイルからタイトル・説明・タグを読み込む
    video_file = Path(video_path)
    metadata_candidates = list(video_file.parent.glob("動画_*.md"))
    title = video_file.stem
    description = "iDeCoシリーズ 第5弾"
    tags = ["iDeCo", "老後資金", "繰り下げ受給", "就労継続", "加給年金", "55歳", "年金対策"]

    if metadata_candidates:
        md_path = metadata_candidates[0]
        text = md_path.read_text(encoding="utf-8")
        # タイトル抽出
        for line in text.splitlines():
            if line.startswith("## タイトル") or "タイトル" in line and "**" in line:
                next_idx = text.splitlines().index(line) + 1
                lines = text.splitlines()
                if next_idx < len(lines):
                    candidate = lines[next_idx].strip().lstrip("#").strip()
                    if candidate:
                        title = candidate
                        break
        # 説明抽出（概要欄セクション）
        if "## 概要欄" in text or "概要欄" in text:
            start = text.find("## 概要欄")
            if start == -1:
                start = text.find("概要欄")
            end = text.find("\n## ", start + 1)
            if end == -1:
                end = start + 3000
            description = text[start:end].strip()

    print(f"アップロード開始: {video_path}")
    print(f"タイトル: {title}")

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": "27",  # 教育
            "defaultLanguage": "ja",
            "defaultAudioLanguage": "ja",
        },
        "status": {
            "privacyStatus": "private",  # 非公開
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024,  # 5MB chunks
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"\rアップロード中... {pct}%", end="", flush=True)

    print(f"\n完了！")
    video_id = response["id"]
    url = f"https://youtu.be/{video_id}"
    print(f"非公開URL: {url}")
    print(f"YouTube Studio: https://studio.youtube.com/video/{video_id}/edit")
    return url


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    upload_video(sys.argv[1], sys.argv[2])
