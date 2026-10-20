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
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
HTML_FILE = os.path.join(SCRIPT_DIR, "activity_dashboard.html")
INDEX_FILE = os.path.join(SCRIPT_DIR, "index.html")
CSV_FILE = os.path.join(SCRIPT_DIR, "sessions_report.csv")
MD_FILE = os.path.join(SCRIPT_DIR, "summary_report.md")

# Default timezone: Cairo, Egypt (UTC+3)
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

def format_arabic_time(dt):
    hour = dt.hour
    minute = dt.minute
    period = "م" if hour >= 12 else "ص"
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour:02d}:{minute:02d} {period}"

def format_duration(total_minutes):
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

def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_cfg = {
            "trainees": ["Israa_abdelhaq", "Omar_Awad_Saber", "Fatemaelfiky1", "Amr2Khaled"],
            "session_gap_minutes": 60,
            "check_interval_minutes": 5,
            "fetch_limit": 100,
            "timezone_offset_hours": 3
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_cfg, f, indent=2, ensure_ascii=False)
        return default_cfg
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_official_profile_data(username):
    """
    Fetches the official profile metrics directly from https://vjudge.net/user/{username}
    Extracts acAll (total solved), attAll (total attempted), ac1d, ac7d, ac30d.
    """
    url = f"https://vjudge.net/user/{username}"
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
                return data.get("counts", {})
    except Exception as e:
        print(f"[-] Profile data fetch error for {username}: {e}")
    return {}

def fetch_submissions(username, limit=100):
    url = f"https://vjudge.net/status/data?start=0&length={limit}&un={username}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("data", [])
    except Exception as e:
        print(f"[-] Submissions fetch error for {username}: {e}")
        return []

