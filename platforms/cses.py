import urllib.request
import re
import datetime
from .base import BaseJudgeAdapter

class CSESAdapter(BaseJudgeAdapter):
    def __init__(self):
        super().__init__("CSES")

    def fetch_profile(self, handle):
        if not handle:
            return {}
        # Extract numeric ID if URL or string passed
        m_id = re.search(r"(\d+)", str(handle))
        uid = m_id.group(1) if m_id else str(handle).strip()
        url = f"https://cses.fi/user/{uid}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                user_m = re.search(r"<h1>User\s+([^<]+)</h1>", html)
                sub_m = re.search(r"Submission count:</td><td[^>]*>(\d+)</td>", html)
                last_m = re.search(r"Last submission:</td><td[^>]*>([0-9\-:\s]+)</td>", html)
                username = user_m.group(1).strip() if user_m else uid
                sub_count = int(sub_m.group(1)) if sub_m else 0
                last_sub_ms = 0
                if last_m:
                    try:
                        # CSES timestamps are UTC+2/UTC+3 (Finland time, same timezone as Cairo!)
                        dt = datetime.datetime.strptime(last_m.group(1).strip(), "%Y-%m-%d %H:%M:%S")
                        dt = dt.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
                        last_sub_ms = int(dt.timestamp() * 1000)
                    except Exception:
                        pass
                return {
                    "handle": uid,
                    "username": username,
                    "attAll": sub_count,
                    "lastSubmissionMs": last_sub_ms
                }
        except Exception as e:
            print(f"[-] CSES profile error for {handle}: {e}")
        return {"handle": str(handle), "username": str(handle), "attAll": 0, "lastSubmissionMs": 0}

    def fetch_submissions(self, handle, limit=100):
        # CSES only exposes summary timestamps publicly; convert lastSubmissionMs into an activity event
        prof = self.fetch_profile(handle)
        if prof.get("lastSubmissionMs", 0) > 0:
            return [{
                "id": f"cses_{prof['handle']}_{prof['lastSubmissionMs']}",
                "type": "submission",
                "platform": "CSES",
                "remote_oj": "CSES",
                "time": prof["lastSubmissionMs"],
                "probNum": "CSES Problemset",
                "problemName": f"CSES Problemset (Total: {prof.get('attAll', 0)} subs)",
                "problemUrl": f"https://cses.fi/user/{prof['handle']}",
                "status": "Submitted",
                "is_ac": True,
                "language": "C++",
                "avatarUrl": ""
            }]
        return []

