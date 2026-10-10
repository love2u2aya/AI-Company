#!/usr/bin/env python3
"""
秘書スキル：やることボード ⇔ Google Tasks 双方向同期

使い方:
    python3 gtasks_sync.py <tasks> <client_secret.json> [--list やることボード] [--dry-run]
    python3 gtasks_sync.py <tasks> <client_secret.json> --redirected-url "<URL>"   # 初回認証の2段目

<tasks> は「やることボード」(claude.ai Artifact) の tasks コレクションを書き出したもの。
  - ディレクトリ: ArtifactData の out_dir で書き出した <doc_id>.json の集まり（ファイル名がID）
  - JSONファイル: [{"id", "title", ...}, ...] の配列（同期後に上書き更新される）
1件 = {"title", "project", "status": "open"|"done", "priority", "due": "YYYY-MM-DD",
       "note", "updatedAt": ISO8601, "gtaskId"?}
ボードに書き戻す変更は標準出力の JSON（boardOps）に出す。Claude がそれを ArtifactData で反映する。

【同期ルール】
- ボードの未完了タスクで gtaskId が無いもの → Google Tasks に作成し gtaskId を記録
- 両方にあるもの → 更新日時が新しい側を正とする（タイトル・期限・完了状態）
- Google Tasks で新規追加されたもの → ボードに追加（タイトルが「[プロジェクト] 件名」ならプロジェクトに振り分け）
- Google Tasks で削除されたもの → ボード側は完了扱い
- Google Tasks 側のタイトルは「[プロジェクト] 件名」、メモ末尾に「#board:<id>」を付けて対応を保つ

認証は drive_upload.py と同じ2段階方式。トークンは gtasks_token.json に保存（.gitignore 済み）。
環境変数 GTASKS_TOKEN_JSON にトークンJSONを入れておけば、クラウドのセッションでも動く。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

SCOPES = ["https://www.googleapis.com/auth/tasks"]
TOKEN_PATH = Path(__file__).parent / "gtasks_token.json"
DEFAULT_LIST = "やることボード"
MARKER_RE = re.compile(r"\n*#board:([A-Za-z0-9_\-.~:@+]+)\s*$")
TITLE_RE = re.compile(r"^\[(.+?)\]\s*(.+)$")
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


# ---------- 純粋ロジック（テスト可能） ----------

def parse_ts(s):
    if not s:
        return EPOCH
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return EPOCH
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def g_title(task):
    p = (task.get("project") or "").strip()
    return f"[{p}] {task['title']}" if p else task["title"]


def g_notes(task):
    body = (task.get("note") or "").strip()
    marker = f"#board:{task['id']}"
    return f"{body}\n\n{marker}" if body else marker


def g_due(due):
    return f"{due}T00:00:00.000Z" if due else None


def split_g_title(title):
    m = TITLE_RE.match(title or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else ("", (title or "").strip())


def split_g_notes(notes):
    notes = notes or ""
    m = MARKER_RE.search(notes)
    return (notes[: m.start()].strip(), m.group(1)) if m else (notes.strip(), None)


def g_body(task):
    body = {
        "title": g_title(task),
        "notes": g_notes(task),
        "status": "completed" if task.get("status") == "done" else "needsAction",
    }
    due = g_due(task.get("due"))
    if due:
        body["due"] = due
    return body


def merge(local, remote, now):
    """local: ボードのタスク一覧, remote: Google Tasks の一覧(API の item 形式)。
    戻り値: (更新後のローカル一覧, Google への操作リスト, ボードへの変更リスト)
    Google 操作: {"op": "insert"|"patch", "localId", "gid"?, "body"}
    ボード変更: {"op": "set"|"update", "id", "data"}"""
    by_gid = {g["id"]: g for g in remote}
    by_marker = {}
    for g in remote:
        _, lid = split_g_notes(g.get("notes"))
        if lid:
            by_marker[lid] = g

    out, g_ops, b_ops, seen = [], [], [], set()
    for t in local:
        t = dict(t)
        g = by_gid.get(t.get("gtaskId")) or by_marker.get(t["id"])
        if g is None:
            if t.get("gtaskId"):
                # Google 側で削除された → 完了扱い
                patch = {"gtaskId": "", "updatedAt": iso(now)}
                if t.get("status") != "done":
                    patch.update(status="done", completedAt=iso(now))
                t.update(patch)
                b_ops.append({"op": "update", "id": t["id"], "data": patch})
            elif t.get("status") != "done":
                g_ops.append({"op": "insert", "localId": t["id"], "body": g_body(t)})
            out.append(t)
            continue

        seen.add(g["id"])
        if t.get("gtaskId") != g["id"]:
            t["gtaskId"] = g["id"]
            b_ops.append({"op": "update", "id": t["id"], "data": {"gtaskId": g["id"]}})

        if parse_ts(g.get("updated")) > parse_ts(t.get("updatedAt")):
            project, title = split_g_title(g.get("title"))
            note, _ = split_g_notes(g.get("notes"))
            patch = {
                "title": title or t["title"],
                "status": "done" if g.get("status") == "completed" else "open",
                "due": (g.get("due") or "")[:10],
                "note": note,
            }
            if project:
                patch["project"] = project
            if patch["status"] == "done" and t.get("status") != "done":
                patch["completedAt"] = g.get("completed") or iso(now)
            changed = {k: v for k, v in patch.items() if t.get(k, "") != v}
            if changed:
                changed["updatedAt"] = g.get("updated")
                t.update(changed)
                b_ops.append({"op": "update", "id": t["id"], "data": changed})
        else:
            want = g_body(t)
            have = {"title": g.get("title"), "notes": g.get("notes") or "", "status": g.get("status")}
            if g.get("due"):
                have["due"] = g["due"][:10] + "T00:00:00.000Z"
            if want != have:
                if "due" not in want and "due" in have:
                    want["due"] = None
                g_ops.append({"op": "patch", "localId": t["id"], "gid": g["id"], "body": want})
        out.append(t)

    for g in remote:
        if g["id"] in seen or g.get("deleted") or not (g.get("title") or "").strip():
            continue
        _, lid = split_g_notes(g.get("notes"))
        if lid and any(x["id"] == lid for x in out):
            continue
        project, title = split_g_title(g.get("title"))
        note, _ = split_g_notes(g.get("notes"))
        new_id = "g-" + re.sub(r"[^A-Za-z0-9_\-]", "", g["id"])[:60]
        ts = g.get("updated") or iso(now)
        t = {
            "id": new_id, "title": title, "project": project or "受信箱",
            "status": "done" if g.get("status") == "completed" else "open",
            "priority": "中", "due": (g.get("due") or "")[:10], "note": note, "owner": "",
            "source": "Google Tasksから追加", "createdAt": ts, "updatedAt": ts, "gtaskId": g["id"],
        }
        out.append(t)
        b_ops.append({"op": "set", "id": new_id, "data": {k: v for k, v in t.items() if k != "id"}})
        # ボードIDをメモに埋めて対応を固定する
        g_ops.append({"op": "patch", "localId": new_id, "gid": g["id"], "body": {"notes": g_notes(t)}})
    return out, g_ops, b_ops


def load_local(path):
    path = Path(path)
    if path.is_dir():
        return [{"id": f.stem, **json.loads(f.read_text(encoding="utf-8"))} for f in sorted(path.glob("*.json"))]
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- Google API ----------

def get_credentials(client_secret_path, redirected_url=None):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    env_token = os.environ.get("GTASKS_TOKEN_JSON")
    if env_token:
        creds = Credentials.from_authorized_user_info(json.loads(env_token), SCOPES)
    elif TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
        flow.redirect_uri = "http://localhost"
        if not redirected_url:
            auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
            print(auth_url, file=sys.stderr)
            print("\n上のURLを開いて「許可」→ 表示できなかったページのURL全体を", file=sys.stderr)
            print('--redirected-url "<URL>" に付けてもう一度実行してください。', file=sys.stderr)
            sys.exit(2)
        code = parse_qs(urlparse(redirected_url).query).get("code", [None])[0]
        if not code:
            raise ValueError(f"URLからcodeが取得できませんでした: {redirected_url}")
        flow.fetch_token(code=code)
        creds = flow.credentials
    if not env_token:
        TOKEN_PATH.write_text(creds.to_json())
        print("トークンを保存しました。", file=sys.stderr)
    return creds


def find_or_create_list(service, name, dry_run):
    token = None
    while True:
        res = service.tasklists().list(maxResults=100, pageToken=token).execute()
        for tl in res.get("items", []):
            if tl.get("title") == name:
                return tl["id"]
        token = res.get("nextPageToken")
        if not token:
            break
    if dry_run:
        return None
    return service.tasklists().insert(body={"title": name}).execute()["id"]


def fetch_tasks(service, list_id):
    items, token = [], None
    while list_id:
        res = service.tasks().list(tasklist=list_id, maxResults=100, pageToken=token,
                                   showCompleted=True, showHidden=True, showDeleted=False).execute()
        items += res.get("items", [])
        token = res.get("nextPageToken")
        if not token:
            break
    return items


def main():
    ap = argparse.ArgumentParser(description="やることボード ⇔ Google Tasks 同期")
    ap.add_argument("tasks", help="書き出したディレクトリ、または tasks.json")
    ap.add_argument("client_secret")
    ap.add_argument("--list", default=DEFAULT_LIST)
    ap.add_argument("--redirected-url")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from googleapiclient.discovery import build

    path = Path(args.tasks)
    local = load_local(path)
    service = build("tasks", "v1", credentials=get_credentials(args.client_secret, args.redirected_url))
    list_id = find_or_create_list(service, args.list, args.dry_run)
    remote = fetch_tasks(service, list_id)

    now = datetime.now(timezone.utc)
    out, g_ops, b_ops = merge(local, remote, now)

    if not args.dry_run:
        by_id = {t["id"]: t for t in out}
        for op in g_ops:
            body = {k: v for k, v in op["body"].items() if v is not None}
            if op["op"] == "insert":
                created = service.tasks().insert(tasklist=list_id, body=body).execute()
                t = by_id[op["localId"]]
                t["gtaskId"] = created["id"]
                b_ops.append({"op": "update", "id": t["id"], "data": {"gtaskId": created["id"]}})
            else:
                if op["body"].get("due", "") is None:
                    body["due"] = None  # 期限の削除を明示的に送る
                service.tasks().patch(tasklist=list_id, task=op["gid"], body=body).execute()
        if not path.is_dir():
            path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "dryRun": args.dry_run,
        "google": {"insert": sum(o["op"] == "insert" for o in g_ops), "patch": sum(o["op"] == "patch" for o in g_ops)},
        "boardOps": b_ops,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
