import urllib.request
import json
import re
from .base import BaseJudgeAdapter

class VJudgeAdapter(BaseJudgeAdapter):
    def __init__(self):
        super().__init__("VJudge")

    def fetch_profile(self, handle):
        if not handle:
            return {}
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
                        "handle": data.get("username", handle),
                        "acAll": counts.get("acAll", 0),
                        "attAll": counts.get("attAll", 0),
                        "ac1d": counts.get("ac1d", 0),
                        "ac7d": counts.get("ac7d", 0),
                        "ac30d": counts.get("ac30d", 0),
                        "avatar": ""
                    }
        except Exception as e:
            print(f"[-] VJudge profile error for {handle}: {e}")
        return {"handle": handle, "acAll": 0, "attAll": 0, "ac1d": 0, "ac7d": 0, "ac30d": 0, "avatar": ""}

    def fetch_submissions(self, handle, limit=100):
        if not handle:
            return []
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
                    oj = s.get("oj", "VJudge")
                    prob_num = s.get("probNum", "—")
                    is_ac = (status == "Accepted")
                    unified.append({
                        "id": f"vj_{s.get('runId', s.get('time', 0))}",
                        "type": "submission",
                        "platform": "VJudge",
                        "remote_oj": oj,
                        "time": s.get("time", 0),
                        "probNum": prob_num,
                        "problemName": f"{oj} {prob_num}",
                        "problemUrl": f"https://vjudge.net/problem/{oj}-{prob_num}",
                        "status": status,
                        "is_ac": is_ac,
                        "language": s.get("language", ""),
                        "avatarUrl": s.get("avatarUrl", "")
                    })
                return unified
        except Exception as e:
            print(f"[-] VJudge submissions error for {handle}: {e}")
            return []

    def auto_discover_cf_handle(self, vjudge_handle, vj_subs=None):
        """
        Attempts to automatically discover a user's bound Codeforces handle
        by matching their VJudge CodeForces submission timestamps against Codeforces contest status.
        """
        if not vjudge_handle:
            return None
        if vj_subs is None:
            vj_subs = self.fetch_submissions(vjudge_handle, limit=30)
        for s in vj_subs[:15]:
            if s.get("remote_oj") == "CodeForces":
                m = re.match(r"^(\d+)([A-Z]\d?)$", s.get("probNum", ""))
                if m:
                    cid, idx = int(m.group(1)), m.group(2)
                    ts = s["time"] // 1000
                    try:
                        cf_url = f"https://codeforces.com/api/contest.status?contestId={cid}&from=1&count=300"
                        req = urllib.request.Request(cf_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=8) as resp:
                            d = json.loads(resp.read().decode("utf-8"))
                            for cs in d.get("result", []):
                                if abs(cs.get("creationTimeSeconds", 0) - ts) < 60 and cs.get("problem", {}).get("index") == idx:
                                    author = cs.get("author", {}).get("members", [{}])[0].get("handle", "")
                                    if author and not author.lower().startswith("vjudge"):
                                        return author
                    except Exception:
                        pass
                    break
        return None
