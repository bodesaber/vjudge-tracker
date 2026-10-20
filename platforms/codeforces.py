import urllib.request
import json
import datetime
from .base import BaseJudgeAdapter

class CodeforcesAdapter(BaseJudgeAdapter):
    def __init__(self):
        super().__init__("Codeforces")

    def fetch_profile(self, handle):
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
                    avatar = u.get("titlePhoto", "")
                    return {
                        "rating": u.get("rating", 0),
                        "rank": u.get("rank", "unrated"),
                        "avatar": avatar
                    }
        except Exception as e:
            print(f"[-] Codeforces profile error for {handle}: {e}")
        return {"rating": 0, "rank": "unrated", "avatar": ""}

    def fetch_submissions(self, handle, limit=100):
        url = f"https://codeforces.com/api/user.status?handle={handle}&from=1&count={limit}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "OK":
                    raw = data.get("result", [])
                    unified = []
                    for s in raw:
                        prob = s.get("problem", {})
                        prob_code = f"{prob.get('contestId', '')}{prob.get('index', '')}"
                        verdict = s.get("verdict", "UNKNOWN")
                        is_ac = (verdict == "OK")
                        unified.append({
                            "time": s.get("creationTimeSeconds", 0) * 1000,
                            "oj": "Codeforces",
                            "probNum": prob_code,
                            "problemName": f"CF {prob_code}: {prob.get('name', '')}",
                            "status": "Accepted" if is_ac else verdict.replace("_", " ").title(),
                            "is_ac": is_ac,
                            "language": s.get("programmingLanguage", ""),
                            "avatarUrl": ""
                        })
                    return unified
        except Exception as e:
            print(f"[-] Codeforces submissions error for {handle}: {e}")
        return []
