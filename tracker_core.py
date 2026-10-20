import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.error
import re
import csv
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from platforms import get_adapter

CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
PINGS_FILE = os.path.join(SCRIPT_DIR, "pings_history.json")
DATA_JSON_FILE = os.path.join(SCRIPT_DIR, "data.json")
HTML_FILE = os.path.join(SCRIPT_DIR, "activity_dashboard.html")
INDEX_FILE = os.path.join(SCRIPT_DIR, "index.html")
CSV_FILE = os.path.join(SCRIPT_DIR, "sessions_report.csv")
MD_FILE = os.path.join(SCRIPT_DIR, "summary_report.md")

CAIRO_TZ = datetime.timezone(datetime.timedelta(hours=3))

ARABIC_DAYS = {
    "Monday": "الإثنين",
    "Tuesday": "الثلاثاء",
    "Wednesday": "الأربعاء",
    "Thursday": "الخميس",
    "Friday": "الجمعة",
    "Saturday": "السبت",
    "Sunday": "الأحد"
}

ARABIC_MONTHS = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو",
    7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
}

def get_cairo_now():
    return datetime.datetime.now(CAIRO_TZ)

def to_cairo_dt(timestamp_ms):
    return datetime.datetime.fromtimestamp(timestamp_ms / 1000, tz=CAIRO_TZ)

def format_arabic_datetime(dt):
    day_name = ARABIC_DAYS.get(dt.strftime("%A"), dt.strftime("%A"))
    month_name = ARABIC_MONTHS.get(dt.month, str(dt.month))
    return f"{day_name} {dt.day} {month_name} {dt.year}"

def format_arabic_time(dt, include_seconds=False):
    hour = dt.hour
    minute = dt.minute
    second = dt.second
    period = "م" if hour >= 12 else "ص"
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    if include_seconds:
        return f"{display_hour:02d}:{minute:02d}:{second:02d} {period}"
    return f"{display_hour:02d}:{minute:02d} {period}"

def format_duration(total_minutes):
    total_minutes = int(round(total_minutes))
    if total_minutes <= 0:
        return "0 دقيقة"
    hours = total_minutes // 60
    mins = total_minutes % 60
    if hours > 0 and mins > 0:
        return f"{hours} س و {mins} د"
    elif hours > 0:
        return f"{hours} ساعة"
    else:
        return f"{mins} دقيقة"

def normalize_trainees_list(raw_trainees):
    normalized = []
    for idx, item in enumerate(raw_trainees):
        if isinstance(item, str):
            h = item.strip()
            if h:
                normalized.append({
                    "id": re.sub(r"[^a-zA-Z0-9_-]", "_", h.lower()),
                    "name": h,
                    "handles": {"vjudge": h, "codeforces": "", "atcoder": "", "cses": ""}
                })
        elif isinstance(item, dict):
            handles = item.get("handles", {})
            if not handles:
                handles = {
                    "vjudge": item.get("vjudge", ""),
                    "codeforces": item.get("codeforces", ""),
                    "atcoder": item.get("atcoder", ""),
                    "cses": item.get("cses", "")
                }
            name = item.get("name") or handles.get("vjudge") or handles.get("codeforces") or f"Trainee {idx+1}"
            pid = item.get("id") or re.sub(r"[^a-zA-Z0-9_-]", "_", name.lower()) or f"user_{idx+1}"
            normalized.append({
                "id": pid,
                "name": name,
                "handles": {
                    "vjudge": (handles.get("vjudge") or "").strip(),
                    "codeforces": (handles.get("codeforces") or "").strip(),
                    "atcoder": (handles.get("atcoder") or "").strip(),
                    "cses": (handles.get("cses") or "").strip()
                }
            })
    return normalized

def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_cfg = {
            "trainees": [
                {
                    "id": "israa",
                    "name": "إسراء عبد الحق (Israa)",
                    "handles": {"vjudge": "Israa_abdelhaq", "codeforces": "Isabella_", "atcoder": "Isabella_", "cses": ""}
                },
                {
                    "id": "omar",
                    "name": "عمر عوض صابر (Omar)",
                    "handles": {"vjudge": "Omar_Awad_Saber", "codeforces": "Lumino", "atcoder": "Lumino", "cses": ""}
                },
                {
                    "id": "fatema",
                    "name": "فاطمة الفقي (Fatema)",
                    "handles": {"vjudge": "Fatemaelfiky1", "codeforces": "Zhraa_", "atcoder": "", "cses": ""}
                },
                {
                    "id": "amr",
                    "name": "عمرو خالد (Amr)",
                    "handles": {"vjudge": "Amr2Khaled", "codeforces": "SHANKS-A", "atcoder": "SHANKS_A", "cses": ""}
                }
            ],
            "session_gap_minutes": 30,
            "coding_buffer_minutes": 15,
            "check_interval_minutes": 5,
            "fetch_limit": 200,
            "timezone_offset_hours": 3,
            "cloud_sync_topic": "vj_tracker_bodesaber_sync_v2"
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_cfg, f, indent=2, ensure_ascii=False)
        return default_cfg

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["trainees"] = normalize_trainees_list(cfg.get("trainees", []))
    return cfg

