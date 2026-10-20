import urllib.request
import json
import re
from .base import BaseJudgeAdapter

class VJudgeAdapter(BaseJudgeAdapter):
    def __init__(self):
        super().__init__("VJudge")

    def fetch_profile(self, handle):
        url = f"https://vjudge.net/user/{handle}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                m = re.search(r'id=["\']profile-header-data["\']>(.*?)</script>', html)
                if m:
                    data = json.loads(m.group(1))
                    counts = data.get("counts", {})
                    return {
                        "acAll": counts.get("acAll", 0),
                        "attAll": counts.get("attAll", 0),
                        "ac1d": counts.get("ac1d", 0),
                        "ac7d": counts.get("ac7d", 0),
                        "ac30d": counts.get("ac30d", 0),
                        "avatar": f"https://cdn.vjudge.net.cn/user/avatar/{data.get('userId', 'default')}"
                    }
        except Exception as e:
            print(f"[-] VJudge profile error for {handle}: {e}")
        return {"acAll": 0, "attAll": 0, "ac1d": 0, "ac7d": 0, "ac30d": 0, "avatar": ""}

    def fetch_submissions(self, handle, limit=100):
        url = f"https://vjudge.net/status/data?start=0&length={limit}&un={handle}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_subs = data.get("data", [])
                unified = []
                for s in raw_subs:
                    status = s.get("status", "Unknown")
                    unified.append({
                        "time": s.get("time", 0),
                        "oj": s.get("oj", "VJudge"),
                        "probNum": s.get("probNum", "—"),
                        "problemName": f"{s.get('oj', '')} {s.get('probNum', '')}",
                        "status": status,
                        "is_ac": (status == "Accepted"),
                        "language": s.get("language", ""),
                        "avatarUrl": s.get("avatarUrl", "")
                    })
                return unified
        except Exception as e:
            print(f"[-] VJudge submissions error for {handle}: {e}")
            return []
