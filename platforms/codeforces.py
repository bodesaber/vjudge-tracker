import urllib.request
import json
from .base import BaseJudgeAdapter

class CodeforcesAdapter(BaseJudgeAdapter):
    def __init__(self):
        super().__init__("Codeforces")

    def fetch_profile(self, handle):
        if not handle:
            return {}
        url = f"https://codeforces.com/api/user.info?handles={handle}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "OK" and data.get("result"):
                    u = data["result"][0]
                    last_online_sec = u.get("lastOnlineTimeSeconds", 0)
                    return {
                        "handle": u.get("handle", handle),
                        "rating": u.get("rating", 0),
                        "maxRating": u.get("maxRating", 0),
                        "rank": u.get("rank", "unrated"),
                        "lastOnlineTimeMs": last_online_sec * 1000 if last_online_sec else 0,
                        "avatar": u.get("titlePhoto", u.get("avatar", ""))
                    }
        except Exception as e:
            print(f"[-] Codeforces profile error for {handle}: {e}")
        return {"handle": handle, "rating": 0, "maxRating": 0, "rank": "unrated", "lastOnlineTimeMs": 0, "avatar": ""}

    def fetch_submissions(self, handle, limit=500):
        if not handle:
            return []
        url = f"https://codeforces.com/api/user.status?handle={handle}&from=1&count={limit}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "OK":
                    raw = data.get("result", [])
                    unified = []
                    for s in raw:
                        prob = s.get("problem", {})
                        cid = prob.get("contestId", "")
                        idx = prob.get("index", "")
                        prob_code = f"{cid}{idx}"
                        prob_name = prob.get("name", prob_code)
                        verdict = s.get("verdict", "UNKNOWN")
                        is_ac = (verdict == "OK")
                        status_str = "Accepted" if is_ac else verdict.replace("_", " ").title()
                        unified.append({
                            "id": f"cf_{s.get('id', s.get('creationTimeSeconds', 0))}",
                            "type": "submission",
                            "platform": "Codeforces",
                            "remote_oj": "CodeForces",
                            "time": s.get("creationTimeSeconds", 0) * 1000,
                            "probNum": prob_code,
                            "problemName": f"{prob_code} - {prob_name}",
                            "problemUrl": f"https://codeforces.com/contest/{cid}/problem/{idx}" if cid else f"https://codeforces.com/problemset/problem/{cid}/{idx}",
                            "status": status_str,
                            "is_ac": is_ac,
                            "difficulty": prob.get("rating", 0) or 0,
                            "tags": prob.get("tags", []),
                            "language": s.get("programmingLanguage", ""),
                            "avatarUrl": ""
                        })
                    return unified
        except Exception as e:
            print(f"[-] Codeforces submissions error for {handle}: {e}")
        return []