def cluster_into_sessions(subs, max_gap_minutes=60):
    if not subs:
        return []

    # Sort chronologically ascending
    valid_subs = sorted(subs, key=lambda x: x["time"])

    sessions = []
    current_session = [valid_subs[0]]

    for sub in valid_subs[1:]:
        prev_sub = current_session[-1]
        gap_min = (sub["time"] - prev_sub["time"]) / (1000 * 60)
        if gap_min <= max_gap_minutes:
            current_session.append(sub)
        else:
            sessions.append(current_session)
            current_session = [sub]
    if current_session:
        sessions.append(current_session)

    processed_sessions = []
    for s in sessions:
        start_dt = to_cairo_dt(s[0]["time"])
        end_dt = to_cairo_dt(s[-1]["time"])
        total_seconds = int((end_dt - start_dt).total_seconds())

        is_single = (len(s) == 1 or total_seconds == 0)
        if is_single:
            dur_display = "محاولة فردية (~15 د)"
            dur_minutes = 15
        else:
            dur_minutes = max(total_seconds // 60, 1)
            dur_display = format_duration(dur_minutes)

        probs = list(dict.fromkeys(x.get("probNum", "—") for x in s))
        ac_count = sum(1 for x in s if x.get("status") == "Accepted")

        processed_sessions.append({
            "start_dt": start_dt,
            "end_dt": end_dt,
            "duration_str": dur_display,
            "duration_minutes": dur_minutes,
            "is_single": is_single,
            "submissions_count": len(s),
            "accepted_count": ac_count,
            "problems": probs,
            "raw_subs": s
        })

    # Sort sessions newest first
    processed_sessions.sort(key=lambda x: x["start_dt"], reverse=True)
    return processed_sessions

def analyze_user_comprehensive(username, all_subs, official_counts, max_gap_minutes=60):
    now = get_cairo_now()
    today_start = datetime.datetime(now.year, now.month, now.day, tzinfo=CAIRO_TZ)
    week_start = now - datetime.timedelta(days=7)
    month_start = now - datetime.timedelta(days=30)

    # Official counts fallback
    ac_all_official = official_counts.get("acAll", 0)
    att_all_official = official_counts.get("attAll", 0)
    ac_1d_official = official_counts.get("ac1d", 0)
    ac_7d_official = official_counts.get("ac7d", 0)
    ac_30d_official = official_counts.get("ac30d", 0)

    if not all_subs:
        return {
            "username": username,
            "avatar": "",
            "is_active_now": False,
            "last_seen_str": "لا توجد بيانات",
            "last_problem_str": "—",
            "all_time_ac": ac_all_official,
            "all_time_att": att_all_official,
            "today": {"solved": ac_1d_official, "subs": 0, "time_str": "0 د", "sessions": 0},
            "week": {"solved": ac_7d_official, "subs": 0, "time_str": "0 د", "sessions": 0},
            "month": {"solved": ac_30d_official, "subs": 0, "time_str": "0 د", "sessions": 0},
            "peak_hours_str": "غير محدد",
            "sessions": [],
            "recent_subs": []
        }

    # Latest submission & live status
    latest_sub = max(all_subs, key=lambda x: x["time"])
    last_seen_dt = to_cairo_dt(latest_sub["time"])
    time_since_last = (now - last_seen_dt).total_seconds()

    # Active now if submitted in the last 40 minutes
    is_active_now = (time_since_last <= 40 * 60)

    if time_since_last < 60:
        last_seen_str = "الآن (منذ لحظات)"
    elif time_since_last < 3600:
        last_seen_str = f"منذ {int(time_since_last // 60)} دقيقة"
    elif time_since_last < 86400:
        last_seen_str = f"منذ {int(time_since_last // 3600)} ساعة"
    else:
        days = int(time_since_last // 86400)
        last_seen_str = f"منذ {days} يوم ({last_seen_dt.strftime('%d-%m-%Y')})"

    latest_prob = f"{latest_sub.get('oj', '')} {latest_sub.get('probNum', '')} ({latest_sub.get('status', '')})"

    # Cluster all sessions
    all_sessions = cluster_into_sessions(all_subs, max_gap_minutes=max_gap_minutes)

    # Periodic breakdowns (combining official AC with session time)
    def compute_period_time(dt_threshold):
        period_subs = [s for s in all_subs if to_cairo_dt(s["time"]) >= dt_threshold]
        period_sessions = [s for s in all_sessions if s["start_dt"] >= dt_threshold]
        total_mins = sum(s["duration_minutes"] for s in period_sessions)
        return {
            "subs": len(period_subs),
            "time_str": format_duration(total_mins),
            "total_mins": total_mins,
            "sessions": len(period_sessions)
        }

    today_time = compute_period_time(today_start)
    week_time = compute_period_time(week_start)
    month_time = compute_period_time(month_start)

    today_stats = {
        "solved": ac_1d_official,
        "subs": today_time["subs"],
        "time_str": today_time["time_str"],
        "sessions": today_time["sessions"]
    }
    week_stats = {
        "solved": ac_7d_official,
        "subs": week_time["subs"],
        "time_str": week_time["time_str"],
        "sessions": week_time["sessions"]
    }
    month_stats = {
        "solved": ac_30d_official,
        "subs": month_time["subs"],
        "time_str": month_time["time_str"],
        "sessions": month_time["sessions"]
    }

    # Peak hours / Active time of day
    slots = {"فجر / ليل متأخر (12ص-6ص)": 0, "صباحاً (6ص-12ظ)": 0, "ظهراً وعصراً (12ظ-6م)": 0, "مساءً (6م-12ص)": 0}
    hours_count = defaultdict(int)

    for sub in all_subs:
        dt = to_cairo_dt(sub["time"])
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
        display_h = top_h % 12
        if display_h == 0:
            display_h = 12
        peak_hours_str = f"الذروة حوالي {display_h:02d}:00 {period} ({top_slot[0]})"
    else:
        peak_hours_str = top_slot[0]

    return {
        "username": username,
        "avatar": latest_sub.get("avatarUrl", ""),
        "is_active_now": is_active_now,
        "last_seen_str": last_seen_str,
        "last_seen_dt": last_seen_dt,
        "last_problem_str": latest_prob,
        "all_time_ac": ac_all_official,
        "all_time_att": att_all_official,
        "today": today_stats,
        "week": week_stats,
        "month": month_stats,
        "peak_hours_str": peak_hours_str,
        "sessions": all_sessions
    }

def generate_html_dashboard(users_data):
    now_dt = get_cairo_now()
    now_str = format_arabic_datetime(now_dt) + " - " + format_arabic_time(now_dt) + " (توقيت مصر)"

    cards_html = ""
    for u in users_data:
        badge_class = "badge-online" if u["is_active_now"] else "badge-offline"
        badge_text = "🟢 نشط الآن على VJudge" if u["is_active_now"] else "⚪ غير نشط"
        avatar_src = u["avatar"] if u["avatar"] else "https://cdn.vjudge.net.cn/user/avatar/default.png"

        cards_html += f"""
        <div class="user-card" id="card-{u['username']}">
            <div class="user-header">
                <img src="{avatar_src}" alt="{u['username']}" class="avatar" onerror="this.src='https://cdn.vjudge.net.cn/user/avatar/default.png'">
                <div style="flex: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h3 class="user-title">
                            <a href="https://vjudge.net/user/{u['username']}" target="_blank">{u['username']}</a>
                        </h3>
                        <span class="badge {badge_class}">{badge_text}</span>
                    </div>
                    <div class="alltime-banner">
                        🏆 إجمالي المسائل المحلولة كلياً: <strong>{u['all_time_ac']} مسألة AC</strong> (من {u['all_time_att']} محاولة)
                    </div>
                    <div style="font-size: 0.8rem; color: #64748b; margin-top: 4px;">
                        آخر ظهور: <strong>{u['last_seen_str']}</strong> | <em>{u['last_problem_str']}</em>
                    </div>
                </div>
            </div>

            <!-- Periodic Breakdown Matrix -->
            <div class="period-matrix">
                <div class="matrix-cell">
                    <span class="matrix-title">📅 اليوم</span>
                    <div class="matrix-val text-success">{u['today']['solved']} <span class="matrix-unit">مسائل AC</span></div>
                    <div class="matrix-sub">{u['today']['time_str']} حل ({u['today']['subs']} تقديم)</div>
                </div>
                <div class="matrix-cell">
                    <span class="matrix-title">🗓️ آخر 7 أيام</span>
                    <div class="matrix-val text-primary">{u['week']['solved']} <span class="matrix-unit">مسائل AC</span></div>
                    <div class="matrix-sub">{u['week']['time_str']} حل ({u['week']['sessions']} جلسات)</div>
                </div>
                <div class="matrix-cell">
                    <span class="matrix-title">📊 آخر 30 يوماً</span>
                    <div class="matrix-val text-purple">{u['month']['solved']} <span class="matrix-unit">مسائل AC</span></div>
                    <div class="matrix-sub">{u['month']['time_str']} حل ({u['month']['sessions']} جلسة)</div>
                </div>
            </div>

            <div class="peak-box">
                <span class="peak-icon">⏰</span>
                <div>
                    <strong>فترات النشاط المعتادة:</strong>
                    <div style="font-size: 0.88rem; color: #334155; margin-top: 2px;">{u['peak_hours_str']}</div>
                </div>
            </div>
        </div>
        """

    # Build Sessions Table rows
    table_rows_html = ""
    for u in users_data:
        for s in u["sessions"]:
            day_str = format_arabic_datetime(s["start_dt"])
            start_str = format_arabic_time(s["start_dt"])
            end_str = format_arabic_time(s["end_dt"])
            dur_class = "dur-single" if s["is_single"] else "dur-multi"
            ac_badge = f"<span class='badge badge-ac'>{s['accepted_count']} AC</span>" if s["accepted_count"] > 0 else "<span class='badge badge-wa'>0 AC</span>"
            probs_tags = "".join([f"<span class='prob-tag'>{p}</span>" for p in s["problems"][:6]])

            table_rows_html += f"""
            <tr data-user="{u['username']}">
                <td>
                    <strong><a href="https://vjudge.net/user/{u['username']}" target="_blank" class="user-link">{u['username']}</a></strong>
                </td>
                <td>{day_str}</td>
                <td><span class="time-badge start-time">{start_str}</span></td>
                <td><span class="time-badge end-time">{end_str}</span></td>
                <td><span class="{dur_class}">{s['duration_str']}</span></td>
                <td>{s['submissions_count']}</td>
                <td>{ac_badge}</td>
                <td><div class="prob-list">{probs_tags}</div></td>
            </tr>
            """

    # Filter buttons for Trainees
    user_filters_html = '<button class="filter-btn active" onclick="filterUser(\'all\', this)">الكل</button>'
    for u in users_data:
        uname = u["username"]
        user_filters_html += f'<button class="filter-btn" onclick="filterUser(\'{uname}\', this)">{uname}</button>'

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <!-- Auto-refresh every 5 minutes (300 seconds) -->
    <meta http-equiv="refresh" content="300">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة متابعة نشاط المتدربين على VJudge (تحديث كل 5 دقائق)</title>
    <style>
        :root {{
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --bg: #f1f5f9;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --success: #16a34a;
            --success-bg: #dcfce7;
            --purple: #9333ea;
            --radius: 12px;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        body {{
            background-color: var(--bg);
            color: var(--text-main);
            padding: 20px;
            direction: rtl;
        }}
        .container {{
            max-width: 1300px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #1e293b, #0f172a);
            color: #ffffff;
            padding: 24px 28px;
            border-radius: var(--radius);
            margin-bottom: 24px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.06);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header h1 {{
            font-size: 1.7rem;
            margin-bottom: 4px;
        }}
        .header p {{
            color: #94a3b8;
            font-size: 0.92rem;
        }}
        .cloud-badge {{
            display: inline-block;
            background: #10b981;
            color: white;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: bold;
            margin-right: 8px;
        }}
        .refresh-pill {{
            background: rgba(59, 130, 246, 0.2);
            color: #93c5fd;
            border: 1px solid rgba(59, 130, 246, 0.4);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.78rem;
            display: inline-block;
            margin-right: 6px;
        }}
        .header-actions {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 8px;
        }}
        .last-update {{
            background: rgba(255,255,255,0.1);
            padding: 7px 14px;
            border-radius: 20px;
            font-size: 0.82rem;
            color: #cbd5e1;
        }}
        .btn-reload {{
            background: var(--primary);
            color: white;
            border: none;
            padding: 7px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.82rem;
            font-weight: 600;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .btn-reload:hover {{
            background: var(--primary-dark);
        }}
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 20px;
            margin-bottom: 28px;
        }}
        .user-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.03);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .user-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 14px rgba(0,0,0,0.06);
        }}
        .user-header {{
            display: flex;
            align-items: flex-start;
            gap: 14px;
            margin-bottom: 14px;
        }}
        .avatar {{
            width: 54px;
            height: 54px;
            border-radius: 50%;
            border: 2px solid var(--border);
            object-fit: cover;
        }}
        .user-title {{
            font-size: 1.25rem;
        }}
        .user-title a {{
            color: var(--text-main);
            text-decoration: none;
        }}
        .user-title a:hover {{
            color: var(--primary);
        }}
        .alltime-banner {{
            background: #fef3c7;
            color: #92400e;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.82rem;
            margin-top: 5px;
            display: inline-block;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.78rem;
            font-weight: 600;
        }}
        .badge-online {{
            background: #dcfce7;
            color: #15803d;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.04); }}
            100% {{ transform: scale(1); }}
        }}
        .badge-offline {{
            background: #f1f5f9;
            color: #64748b;
        }}
        .badge-ac {{
            background: #dcfce7;
            color: #166534;
        }}
        .badge-wa {{
            background: #fee2e2;
            color: #991b1b;
        }}
        .period-matrix {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 8px;
            margin-bottom: 14px;
        }}
        .matrix-cell {{
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px 8px;
            text-align: center;
        }}
        .matrix-title {{
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-muted);
            display: block;
            margin-bottom: 3px;
        }}
        .matrix-val {{
            font-size: 1.25rem;
            font-weight: bold;
            line-height: 1.2;
        }}
        .matrix-unit {{
            font-size: 0.72rem;
            font-weight: normal;
        }}
        .matrix-sub {{
            font-size: 0.72rem;
            color: #64748b;
            margin-top: 4px;
        }}
        .text-primary {{ color: var(--primary) !important; }}
        .text-success {{ color: var(--success) !important; }}
        .text-purple {{ color: var(--purple) !important; }}
        .peak-box {{
            background: #eff6ff;
            border: 1px solid #dbeafe;
            border-radius: 8px;
            padding: 10px 14px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .peak-icon {{
            font-size: 1.4rem;
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .section-header h2 {{
            font-size: 1.35rem;
            color: var(--text-main);
        }}
        .filter-buttons {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .filter-btn {{
            background: #ffffff;
            border: 1px solid var(--border);
            padding: 6px 14px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 500;
            transition: all 0.2s;
        }}
        .filter-btn:hover, .filter-btn.active {{
            background: var(--primary);
            color: #ffffff;
            border-color: var(--primary);
        }}
        .table-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            box-shadow: 0 2px 6px rgba(0,0,0,0.03);
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: right;
            font-size: 0.9rem;
        }}
        th {{
            background: #f1f5f9;
            color: #475569;
            padding: 13px 16px;
            font-weight: 600;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}
        td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            color: var(--text-main);
        }}
        tr:hover td {{
            background-color: #f8fafc;
        }}
        .user-link {{
            color: var(--primary);
            text-decoration: none;
        }}
        .time-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.8rem;
        }}
        .start-time {{
            background: #e0f2fe;
            color: #0369a1;
        }}
        .end-time {{
            background: #fef3c7;
            color: #92400e;
        }}
        .dur-multi {{
            font-weight: bold;
            color: #15803d;
        }}
        .dur-single {{
            color: #64748b;
            font-size: 0.82rem;
        }}
        .prob-list {{
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
        }}
        .prob-tag {{
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            color: #334155;
            border: 1px solid #e2e8f0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>
                    📊 لوحة متابعة نشاط المتدربين على VJudge 
                    <span class="cloud-badge">24/7 Cloud</span>
                    <span class="refresh-pill">تحديث كل 5 دقائق</span>
                </h1>
                <p>رصد دقيق لمواعيد فتح وحل المسائل (اليوم - الأسبوع - الشهر) مع توقيت البداية والنهاية</p>
            </div>
            <div class="header-actions">
                <div class="last-update">
                    🕒 آخر تحديث: {now_str}
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span id="countdown" style="font-size: 0.8rem; color: #94a3b8;">التحديث القادم خلال: 05:00</span>
                    <button class="btn-reload" onclick="location.reload();">🔄 تحديث الآن</button>
                </div>
            </div>
        </div>

        <div class="cards-grid">
            {cards_html}
        </div>

        <div class="section-header">
            <h2>سجل جلسات النشاط (من - إلى)</h2>
            <div class="filter-buttons">
                {user_filters_html}
            </div>
        </div>

        <div class="table-card">
            <table>
                <thead>
                    <tr>
                        <th>المتدرب</th>
                        <th>التاريخ</th>
                        <th>بداية الجلسة (من)</th>
                        <th>نهاية الجلسة (إلى)</th>
                        <th>مدة النشاط</th>
                        <th>التقديمات</th>
                        <th>النتيجة</th>
                        <th>المسائل</th>
                    </tr>
                </thead>
                <tbody id="sessionsTableBody">
                    {table_rows_html}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function filterUser(username, btn) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const rows = document.querySelectorAll('#sessionsTableBody tr');
            rows.forEach(r => {{
                if (username === 'all' || r.getAttribute('data-user') === username) {{
                    r.style.display = '';
                }} else {{
                    r.style.display = 'none';
                }}
            }});
        }}

        // 5-minute Countdown Timer
        let secondsLeft = 300;
        const countdownEl = document.getElementById('countdown');
        setInterval(() => {{
            secondsLeft--;
            if (secondsLeft <= 0) {{
                location.reload();
            }} else {{
                const m = Math.floor(secondsLeft / 60);
                const s = secondsLeft % 60;
                countdownEl.innerText = `التحديث القادم خلال: ${{m.toString().padStart(2, '0')}}:${{s.toString().padStart(2, '0')}}`;
            }}
        }}, 1000);
    </script>