def sync_profiles_from_cloud(cfg):
    """
    Checks the cloud pub/sub channel (ntfy.sh) for any profile updates
    saved directly by the coach from the Browser UI (on PC or Mobile).
    """
    topic = cfg.get("cloud_sync_topic", "vj_tracker_bodesaber_sync_v2")
    if not topic:
        return cfg
    url = f"https://ntfy.sh/{topic}/json?poll=1&since=24h"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            lines = resp.read().decode("utf-8", errors="ignore").strip().splitlines()
            latest_profiles = None
            latest_ts = cfg.get("last_cloud_sync_ts", 0)
            for line in lines:
                try:
                    msg_obj = json.loads(line)
                    msg_time = msg_obj.get("time", 0)
                    if msg_obj.get("event") == "message" and msg_time > latest_ts:
                        payload = json.loads(msg_obj.get("message", "{}"))
                        if payload.get("action") == "update_profiles" and isinstance(payload.get("trainees"), list):
                            latest_profiles = normalize_trainees_list(payload["trainees"])
                            latest_ts = msg_time
                except Exception:
                    continue
            if latest_profiles is not None:
                print(f"[+] Synced {len(latest_profiles)} trainee profiles from Browser Cloud UI!")
                cfg["trainees"] = latest_profiles
                cfg["last_cloud_sync_ts"] = latest_ts
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[-] Cloud sync check note: {e}")
    return cfg

