#!/usr/bin/env python3
"""
SNS_Managerスキル：Google Driveアップロード

使い方:
    python3 drive_upload.py <ファイルパス> <client_secret.json>

例:
    python3 Organization/SNS_Manager/Skills/drive_upload.py \
        "Workspace/Output/FinalOutput/動画_第5弾_20260511.mp4" \
        client_secret.json

初回実行時にブラウザでOAuth認証が必要です。
認証後はトークンが drive_token.json に保存されます。

【OAuth認証の手順】
1. 表示されたURLをブラウザで開く
2. Googleアカウントを選択
3. 「このアプリはGoogleによって確認されていません」画面 → 「詳細」をクリック → 「（安全でないページ）に移動」をクリック
4. アクセス許可の画面で「許可」ボタンをクリック（「続行」ではなく「許可」）
5. 「このサイトにアクセスできません」となったアドレスバーのURL全体をコピーして貼り付け
"""

import sys
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_PATH = Path(__file__).parent / "drive_token.json"


def get_credentials(client_secret_path: str) -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            flow.redirect_uri = "http://localhost"
            auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

            print("\n" + "="*60)
            print("【Google Drive OAuth認証】")
            print("="*60)
            print("\n手順:")
            print("1. 以下のURLをブラウザで開く")
            print("2. Googleアカウントを選択")
            print("3. 警告画面 →「詳細」→「安全でないページに移動」をクリック")
            print("4. ★「許可」ボタンをクリック（「続行」ではなく「許可」）★")
            print("5. 「アクセスできません」のURLをアドレスバーからコピーして貼り付け")
            print("\n" + "-"*60)
            print(auth_url)
            print("-"*60)

            redirected = input("\nリダイレクト先のURL全体を貼り付け: ").strip()
            parsed = urlparse(redirected)
            code = parse_qs(parsed.query).get("code", [None])[0]
            if not code:
                raise ValueError(f"URLからcodeが取得できませんでした: {redirected}")
            flow.fetch_token(code=code)
            creds = flow.credentials

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        print("認証成功。トークンを保存しました。")
    return creds


def upload_file(file_path: str, client_secret_path: str, folder_id: str = None) -> str:
    creds = get_credentials(client_secret_path)
    service = build("drive", "v3", credentials=creds)

    file_path = Path(file_path)
    file_name = file_path.name
    file_size = file_path.stat().st_size

    # MIMEタイプ判定
    ext = file_path.suffix.lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".md":  "text/plain",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    metadata = {"name": file_name}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaFileUpload(
        str(file_path),
        mimetype=mime_type,
        resumable=True,
        chunksize=5 * 1024 * 1024,  # 5MB chunks
    )

    print(f"\nアップロード開始: {file_name} ({file_size / 1024 / 1024:.1f} MB)")

    request = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,webViewLink,webContentLink",
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"\rアップロード中... {pct}%", end="", flush=True)

    print("\n完了！")
    file_id = response["id"]
    view_link = response.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")

    # 共有設定（リンクを知っている全員が閲覧可能）
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    share_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    print(f"\n共有リンク: {share_link}")
    print(f"ファイルID: {file_id}")
    return share_link


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    upload_file(sys.argv[1], sys.argv[2])