</body>
</html>
"""
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

def generate_csv_report(users_data):
    rows = []
    for u in users_data:
        for s in u["sessions"]:
            rows.append({
                "المتدرب": u["username"],
                "إجمالي المسائل الكلي": u["all_time_ac"],
                "اليوم": format_arabic_datetime(s["start_dt"]),
                "بداية الجلسة": format_arabic_time(s["start_dt"]),
                "نهاية الجلسة": format_arabic_time(s["end_dt"]),
                "مدة النشاط": s["duration_str"],
                "عدد التقديمات": s["submissions_count"],
                "المقبول": s["accepted_count"],
                "المسائل": ", ".join(s["problems"][:8])
            })
    fieldnames = ["المتدرب", "إجمالي المسائل الكلي", "اليوم", "بداية الجلسة", "نهاية الجلسة", "مدة النشاط", "عدد التقديمات", "المقبول", "المسائل"]
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def generate_markdown_report(users_data):
    now_dt = get_cairo_now()
    now_str = format_arabic_datetime(now_dt) + " - " + format_arabic_time(now_dt)
    lines = [
        f"# تقرير فترات نشاط المتدربين على VJudge (تحديث كل 5 دقائق)",
        f"**تاريخ التحديث:** {now_str} (بتوقيت مصر)",
        "",
        "## نظرة عامة على المتدربين",
        "| المتدرب | الحالة | الإجمالي الكلي (AC) | اليوم (AC) | آخر 7 أيام (AC) | آخر 30 يوماً (AC) | وقت الذروة |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]
    for u in users_data:
        status_icon = "🟢 نشط الآن" if u["is_active_now"] else "⚪ غير نشط"
        lines.append(
            f"| **[{u['username']}](https://vjudge.net/user/{u['username']})** | {status_icon} | **{u['all_time_ac']} مسألة** | **{u['today']['solved']} مسألة** ({u['today']['time_str']}) | **{u['week']['solved']} مسألة** ({u['week']['time_str']}) | **{u['month']['solved']} مسألة** ({u['month']['time_str']}) | {u['peak_hours_str']} |"
        )

    lines.append("\n## تفاصيل جلسات النشاط الأخيرة (من - إلى)")
    for u in users_data:
        lines.append(f"\n### المتدرب: {u['username']} (إجمالي الحل الكلي: {u['all_time_ac']} مسألة)")
        if not u["sessions"]:
            lines.append("_لا توجد جلسات في الفترة المحددة_")
            continue
        lines.append("| اليوم والتاريخ | من (البداية) | إلى (النهاية) | مدة الجلسة | التقديمات | المقبول | المسائل |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :--- |")
        for s in u["sessions"][:15]:
            day_str = format_arabic_datetime(s["start_dt"])
            start_str = format_arabic_time(s["start_dt"])
            end_str = format_arabic_time(s["end_dt"])
            probs_str = ", ".join(s["problems"][:5])
            lines.append(f"| {day_str} | {start_str} | {end_str} | {s['duration_str']} | {s['submissions_count']} | {s['accepted_count']} AC | {probs_str} |")

    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def run_once():
    config = load_config()
    trainees = config.get("trainees", [])
    gap_min = config.get("session_gap_minutes", 60)
    limit = config.get("fetch_limit", 100)

    print(f"[*] Starting activity analysis for {len(trainees)} trainees (5-min interval)...")
    users_data = []

    for username in trainees:
        print(f"  -> Fetching data for {username}...")
        official_counts = fetch_official_profile_data(username)
        subs = fetch_submissions(username, limit=limit)
        stats = analyze_user_comprehensive(username, subs, official_counts, max_gap_minutes=gap_min)
        users_data.append(stats)
        time.sleep(0.4)

    print("[*] Generating reports...")
    generate_html_dashboard(users_data)
    generate_csv_report(users_data)
    generate_markdown_report(users_data)

    print("\n" + "="*65)
    print("        ملخص نشاط المتدربين الرسمي (تحديث كل 5 دقائق)")
    print("="*65)
    for u in users_data:
        status_txt = "🟢 نشط الآن" if u["is_active_now"] else "⚪ غير نشط"
        print(f"\n[{u['username']}] {status_txt}")
        print(f"  - الإجمالي الكلي: {u['all_time_ac']} مسألة AC (من {u['all_time_att']} محاولة)")
        print(f"  - اليوم:          {u['today']['solved']} مسألة AC | وقت الحل: {u['today']['time_str']}")
        print(f"  - آخر 7 أيام:      {u['week']['solved']} مسألة AC | وقت الحل: {u['week']['time_str']}")
        print(f"  - آخر 30 يوماً:    {u['month']['solved']} مسألة AC | وقت الحل: {u['month']['time_str']}")
        print(f"  - أوقات الذروة:    {u['peak_hours_str']}")

    print("\n" + "="*65)
    print(f"[✓] Dashboard HTML: {HTML_FILE}")
    print(f"[✓] GitHub Pages:   {INDEX_FILE}")
    print(f"[✓] Excel / CSV:    {CSV_FILE}")
    print("="*65)

def run_watch():
    config = load_config()
    interval = config.get("check_interval_minutes", 5)
    print(f"[*] Starting Watch Mode (refreshing every {interval} minutes). Press Ctrl+C to stop.")
    while True:
        try:
            print(f"\n[{get_cairo_now().strftime('%Y-%m-%d %I:%M:%S %p')}] Refreshing data...")
            run_once()
            print(f"[*] Sleeping for {interval} minutes...")
            time.sleep(interval * 60)
        except KeyboardInterrupt:
            print("\n[!] Watcher stopped by user.")
            break
        except Exception as e:
            print(f"[!] Error during loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        run_watch()
    else:
        run_once()
