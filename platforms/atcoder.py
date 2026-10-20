import urllib.request
import json
from .base import BaseJudgeAdapter

class AtCoderAdapter(BaseJudgeAdapter):
    def __init__(self):
        super().__init__("AtCoder")

    def fetch_profile(self, handle):
        if not handle:
            return {}
        return {
            "handle": handle,
            "avatar": ""
        }

    def fetch_submissions(self, handle, limit=500):
        if not handle:
            return []
        url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={handle}&from_second=0"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                if isinstance(raw, list):
                    raw.sort(key=lambda x: x.get("epoch_second", 0), reverse=True)
                    unified = []
                    for s in raw[:limit]:
                        res = s.get("result", "Unknown")
                        is_ac = (res == "AC")
                        cid = s.get("contest_id", "")
                        pid = s.get("problem_id", "")
                        unified.append({
                            "id": f"ac_{s.get('id', s.get('epoch_second', 0))}",
                            "type": "submission",
                            "platform": "AtCoder",
                            "remote_oj": "AtCoder",
                            "time": s.get("epoch_second", 0) * 1000,
                            "probNum": pid,
                            "problemName": f"{pid} ({cid})",
                            "problemUrl": f"https://atcoder.jp/contests/{cid}/tasks/{pid}" if cid else f"https://atcoder.jp/users/{handle}",
                            "status": "Accepted" if is_ac else res,
                            "is_ac": is_ac,
                            "language": s.get("language", ""),
                            "avatarUrl": ""
                        })
                    return unified
        except Exception as e:
            print(f"[-] AtCoder submissions error for {handle}: {e}")
        return []