def load_pings_history():
    if os.path.exists(PINGS_FILE):
        try:
            with open(PINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_pings_history(pings):
    try:
        with open(PINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(pings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[-] Error saving pings history: {e}")

_CF_PROBLEMSET_RATINGS = None
_ATCODER_MODELS_DIFF = None

def get_global_difficulty_maps():
    global _CF_PROBLEMSET_RATINGS, _ATCODER_MODELS_DIFF
    if _CF_PROBLEMSET_RATINGS is None:
        _CF_PROBLEMSET_RATINGS = {}
        try:
            req = urllib.request.Request("https://codeforces.com/api/problemset.problems", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                for p in data.get("result", {}).get("problems", []):
                    if p.get("rating"):
                        code = f"{p.get('contestId', '')}{p.get('index', '')}".upper()
                        _CF_PROBLEMSET_RATINGS[code] = int(p["rating"])
        except Exception as e:
            print(f"[-] Note: CF problemset rating map fetch: {e}")

    if _ATCODER_MODELS_DIFF is None:
        _ATCODER_MODELS_DIFF = {}
        try:
            req = urllib.request.Request("https://kenkoooo.com/atcoder/resources/problem-models.json", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                for k, v in data.items():
                    if isinstance(v, dict) and v.get("difficulty") is not None:
                        _ATCODER_MODELS_DIFF[k.lower()] = float(v["difficulty"])
        except Exception as e:
            print(f"[-] Note: AtCoder problem models fetch: {e}")

    return _CF_PROBLEMSET_RATINGS, _ATCODER_MODELS_DIFF

def rating_to_points_and_tier(rating):
    r = int(rating or 1000)
    if r <= 850:
        return 80, "🟢 سهل"
    elif r <= 950:
        return 100, "🟢 سهل"
    elif r <= 1050:
        return 130, "🔵 فوق المبتدئ"
    elif r <= 1150:
        return 160, "🔵 فوق المبتدئ"
    elif r <= 1250:
        return 195, "🟣 متوسط"
    elif r <= 1350:
        return 235, "🟣 متوسط"
    elif r <= 1450:
        return 280, "🟠 فوق المتوسط"
    elif r <= 1550:
        return 335, "🟠 فوق المتوسط"
    elif r <= 1650:
        return 400, "🔴 صعب"
    elif r <= 1750:
        return 470, "🔴 صعب"
    elif r <= 1850:
        return 550, "🔴 صعب"
    elif r <= 1950:
        return 640, "🔥 صعب جداً"
    elif r <= 2050:
        return 740, "🔥 صعب جداً"
    elif r <= 2150:
        return 850, "🔥 صعب جداً"
    else:
        pts = int(960 + max(0, (r - 2200)) * 0.6)
        return pts, "👑 ماستر"

def evaluate_problem_difficulty(ev):
    if ev.get("type") == "online_ping":
        return 0, "", 0

    cf_map, ac_map = get_global_difficulty_maps()
    raw_diff = ev.get("difficulty", 0) or 0
    if raw_diff >= 800:
        pts, tier = rating_to_points_and_tier(raw_diff)
        return int(raw_diff), tier, pts

    plat = (ev.get("platform") or "").strip()
    remote_oj = (ev.get("remote_oj") or plat).strip()
    prob_num = (ev.get("probNum") or "").strip()
    prob_upper = prob_num.upper()

    rating = 0
    if remote_oj.lower() in ("codeforces", "gym") or plat.lower() == "codeforces":
        if prob_upper in cf_map:
            rating = cf_map[prob_upper]
        else:
            m = re.match(r"^(\d+)([A-Z])", prob_upper)
            if m:
                cid_str, letter = m.group(1), m.group(2)
                is_gym = len(cid_str) >= 6 or remote_oj.lower() == "gym"
                idx_ord = max(0, ord(letter) - ord("A"))
                if is_gym:
                    rating = min(2300, 1200 + idx_ord * 200)
                else:
                    rating = min(2500, 850 + idx_ord * 280)
            else:
                rating = 1200
    elif remote_oj.lower() == "atcoder" or plat.lower() == "atcoder":
        p_low = prob_num.lower()
        if p_low in ac_map:
            d_val = ac_map[p_low]
            rating = max(800, int(round((d_val + 600) / 100.0) * 100))
        elif p_low.startswith("dp_"):
            letter = p_low.split("_")[-1][:1]
            idx_ord = max(0, ord(letter) - ord("a")) if letter.isalpha() else 3
            rating = min(2400, 1100 + idx_ord * 60)
        else:
            letter = p_low.split("_")[-1][:1]
            idx_map = {"a": 800, "b": 950, "c": 1200, "d": 1450, "e": 1750, "f": 2000, "g": 2250, "h": 2400}
            rating = idx_map.get(letter, 1200)
    elif remote_oj.lower() in ("lightoj", "spoj", "toph"):
        rating = 1500
    elif remote_oj.lower() == "cses" or plat.lower() == "cses":
        rating = 1400
    elif remote_oj.lower() in ("uva", "dmoj", "kattis", "ural", "POJ"):
        rating = 1350
    else:
        rating = 1200

    pts, tier = rating_to_points_and_tier(rating)
    return int(rating), tier, pts

def cluster_events_into_sessions(events, max_gap_minutes=30, coding_buffer=15):
    """
    Clusters activity events (submissions + online presence pings) using the 30-minute rule:
    - Each submission at time T represents active engagement from (T - coding_buffer) to T.
    - Each online presence ping at time T represents active platform presence from (T - 5 mins) to T.
    - If the gap between consecutive events is <= max_gap_minutes (30 mins), the trainee was
      continuously active/connected. If > 30 mins, the session ends and a new one begins.
    """
    if not events:
        return []

    sorted_events = sorted(events, key=lambda x: x["time"])
    raw_sessions = []
    cur_group = [sorted_events[0]]

    for ev in sorted_events[1:]:
        prev_ev = cur_group[-1]
        gap_min = (ev["time"] - prev_ev["time"]) / (1000 * 60)
        if gap_min <= max_gap_minutes:
            cur_group.append(ev)
        else:
            raw_sessions.append(cur_group)
            cur_group = [ev]
    if cur_group:
        raw_sessions.append(cur_group)

    processed_sessions = []
    for s_events in raw_sessions:
        first_ev = s_events[0]
        last_ev = s_events[-1]

        # Determine initial buffer before the first recorded timestamp in the session
        first_buffer_mins = 5 if first_ev.get("type") == "online_ping" else coding_buffer
        start_ms = first_ev["time"] - (first_buffer_mins * 60 * 1000)
        end_ms = last_ev["time"]

        start_dt = to_cairo_dt(start_ms)
        end_dt = to_cairo_dt(end_ms)
        duration_minutes = max(int(round((end_ms - start_ms) / 60000)), 5)

        # Calculate per-platform breakdown inside this session
        plat_stats = {}
        for p_name in ["VJudge", "Codeforces", "AtCoder", "CSES"]:
            p_evs = [e for e in s_events if e.get("platform") == p_name or (p_name in e.get("platforms_involved", []))]
            if p_evs:
                p_first = p_evs[0]
                p_last = p_evs[-1]
                p_buf = 5 if p_first.get("type") == "online_ping" else coding_buffer
                p_start_ms = p_first["time"] - (p_buf * 60 * 1000)
                p_end_ms = p_last["time"]
                p_dur = min(max(int(round((p_end_ms - p_start_ms) / 60000)), 5), duration_minutes)
                p_subs = [e for e in p_evs if e.get("type") == "submission"]
                p_ac = sum(1 for e in p_subs if e.get("is_ac"))
                p_pings = sum(1 for e in p_evs if e.get("type") == "online_ping")
                plat_stats[p_name] = {
                    "duration_minutes": p_dur,
                    "duration_str": format_duration(p_dur),
                    "subs_count": len(p_subs),
                    "ac_count": p_ac,
                    "pings_count": p_pings
                }

        sub_events = [e for e in s_events if e.get("type") == "submission"]
        ping_events = [e for e in s_events if e.get("type") == "online_ping"]
        ac_count = sum(1 for e in sub_events if e.get("is_ac"))
        probs = list(dict.fromkeys(e.get("probNum", "—") for e in sub_events))

        if len(sub_events) == 0 and len(ping_events) > 0:
            dur_display = f"{format_duration(duration_minutes)} (فتح وتصفح المنصة)"
        else:
            dur_display = f"{format_duration(duration_minutes)} (اتصال متواصل)"

        # Format timeline items (newest first inside session or chronological)
        timeline = []
        unique_session_ac_pts = {}
        for e in sorted(s_events, key=lambda x: x["time"], reverse=True):
            ev_dt = to_cairo_dt(e["time"])
            diff_val, diff_tier, prob_pts = evaluate_problem_difficulty(e)
            if e.get("type") == "submission" and e.get("is_ac"):
                pkey = f"{e.get('remote_oj', e.get('platform', ''))}_{e.get('probNum', '')}"
                unique_session_ac_pts[pkey] = max(unique_session_ac_pts.get(pkey, 0), prob_pts)
            timeline.append({
                "time": e["time"],
                "time_str": format_arabic_time(ev_dt, include_seconds=True),
                "platform": e.get("platform", ""),
                "type": e.get("type", "submission"),
                "probNum": e.get("probNum", ""),
                "problemName": e.get("problemName", ""),
                "problemUrl": e.get("problemUrl", "#"),
                "status": e.get("status", ""),
                "is_ac": e.get("is_ac", False),
                "difficulty": diff_val,
                "diff_tier": diff_tier,
                "prob_points": prob_pts
            })

        session_prob_pts = sum(unique_session_ac_pts.values())
        session_score = int(round(session_prob_pts + (duration_minutes * 1) + (len(sub_events) * 5) + 15))
        processed_sessions.append({
            "date_iso": start_dt.strftime("%Y-%m-%d"),
            "month_iso": start_dt.strftime("%Y-%m"),
            "date_str": format_arabic_datetime(start_dt),
            "start_str": format_arabic_time(start_dt),
            "end_str": format_arabic_time(end_dt),
            "start_dt": start_dt,
            "end_dt": end_dt,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_minutes": duration_minutes,
            "duration_str": dur_display,
            "submissions_count": len(sub_events),
            "accepted_count": ac_count,
            "pings_count": len(ping_events),
            "problem_points": session_prob_pts,
            "score": session_score,
            "problems": probs,
            "platform_breakdown": plat_stats,
            "timeline": timeline
        })

    processed_sessions.sort(key=lambda x: x["end_ms"], reverse=True)
    return processed_sessions

def analyze_trainee_profile(profile, pings_history, session_gap_min=30, coding_buffer=15, fetch_limit=200):
    pid = profile["id"]
    display_name = profile["name"]
    handles = profile["handles"]

    vj_handle = handles.get("vjudge", "")
    cf_handle = handles.get("codeforces", "")
    ac_handle = handles.get("atcoder", "")
    cses_handle = handles.get("cses", "")

    now = get_cairo_now()
    now_ms = int(now.timestamp() * 1000)
    today_start = datetime.datetime(now.year, now.month, now.day, tzinfo=CAIRO_TZ)
    today_start_ms = int(today_start.timestamp() * 1000)
    week_start_ms = int((now - datetime.timedelta(days=7)).timestamp() * 1000)
    month_start_ms = int((now - datetime.timedelta(days=30)).timestamp() * 1000)

    if pid not in pings_history:
        pings_history[pid] = []

    platform_events = {
        "VJudge": [],
        "Codeforces": [],
        "AtCoder": [],
        "CSES": []
    }
    platform_profiles = {}
    avatar = ""

    # 1. Fetch VJudge
    vj_subs = []
    if vj_handle:
        vj_adapter = get_adapter("vjudge")
        vj_prof = vj_adapter.fetch_profile(vj_handle)
        vj_subs = vj_adapter.fetch_submissions(vj_handle, limit=fetch_limit)
        for s in vj_subs:
            if not avatar and s.get("avatarUrl"):
                avatar = s["avatarUrl"]
        platform_events["VJudge"].extend(vj_subs)
        platform_profiles["VJudge"] = {
            "handle": vj_handle,
            "url": f"https://vjudge.net/user/{vj_handle}",
            "acAll": vj_prof.get("acAll", 0),
            "attAll": vj_prof.get("attAll", 0),
            "ac1d": vj_prof.get("ac1d", 0),
            "ac7d": vj_prof.get("ac7d", 0),
            "ac30d": vj_prof.get("ac30d", 0),
            "extra": ""
        }
        # Auto-discover CF handle if not set
        if not cf_handle and vj_subs:
            discovered = vj_adapter.auto_discover_cf_handle(vj_handle, vj_subs)
            if discovered:
                print(f"    [+] Auto-discovered Codeforces handle for {display_name}: {discovered}")
                cf_handle = discovered
                handles["codeforces"] = discovered

    # 2. Fetch Codeforces
    cf_subs = []
    if cf_handle:
        cf_adapter = get_adapter("codeforces")
        cf_prof = cf_adapter.fetch_profile(cf_handle)
        resolved_cf = cf_prof.get("handle", cf_handle)
        if not avatar and cf_prof.get("avatar"):
            avatar = cf_prof["avatar"]
        cf_subs = cf_adapter.fetch_submissions(resolved_cf, limit=fetch_limit)

        # Record Codeforces lastOnlineTimeMs in pings_history!
        last_online_ms = cf_prof.get("lastOnlineTimeMs", 0)
        if last_online_ms > 0:
            # Check if there is already a submission within 2 minutes of last_online_ms
            has_near_sub = any(abs(s["time"] - last_online_ms) <= 120000 for s in cf_subs)
            existing_pings = pings_history[pid]
            if not any(abs(p.get("time", 0) - last_online_ms) < 60000 for p in existing_pings):
                existing_pings.append({
                    "id": f"ping_cf_{last_online_ms}",
                    "type": "online_ping",
                    "platform": "Codeforces",
                    "time": last_online_ms,
                    "probNum": "تصفح المنصة",
                    "problemName": "👁️ فاتح كود فورسز (متصل أونلاين)",
                    "problemUrl": f"https://codeforces.com/profile/{resolved_cf}",
                    "status": "Online",
                    "is_ac": False
                })
                # Keep last 200 pings
                pings_history[pid] = sorted(existing_pings, key=lambda x: x["time"])[-200:]

        # Add CF submissions + CF online pings
        platform_events["Codeforces"].extend(cf_subs)
        for p in pings_history[pid]:
            if p.get("platform") == "Codeforces":
                # Only include ping if not overlapping with an exact submission within 2 mins
                if not any(abs(s["time"] - p["time"]) <= 120000 for s in cf_subs):
                    platform_events["Codeforces"].append(p)

        cf_ac_all = len(set(s["probNum"] for s in cf_subs if s.get("is_ac")))
        cf_ac_1d = len(set(s["probNum"] for s in cf_subs if s.get("is_ac") and s["time"] >= today_start_ms))
        cf_ac_7d = len(set(s["probNum"] for s in cf_subs if s.get("is_ac") and s["time"] >= week_start_ms))
        cf_ac_30d = len(set(s["probNum"] for s in cf_subs if s.get("is_ac") and s["time"] >= month_start_ms))
        rating_str = f"Rating: {cf_prof.get('rating', 0)} ({cf_prof.get('rank', 'unrated')})" if cf_prof.get("rating") else "Unrated"

        platform_profiles["Codeforces"] = {
            "handle": resolved_cf,
            "url": f"https://codeforces.com/profile/{resolved_cf}",
            "acAll": cf_ac_all,
            "attAll": len(cf_subs),
            "ac1d": cf_ac_1d,
            "ac7d": cf_ac_7d,
            "ac30d": cf_ac_30d,
            "lastOnlineMs": last_online_ms,
            "extra": rating_str
        }

    # 3. Fetch AtCoder
    ac_subs = []
    if ac_handle:
        ac_adapter = get_adapter("atcoder")
        ac_subs = ac_adapter.fetch_submissions(ac_handle, limit=fetch_limit)
        platform_events["AtCoder"].extend(ac_subs)
        ac_all = len(set(s["probNum"] for s in ac_subs if s.get("is_ac")))
        ac_1d = len(set(s["probNum"] for s in ac_subs if s.get("is_ac") and s["time"] >= today_start_ms))
        ac_7d = len(set(s["probNum"] for s in ac_subs if s.get("is_ac") and s["time"] >= week_start_ms))
        ac_30d = len(set(s["probNum"] for s in ac_subs if s.get("is_ac") and s["time"] >= month_start_ms))
        platform_profiles["AtCoder"] = {
            "handle": ac_handle,
            "url": f"https://atcoder.jp/users/{ac_handle}",
            "acAll": ac_all,
            "attAll": len(ac_subs),
            "ac1d": ac_1d,
            "ac7d": ac_7d,
            "ac30d": ac_30d,
            "extra": ""
        }

    # 4. Fetch CSES
    if cses_handle:
        cses_adapter = get_adapter("cses")
        cses_prof = cses_adapter.fetch_profile(cses_handle)
        cses_subs = cses_adapter.fetch_submissions(cses_handle)
        platform_events["CSES"].extend(cses_subs)
        platform_profiles["CSES"] = {
            "handle": cses_prof.get("handle", cses_handle),
            "url": f"https://cses.fi/user/{cses_prof.get('handle', cses_handle)}",
            "acAll": cses_prof.get("attAll", 0),
            "attAll": cses_prof.get("attAll", 0),
            "ac1d": 0,
            "ac7d": 0,
            "ac30d": 0,
            "extra": f"User: {cses_prof.get('username', '')}"
        }

    # 5. Compute Per-Platform Sessions & Active Times
    per_platform_summary = {}
    for p_name, p_prof in platform_profiles.items():
        p_evs = platform_events.get(p_name, [])
        p_sessions = cluster_events_into_sessions(p_evs, max_gap_minutes=session_gap_min, coding_buffer=coding_buffer)

        def calc_plat_period(thresh_ms):
            s_in = [s for s in p_sessions if s["end_ms"] >= thresh_ms]
            evs_in = [e for e in p_evs if e["time"] >= thresh_ms and e.get("type") == "submission"]
            ac_in = len(set(e["probNum"] for e in evs_in if e.get("is_ac")))
            mins = sum(s["duration_minutes"] for s in s_in)
            return {
                "time_minutes": mins,
                "time_str": format_duration(mins),
                "sessions_count": len(s_in),
                "subs_count": len(evs_in),
                "ac_count": ac_in
            }

        p_today = calc_plat_period(today_start_ms)
        p_week = calc_plat_period(week_start_ms)
        p_month = calc_plat_period(month_start_ms)

        # Latest activity on this platform
        last_ms = max([e["time"] for e in p_evs], default=0)
        if p_name == "Codeforces" and p_prof.get("lastOnlineMs", 0) > last_ms:
            last_ms = p_prof["lastOnlineMs"]

        is_plat_online = (last_ms > 0 and (now_ms - last_ms) <= session_gap_min * 60 * 1000)
        if last_ms > 0:
            diff_sec = max(0, (now_ms - last_ms) // 1000)
            if diff_sec < 60:
                p_last_str = "متصل الآن"
            elif diff_sec < 3600:
                p_last_str = f"منذ {int(diff_sec // 60)} د"
            elif diff_sec < 86400:
                p_last_str = f"منذ {int(diff_sec // 3600)} س"
            else:
                p_last_str = f"منذ {int(diff_sec // 86400)} يوم"
        else:
            p_last_str = "لا يوجد نشاط"

        per_platform_summary[p_name] = {
            "platform": p_name,
            "handle": p_prof["handle"],
            "url": p_prof["url"],
            "extra": p_prof.get("extra", ""),
            "is_online": is_plat_online,
            "last_seen_str": p_last_str,
            "last_seen_ms": last_ms,
            "acAll": max(p_prof.get("acAll", 0), p_month["ac_count"]),
            "attAll": p_prof.get("attAll", 0),
            "today": {
                "solved": max(p_prof.get("ac1d", 0), p_today["ac_count"]),
                "subs": p_today["subs_count"],
                "time_str": p_today["time_str"],
                "time_minutes": p_today["time_minutes"]
            },
            "week": {
                "solved": max(p_prof.get("ac7d", 0), p_week["ac_count"]),
                "subs": p_week["subs_count"],
                "time_str": p_week["time_str"],
                "time_minutes": p_week["time_minutes"]
            },
            "month": {
                "solved": max(p_prof.get("ac30d", 0), p_month["ac_count"]),
                "subs": p_month["subs_count"],
                "time_str": p_month["time_str"],
                "time_minutes": p_month["time_minutes"]
            }
        }

    # 6. Merge & Deduplicate Events Across Platforms for Unified Sessions
    # If VJudge proxied a submission to CF/AtCoder (same probNum within 90 seconds), merge them!
    unified_events = []
    for s in vj_subs:
        s_copy = dict(s)
        s_copy["platforms_involved"] = ["VJudge"]
        unified_events.append(s_copy)

    for p_name in ["Codeforces", "AtCoder", "CSES"]:
        for ev in platform_events.get(p_name, []):
            if ev.get("type") == "submission":
                # Check if VJudge already has this exact problem within 90 seconds
                dup = None
                for u_ev in unified_events:
                    if (
                        u_ev.get("type") == "submission"
                        and u_ev.get("probNum", "").lower() == ev.get("probNum", "").lower()
                        and abs(u_ev["time"] - ev["time"]) <= 90000
                    ):
                        dup = u_ev
                        break
                if dup:
                    if p_name not in dup["platforms_involved"]:
                        dup["platforms_involved"].append(p_name)
                else:
                    ev_copy = dict(ev)
                    ev_copy["platforms_involved"] = [p_name]
                    unified_events.append(ev_copy)
            else:
                ev_copy = dict(ev)
                ev_copy["platforms_involved"] = [p_name]
                unified_events.append(ev_copy)

    unified_sessions = cluster_events_into_sessions(unified_events, max_gap_minutes=session_gap_min, coding_buffer=coding_buffer)

    # 7. Overall Trainee Status & Combined Metrics
    latest_ms = max([p["last_seen_ms"] for p in per_platform_summary.values()], default=0)
    is_active_now = any(p["is_online"] for p in per_platform_summary.values())
    active_platforms_now = [p_name for p_name, p in per_platform_summary.items() if p["is_online"]]

    if latest_ms > 0:
        last_dt = to_cairo_dt(latest_ms)
        diff_sec = max(0, (now_ms - latest_ms) // 1000)
        if diff_sec < 60:
            last_seen_str = "متصل الآن (منذ لحظات)"
        elif diff_sec < 3600:
            last_seen_str = f"منذ {int(diff_sec // 60)} دقيقة ({format_arabic_time(last_dt)})"
        elif diff_sec < 86400:
            last_seen_str = f"منذ {int(diff_sec // 3600)} ساعة ({format_arabic_time(last_dt)})"
        else:
            last_seen_str = f"منذ {int(diff_sec // 86400)} يوم ({last_dt.strftime('%d-%m-%Y %I:%M %p')})"
    else:
        last_seen_str = "لا توجد بيانات"

    # Latest event description
    if unified_events:
        latest_ev = max(unified_events, key=lambda x: x["time"])
        last_problem_str = f"[{latest_ev['platform']}] {latest_ev['problemName']} ({latest_ev['status']})"
    else:
        last_problem_str = "—"

    def calc_unified_period(thresh_ms, period_key):
        s_in = [s for s in unified_sessions if s["end_ms"] >= thresh_ms]
        evs_in = [e for e in unified_events if e["time"] >= thresh_ms and e.get("type") == "submission"]
        ac_map_period = {}
        for e in evs_in:
            if e.get("is_ac"):
                pkey = f"{e.get('remote_oj', e.get('platform', ''))}_{e.get('probNum', '')}"
                diff_v, diff_t, p_pts = evaluate_problem_difficulty(e)
                if pkey not in ac_map_period or p_pts > ac_map_period[pkey]["pts"]:
                    ac_map_period[pkey] = {
                        "pts": p_pts,
                        "diff": diff_v,
                        "tier": diff_t,
                        "name": e.get("problemName", e.get("probNum", ""))
                    }
        unique_ac = len(ac_map_period)
        max_plat_ac = max([p[period_key]["solved"] for p in per_platform_summary.values()], default=0)
        solved_count = max(unique_ac, max_plat_ac)

        avg_diff = int(round(sum(x["diff"] for x in ac_map_period.values()) / unique_ac)) if unique_ac > 0 else 0
        max_diff = max([x["diff"] for x in ac_map_period.values()], default=0)
        hardest_obj = max(ac_map_period.values(), key=lambda x: x["diff"]) if ac_map_period else None
        hardest_str = f"{hardest_obj['name']} ({hardest_obj['diff']})" if hardest_obj else "—"

        recorded_prob_pts = sum(x["pts"] for x in ac_map_period.values())
        avg_pts_per_prob = (recorded_prob_pts / unique_ac) if unique_ac > 0 else 120
        extra_unseen_ac = max(0, solved_count - unique_ac)
        total_prob_pts = int(round(recorded_prob_pts + extra_unseen_ac * avg_pts_per_prob))

        total_mins = sum(s["duration_minutes"] for s in s_in)
        subs_count = len(evs_in)
        sess_count = len(s_in)
        score = int(round(total_prob_pts + (total_mins * 1) + (subs_count * 5) + (sess_count * 15)))
        return {
            "solved": solved_count,
            "subs": subs_count,
            "time_minutes": total_mins,
            "time_str": format_duration(total_mins),
            "sessions": sess_count,
            "problem_points": total_prob_pts,
            "avg_difficulty": avg_diff,
            "max_difficulty": max_diff,
            "hardest_problem": hardest_str,
            "score": score
        }

    comb_today = calc_unified_period(today_start_ms, "today")
    comb_week = calc_unified_period(week_start_ms, "week")
    comb_month = calc_unified_period(month_start_ms, "month")

    # Total all-time solved across platforms
    total_all_time_ac = sum(p["acAll"] for p in per_platform_summary.values())
    if "VJudge" in per_platform_summary and "Codeforces" in per_platform_summary:
        # Avoid double counting CF problems already included in VJudge acAll
        vj_cf_ac = len(set(s["probNum"] for s in vj_subs if s.get("is_ac") and s.get("remote_oj") == "CodeForces"))
        total_all_time_ac = max(per_platform_summary["VJudge"]["acAll"], total_all_time_ac - vj_cf_ac)

    all_ac_events_info = [evaluate_problem_difficulty(e) for e in unified_events if e.get("type") == "submission" and e.get("is_ac")]
    overall_avg_diff = int(round(sum(x[0] for x in all_ac_events_info) / len(all_ac_events_info))) if all_ac_events_info else 1100
    overall_max_diff = max([x[0] for x in all_ac_events_info], default=0)
    overall_avg_pts = (sum(x[2] for x in all_ac_events_info) / len(all_ac_events_info)) if all_ac_events_info else 130
    total_rec_mins = sum(s["duration_minutes"] for s in unified_sessions)
    total_rec_subs = sum(s["submissions_count"] for s in unified_sessions)
    all_time_score = int(round((total_all_time_ac * overall_avg_pts) + (total_rec_mins * 1) + (total_rec_subs * 5) + (len(unified_sessions) * 15)))

    # Peak hours calculation
    slots = {"فجر / ليل متأخر (12ص-6ص)": 0, "صباحاً (6ص-12ظ)": 0, "ظهراً وعصراً (12ظ-6م)": 0, "مساءً (6م-12ص)": 0}
    hours_count = defaultdict(int)
    for ev in unified_events:
        dt = to_cairo_dt(ev["time"])
        h = dt.hour
        hours_count[h] += 1
        if 0 <= h < 6:
            slots["فجر / ليل متأخر (12ص-6ص)"] += 1
        elif 6 <= h < 12:
            slots["صباحاً (6ص-12ظ)"] += 1
        elif 12 <= h < 18:
            slots["ظهراً وعصراً (12ظ-6م)"] += 1
        else:
            slots["مساءً (6م-12ص)"] += 1

    top_slot = max(slots.items(), key=lambda x: x[1]) if any(slots.values()) else ("غير محدد", 0)
    sorted_hours = sorted(hours_count.items(), key=lambda x: x[1], reverse=True)
    if sorted_hours and sorted_hours[0][1] > 0:
        top_h = sorted_hours[0][0]
        period = "م" if top_h >= 12 else "ص"
        display_h = top_h % 12 or 12
        peak_hours_str = f"الذروة حوالي {display_h:02d}:00 {period} ({top_slot[0]})"
    else:
        peak_hours_str = top_slot[0]

    return {
        "id": pid,
        "name": display_name,
        "handles": handles,
        "avatar": avatar,
        "is_active_now": is_active_now,
        "active_platforms_now": active_platforms_now,
        "last_seen_str": last_seen_str,
        "last_seen_ms": latest_ms,
        "last_problem_str": last_problem_str,
        "all_time_ac": total_all_time_ac,
        "all_time_score": all_time_score,
        "avg_difficulty": overall_avg_diff,
        "max_difficulty": overall_max_diff,
        "today": comb_today,
        "week": comb_week,
        "month": comb_month,
        "peak_hours_str": peak_hours_str,
        "platforms": per_platform_summary,
        "sessions": unified_sessions
    }

