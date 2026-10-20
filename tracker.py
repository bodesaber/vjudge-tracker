import os
import sys
import json
import time
import datetime
import csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import tracker_core as tc

CONFIG_FILE = tc.CONFIG_FILE
DATA_JSON_FILE = tc.DATA_JSON_FILE
HTML_FILE = tc.HTML_FILE
INDEX_FILE = tc.INDEX_FILE
CSV_FILE = tc.CSV_FILE
MD_FILE = tc.MD_FILE

def serialize_users_data(users_data):
    out = []
    for u in users_data:
        u_copy = dict(u)
        sessions_clean = []
        for s in u["sessions"]:
            s_copy = dict(s)
            s_copy.pop("start_dt", None)
            s_copy.pop("end_dt", None)
            sessions_clean.append(s_copy)
        u_copy["sessions"] = sessions_clean
        out.append(u_copy)
    return out

def generate_csv_report(users_data):
    rows = []
    for u in users_data:
        for s in u["sessions"]:
            plat_str = " | ".join([
                f"{pk}: {pv['duration_str']} ({pv['ac_count']} AC/{pv['subs_count']} محاولة)"
                for pk, pv in s["platform_breakdown"].items()
            ])
            timeline_str = " ، ".join([
                f"[{t['time_str']} - {t['platform']}] {t['problemName']} ({t['status']})"
                for t in s["timeline"][:10]
            ])
            rows.append({
                "اسم المتدرب": u["name"],
                "التاريخ": s["date_str"],
                "بداية الجلسة (من)": s["start_str"],
                "نهاية الجلسة (إلى)": s["end_str"],
                "مدة النشاط الكلية": s["duration_str"],
                "تفصيل المنصات في الجلسة": plat_str,
                "إجمالي المحاولات": s["submissions_count"],
                "المسائل المقبولة (AC)": s["accepted_count"],
                "تفاصيل المسائل بالتوقيت": timeline_str
            })
    fieldnames = [
        "اسم المتدرب", "التاريخ", "بداية الجلسة (من)", "نهاية الجلسة (إلى)",
        "مدة النشاط الكلية", "تفصيل المنصات في الجلسة", "إجمالي المحاولات",
        "المسائل المقبولة (AC)", "تفاصيل المسائل بالتوقيت"
    ]
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def generate_markdown_report(users_data):
    now_dt = tc.get_cairo_now()
    now_str = tc.format_arabic_datetime(now_dt) + " - " + tc.format_arabic_time(now_dt)
    top_today = sorted(users_data, key=lambda x: (x["today"].get("score", 0), x["today"]["solved"], x["today"]["time_minutes"]), reverse=True)
    top_week = sorted(users_data, key=lambda x: (x["week"].get("score", 0), x["week"]["solved"], x["week"]["time_minutes"]), reverse=True)
    top_month = sorted(users_data, key=lambda x: (x["month"].get("score", 0), x["month"]["solved"], x["month"]["time_minutes"]), reverse=True)

    lines = [
        "# 📊 تقرير متابعة نشاط المتدربين الشامل 24/7 (VJudge + Codeforces + AtCoder + CSES)",
        f"**تاريخ التحديث:** {now_str} (بتوقيت مصر - قاعدة الـ 30 دقيقة للاتصال المتواصل)",
        "",
        "## 🏆 أبطال التدريب (الأعلى نقاطاً):",
        f"- **🥇 بطل اليوم:** **{top_today[0]['name']}** ({top_today[0]['today'].get('score', 0)} نقطة — {top_today[0]['today']['solved']} AC، نشط {top_today[0]['today']['time_str']})" if top_today else "",
        f"- **🔥 بطل الأسبوع (آخر 7 أيام):** **{top_week[0]['name']}** ({top_week[0]['week'].get('score', 0)} نقطة — {top_week[0]['week']['solved']} AC، نشط {top_week[0]['week']['time_str']})" if top_week else "",
        f"- **👑 بطل الشهر (آخر 30 يوماً):** **{top_month[0]['name']}** ({top_month[0]['month'].get('score', 0)} نقطة — {top_month[0]['month']['solved']} AC، نشط {top_month[0]['month']['time_str']})" if top_month else "",
        "",
        "## 1. جدول الترتيب والملخص العام (مرتب حسب سكور الأسبوع)",
        "| الترتيب | المتدرب | الحالة | سكور اليوم | سكور 7 أيام | سكور 30 يوماً | المنصات المربوطة |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :--- |"
    ]
    for idx, u in enumerate(top_week):
        medal = "🥇 #1" if idx == 0 else ("🥈 #2" if idx == 1 else ("🥉 #3" if idx == 2 else f"#{idx+1}"))
        status_icon = f"🟢 متصل ({', '.join(u['active_platforms_now'])})" if u["is_active_now"] else "⚪ غير متصل"
        plats_info = ", ".join([f"{pk}: `{pv['handle']}` ({pv['acAll']} AC)" for pk, pv in u["platforms"].items()])
        lines.append(
            f"| **{medal}** | **{u['name']}** | {status_icon} | **{u['today'].get('score', 0)} نقطة** ({u['today']['solved']} AC / {u['today']['time_str']}) | **{u['week'].get('score', 0)} نقطة** ({u['week']['solved']} AC / {u['week']['time_str']}) | **{u['month'].get('score', 0)} نقطة** ({u['month']['solved']} AC / {u['month']['time_str']}) | {plats_info} |"
        )

    lines.append("\n## 2. سجل الجلسات التفصيلي والمسائل بالوقت")
    for u in users_data:
        lines.append(f"\n### 👤 {u['name']}")
        if not u["sessions"]:
            lines.append("_لا توجد جلسات مسجلة_")
            continue
        lines.append("| التاريخ | من | إلى | مدة النشاط | تفصيل المنصات | المسائل بالتوقيت |")
        lines.append("| :--- | :---: | :---: | :---: | :--- | :--- |")
        for s in u["sessions"][:15]:
            plat_str = "<br>".join([
                f"**{pk}**: {pv['duration_str']} ({pv['ac_count']} AC)"
                for pk, pv in s["platform_breakdown"].items()
            ])
            tl_str = "<br>".join([
                f"`{t['time_str']}` [{t['platform']}] {t['problemName']} (**{t['status']}**)"
                for t in s["timeline"][:6]
            ])
            lines.append(f"| {s['date_str']} | {s['start_str']} | {s['end_str']} | {s['duration_str']} | {plat_str} | {tl_str} |")

    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def generate_html_dashboard(users_data, config):
    now_dt = tc.get_cairo_now()
    now_str = tc.format_arabic_datetime(now_dt) + " - " + tc.format_arabic_time(now_dt) + " (توقيت مصر)"
    serializable_users = serialize_users_data(users_data)

    payload_obj = {
        "updated_at": now_str,
        "updated_ms": int(now_dt.timestamp() * 1000),
        "config": {
            "trainees": config.get("trainees", []),
            "session_gap_minutes": config.get("session_gap_minutes", 30),
            "coding_buffer_minutes": config.get("coding_buffer_minutes", 15),
            "cloud_sync_topic": config.get("cloud_sync_topic", "vj_tracker_bodesaber_sync_v2"),
            "last_cloud_sync_ts": config.get("last_cloud_sync_ts", 0)
        },
        "users": serializable_users
    }

    with open(DATA_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(payload_obj, f, ensure_ascii=False, indent=2)

    embedded_json = json.dumps(payload_obj, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>منصة متابعة المتدربين السحابية 24/7 (VJudge • Codeforces • AtCoder • CSES)</title>
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
            --purple: #7c3aed;
            --orange: #ea580c;
            --radius: 14px;
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
            max-width: 1380px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #0f172a, #1e293b);
            color: #ffffff;
            padding: 24px 28px;
            border-radius: var(--radius);
            margin-bottom: 20px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header h1 {{
            font-size: 1.65rem;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .header p {{
            color: #94a3b8;
            font-size: 0.92rem;
        }}
        .cloud-badge {{
            background: #10b981;
            color: white;
            padding: 3px 10px;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: bold;
        }}
        .refresh-pill {{
            background: rgba(59, 130, 246, 0.2);
            color: #93c5fd;
            border: 1px solid rgba(59, 130, 246, 0.4);
            padding: 3px 10px;
            border-radius: 8px;
            font-size: 0.75rem;
        }}
        .header-actions {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 10px;
        }}
        .action-btns {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .btn {{
            border: none;
            padding: 9px 18px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 0.88rem;
            font-weight: 600;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .btn-add {{
            background: #10b981;
            color: white;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        }}
        .btn-add:hover {{ background: #059669; transform: translateY(-1px); }}
        .btn-reload {{
            background: var(--primary);
            color: white;
        }}
        .btn-reload:hover {{ background: var(--primary-dark); }}
        .btn-outline {{
            background: #f8fafc;
            color: #334155;
            border: 1px solid #cbd5e1;
            padding: 5px 12px;
            font-size: 0.8rem;
            border-radius: 8px;
        }}
        .btn-outline:hover {{ background: #e2e8f0; }}
        .last-update {{
            background: rgba(255,255,255,0.08);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
            color: #cbd5e1;
        }}
        .rule-note {{
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            color: #1e40af;
            padding: 12px 18px;
            border-radius: 10px;
            font-size: 0.88rem;
            margin-bottom: 22px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(560px, 1fr));
            gap: 22px;
            margin-bottom: 32px;
        }}
        @media (max-width: 640px) {{
            .cards-grid {{ grid-template-columns: 1fr; }}
        }}
        .user-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 22px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.03);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .user-card:hover {{
            box-shadow: 0 8px 20px rgba(0,0,0,0.06);
        }}
        .user-header {{
            display: flex;
            align-items: flex-start;
            gap: 14px;
            margin-bottom: 16px;
            padding-bottom: 14px;
            border-bottom: 1px solid #f1f5f9;
        }}
        .avatar {{
            width: 58px;
            height: 58px;
            border-radius: 50%;
            border: 2px solid var(--border);
            object-fit: cover;
            background: #f8fafc;
        }}
        .user-title {{
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--text-main);
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
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
        .badge-ac {{ background: #dcfce7; color: #166534; }}
        .badge-wa {{ background: #fee2e2; color: #991b1b; }}
        .badge-ping {{ background: #e0f2fe; color: #0369a1; }}
        .plat-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 0.74rem;
            font-weight: 700;
        }}
        .plat-VJudge {{ background: #ffedd5; color: #c2410c; border: 1px solid #fed7aa; }}
        .plat-Codeforces {{ background: #dbeafe; color: #1d4ed8; border: 1px solid #bfdbfe; }}
        .plat-AtCoder {{ background: #f3e8ff; color: #6d28d9; border: 1px solid #e9d5ff; }}
        .plat-CSES {{ background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }}

        .period-matrix {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 16px;
        }}
        .matrix-cell {{
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 10px;
            text-align: center;
        }}
        .matrix-title {{
            font-size: 0.76rem;
            font-weight: 600;
            color: var(--text-muted);
            display: block;
            margin-bottom: 4px;
        }}
        .matrix-val {{
            font-size: 1.25rem;
            font-weight: 800;
        }}
        .matrix-sub {{
            font-size: 0.75rem;
            color: #475569;
            margin-top: 3px;
            font-weight: 600;
        }}
        .text-primary {{ color: var(--primary) !important; }}
        .text-success {{ color: var(--success) !important; }}
        .text-purple {{ color: var(--purple) !important; }}

        .plat-breakdown-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
            margin-bottom: 14px;
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}
        .plat-breakdown-table th {{
            background: #f1f5f9;
            color: #475569;
            padding: 8px 10px;
            font-weight: 600;
            font-size: 0.76rem;
        }}
        .plat-breakdown-table td {{
            padding: 8px 10px;
            border-top: 1px solid var(--border);
        }}
        .peak-box {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 9px 12px;
            font-size: 0.84rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .filter-buttons {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .filter-btn {{
            background: #ffffff;
            border: 1px solid var(--border);
            padding: 7px 15px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.84rem;
            font-weight: 600;
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
            box-shadow: 0 2px 8px rgba(0,0,0,0.03);
            overflow-x: auto;
        }}
        table.sessions-table {{
            width: 100%;
            border-collapse: collapse;
            text-align: right;
            font-size: 0.88rem;
        }}
        table.sessions-table th {{
            background: #f1f5f9;
            color: #334155;
            padding: 13px 14px;
            font-weight: 700;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}
        table.sessions-table td {{
            padding: 12px 14px;
            border-bottom: 1px solid var(--border);
            vertical-align: top;
        }}
        table.sessions-table tr:hover td {{
            background-color: #f8fafc;
        }}
        .time-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.8rem;
            white-space: nowrap;
        }}
        .start-time {{ background: #e0f2fe; color: #0369a1; }}
        .end-time {{ background: #fef3c7; color: #92400e; }}
        .dur-badge {{
            display: inline-block;
            font-weight: 700;
            color: #15803d;
            background: #dcfce7;
            padding: 3px 9px;
            border-radius: 6px;
            font-size: 0.8rem;
        }}
        .plat-mini-list {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        .plat-mini-item {{
            font-size: 0.8rem;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .timeline-list {{
            display: flex;
            flex-direction: column;
            gap: 5px;
            max-height: 190px;
            overflow-y: auto;
            padding-left: 4px;
        }}
        .timeline-item {{
            display: flex;
            align-items: center;
            gap: 7px;
            font-size: 0.8rem;
            background: #f8fafc;
            padding: 4px 8px;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
        }}
        .timeline-time {{
            font-family: monospace;
            font-weight: 700;
            color: #475569;
            background: #e2e8f0;
            padding: 1px 5px;
            border-radius: 4px;
            white-space: nowrap;
        }}

        /* Modal Styles */
        .modal-backdrop {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(15, 23, 42, 0.65);
            backdrop-filter: blur(3px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            padding: 16px;
        }}
        .modal-backdrop.open {{
            display: flex;
        }}
        .modal-box {{
            background: #ffffff;
            border-radius: 16px;
            width: 100%;
            max-width: 540px;
            padding: 26px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
            max-height: 92vh;
            overflow-y: auto;
        }}
        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }}
        .modal-header h3 {{ font-size: 1.25rem; color: var(--text-main); }}
        .close-btn {{
            background: none;
            border: none;
            font-size: 1.4rem;
            cursor: pointer;
            color: #64748b;
        }}
        .form-group {{
            margin-bottom: 14px;
        }}
        .form-group label {{
            display: block;
            font-size: 0.86rem;
            font-weight: 700;
            margin-bottom: 5px;
            color: #1e293b;
        }}
        .form-group input {{
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            font-size: 0.92rem;
            outline: none;
            transition: border 0.2s;
        }}
        .form-group input:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
        }}
        .form-hint {{
            font-size: 0.76rem;
            color: #64748b;
            margin-top: 3px;
        }}
        .modal-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 20px;
            padding-top: 14px;
            border-top: 1px solid var(--border);
            gap: 10px;
        }}
        .btn-danger {{
            background: #fee2e2;
            color: #b91c1c;
        }}
        .btn-danger:hover {{ background: #fecaca; }}
        .toast {{
            position: fixed;
            bottom: 24px;
            left: 24px;
            background: #0f172a;
            color: white;
            padding: 12px 20px;
            border-radius: 10px;
            font-size: 0.88rem;
            font-weight: 600;
            box-shadow: 0 8px 20px rgba(0,0,0,0.2);
            z-index: 2000;
            display: none;
        }}

        /* Champions Banner & Score Leaderboard Styles */
        .champions-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .champ-card {{
            border-radius: 16px;
            padding: 18px 20px;
            color: white;
            position: relative;
            overflow: hidden;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
        }}
        .champ-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 12px 26px rgba(15, 23, 42, 0.18);
        }}
        .champ-today {{ background: linear-gradient(135deg, #059669 0%, #10b981 100%); }}
        .champ-week {{ background: linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%); }}
        .champ-month {{ background: linear-gradient(135deg, #6d28d9 0%, #8b5cf6 100%); }}
        .champ-custom {{ background: linear-gradient(135deg, #b45309 0%, #f59e0b 100%); }}
        .champ-label {{
            font-size: 0.8rem;
            font-weight: 700;
            opacity: 0.92;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .champ-name {{
            font-size: 1.25rem;
            font-weight: 800;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .champ-score-pill {{
            background: rgba(255, 255, 255, 0.22);
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 800;
            backdrop-filter: blur(4px);
        }}
        .champ-stats {{
            font-size: 0.82rem;
            opacity: 0.95;
            margin-bottom: 8px;
        }}
        .champ-runners {{
            font-size: 0.74rem;
            background: rgba(0, 0, 0, 0.16);
            padding: 6px 10px;
            border-radius: 8px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .leaderboard-box {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 22px;
            margin-bottom: 28px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        }}
        .lb-top-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 14px;
            margin-bottom: 16px;
            padding-bottom: 14px;
            border-bottom: 1px solid var(--border);
        }}
        .lb-tabs {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .lb-tab {{
            padding: 8px 14px;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: #f8fafc;
            color: var(--text-main);
            font-weight: 700;
            font-size: 0.84rem;
            cursor: pointer;
            transition: all 0.18s;
        }}
        .lb-tab:hover {{ border-color: var(--primary); color: var(--primary); }}
        .lb-tab.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
            box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
        }}
        .date-explorer-bar {{
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            padding: 14px 16px;
            margin-bottom: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .date-inputs-row {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .date-inputs-row input[type="date"],
        .date-inputs-row input[type="month"] {{
            padding: 7px 12px;
            border: 1px solid #94a3b8;
            border-radius: 8px;
            font-size: 0.88rem;
            font-weight: 700;
            color: #0f172a;
            background: white;
            cursor: pointer;
        }}
        .day-pills-wrap {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .day-pill {{
            padding: 5px 11px;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 700;
            background: white;
            border: 1px solid #cbd5e1;
            color: #334155;
            cursor: pointer;
            transition: all 0.15s;
        }}
        .day-pill:hover {{ border-color: #f59e0b; color: #b45309; background: #fffbeb; }}
        .day-pill.active {{
            background: #f59e0b;
            color: white;
            border-color: #d97706;
        }}

        .podium-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 14px;
            margin-bottom: 18px;
        }}
        .podium-item {{
            border-radius: 12px;
            padding: 14px 16px;
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .podium-1 {{ background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border-color: #f59e0b; }}
        .podium-2 {{ background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-color: #94a3b8; }}
        .podium-3 {{ background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%); border-color: #fb923c; }}
        .podium-rank-icon {{
            font-size: 2rem;
            line-height: 1;
        }}
        .score-bar-wrap {{
            width: 120px;
            height: 7px;
            background: #e2e8f0;
            border-radius: 999px;
            overflow: hidden;
            margin-top: 4px;
        }}
        .score-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #2563eb, #7c3aed);
            border-radius: 999px;
        }}
        .rank-chip {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
        }}
        .rank-1 {{ background: #fef3c7; color: #b45309; border: 1px solid #f59e0b; }}
        .rank-2 {{ background: #f1f5f9; color: #334155; border: 1px solid #94a3b8; }}
        .rank-3 {{ background: #ffedd5; color: #c2410c; border: 1px solid #fb923c; }}
        .rank-other {{ background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }}
        .score-formula-note {{
            font-size: 0.78rem;
            color: #475569;
            background: #f1f5f9;
            padding: 8px 12px;
            border-radius: 8px;
            margin-top: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>
                    📊 منصة متابعة نشاط المتدربين السحابية 24/7
                    <span class="cloud-badge">Cloud 24/7 • VJudge • Codeforces • AtCoder • CSES</span>
                    <span class="refresh-pill">تحديث سحابي كل 5 دقائق</span>
                </h1>
                <p>تعمل 24 ساعة في السحاب بالكامل بدون الحاجة لجهازك — نظام نقاط ذكي وترتيب الأبطال حسب اليوم أو الأسبوع أو الشهر أو أي تاريخ تختاره</p>
            </div>
            <div class="header-actions">
                <div class="action-btns">
                    <button class="btn btn-add" onclick="openProfileModal(null)">➕ إنشاء بروفايل متدرب جديد</button>
                    <button class="btn btn-reload" id="btnLiveRefresh" onclick="triggerLiveRefresh()">🔄 تحديث البيانات الآن</button>
                </div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span id="countdown" style="font-size: 0.8rem; color: #94a3b8;">التحديث القادم خلال: 05:00</span>
                    <div class="last-update" id="lastUpdateText">🕒 آخر تحديث: {now_str}</div>
                </div>
            </div>
        </div>

        <div class="rule-note">
            <div>
                ☁️ <strong>تعمل سحابياً 24/7 (Cloud Native):</strong> هذه المنصة تعمل على سيرفرات السحابة على مدار 24 ساعة حتى وجهازك مغلق تماماً. يمكنك إضافة متدرب أو ربط حساباته عبر (<strong>VJudge و Codeforces و AtCoder و CSES</strong>) من زر <strong>"🔗 ربط / تعديل المنصات"</strong>، ويتم حساب <strong>السكور (النقاط)</strong> وترتيب المتدربين تلقائياً.
            </div>
        </div>

        <!-- Top 4 Champions Banner -->
        <div class="champions-grid" id="championsGrid"></div>

        <!-- Interactive Score Leaderboard & Random Date/Month Explorer -->
        <div class="leaderboard-box">
            <div class="lb-top-bar">
                <div>
                    <h2 style="font-size: 1.2rem; color: #0f172a; display:flex; align-items:center; gap:8px;">
                        🏆 لوحة الشرف والترتيب بالسكور
                        <span id="lbCurrentPeriodTitle" style="font-size:0.86rem; background:#dbeafe; color:#1e40af; padding:3px 10px; border-radius:999px; font-weight:800;">آخر 7 أيام (الأسبوع)</span>
                    </h2>
                    <div style="font-size:0.8rem; color:#64748b; margin-top:3px;">اختر اليوم أو الأسبوع أو الشهر أو حدد أي يوم عشوائي من التقويم لمعرفة أفضل متدرب وترتيب الجميع بالسكور</div>
                </div>
                <div class="lb-tabs">
                    <button class="lb-tab" id="tab-today" onclick="setLeaderboardMode('today')">☀️ اليوم</button>
                    <button class="lb-tab active" id="tab-week" onclick="setLeaderboardMode('week')">🔥 الأسبوع (7 أيام)</button>
                    <button class="lb-tab" id="tab-month" onclick="setLeaderboardMode('month')">👑 الشهر (30 يوماً)</button>
                    <button class="lb-tab" id="tab-day" onclick="setLeaderboardMode('day')">🎯 يوم معين (اختر تاريخ)</button>
                    <button class="lb-tab" id="tab-custom_month" onclick="setLeaderboardMode('custom_month')">📆 شهر معين</button>
                    <button class="lb-tab" id="tab-range" onclick="setLeaderboardMode('range')">↔️ فترة مخصصة</button>
                    <button class="lb-tab" id="tab-all" onclick="setLeaderboardMode('all')">🏅 الإجمالي الكلي</button>
                </div>
            </div>

            <!-- Date / Month / Range Picker Bar -->
            <div class="date-explorer-bar" id="dateExplorerBar">
                <div class="date-inputs-row">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <label style="font-size:0.84rem; font-weight:800; color:#1e293b;">📅 اختر يوماً محدداً لمعرفة الأفضل فيه:</label>
                        <input type="date" id="customDayInput" onchange="onCustomDateChange(this.value)">
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <label style="font-size:0.84rem; font-weight:800; color:#1e293b;">📆 أو اختر شهراً:</label>
                        <input type="month" id="customMonthInput" onchange="onCustomMonthChange(this.value)">
                    </div>
                    <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;" id="customRangeBox">
                        <label style="font-size:0.82rem; font-weight:700; color:#475569;">↔️ أو من:</label>
                        <input type="date" id="rangeFromInput" onchange="onCustomRangeChange()">
                        <label style="font-size:0.82rem; font-weight:700; color:#475569;">إلى:</label>
                        <input type="date" id="rangeToInput" onchange="onCustomRangeChange()">
                    </div>
                </div>
                <div class="day-pills-wrap">
                    <span style="font-size:0.78rem; font-weight:800; color:#475569;">⚡ أيام شهدت نشاطاً (اضغط على أي يوم لعرض بطل وترتيب ذلك اليوم فوراً):</span>
                    <div id="activeDaysPills" style="display:flex; gap:6px; flex-wrap:wrap;"></div>
                </div>
            </div>

            <!-- Top 3 Podium for Selected Period -->
            <div class="podium-grid" id="podiumGrid"></div>

            <!-- Ranked Leaderboard Table -->
            <div style="overflow-x:auto;">
                <table class="sessions-table">
                    <thead>
                        <tr>
                            <th style="width:90px;">المركز</th>
                            <th>المتدرب</th>
                            <th>السكور (النقاط) 🌟</th>
                            <th style="text-align:center;">المسائل المحلولة (AC)</th>
                            <th style="text-align:center;">إجمالي المحاولات</th>
                            <th style="text-align:center;">وقت النشاط المتصل</th>
                            <th>المسائل التي حُلّت في هذه الفترة / اليوم</th>
                        </tr>
                    </thead>
                    <tbody id="leaderboardTableBody"></tbody>
                </table>
            </div>

            <div class="score-formula-note">
                💡 <strong>كيف يُحسب السكور (نظام النقاط الذكي المعتمد على صعوبة المسائل + وقت النشاط)؟</strong><br>
                🎯 <strong>نقاط حل المسألة (AC) حسب تقييم صعوبتها (Difficulty Rating):</strong>
                🟢 سهل (800-900) = <strong>80–100 نقطة</strong> &nbsp;|&nbsp;
                🔵 فوق المبتدئ (1000-1100) = <strong>130–160 نقطة</strong> &nbsp;|&nbsp;
                🟣 متوسط (1200-1300) = <strong>195–235 نقطة</strong> &nbsp;|&nbsp;
                🟠 فوق المتوسط (1400-1500) = <strong>280–335 نقطة</strong> &nbsp;|&nbsp;
                🔴 صعب (1600-1800) = <strong>400–550 نقطة</strong> &nbsp;|&nbsp;
                🔥 صعب جداً (1900-2100) = <strong>640–850 نقطة</strong> &nbsp;|&nbsp;
                👑 ماستر (2200+) = <strong>960+ نقطة</strong>.<br>
                ⏱️ <strong>نقاط الالتزام والنشاط:</strong>
                كل دقيقة نشاط متصل = <strong>1 نقطة</strong> (الساعة = 60 نقطة) &nbsp;|&nbsp;
                كل محاولة إرسال (<strong>Submission</strong>) = <strong>5 نقاط</strong> &nbsp;|&nbsp;
                كل جلسة تدريب = <strong>15 نقطة</strong>.
            </div>
        </div>

        <div class="section-header" style="margin-bottom:14px;">
            <h2>👥 بروفايلات المتدربين التفصيلية (مرتبة تلقائياً حسب السكور المختار)</h2>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <span style="font-size:0.82rem; font-weight:700; color:#475569;">ترتيب الكروت حسب:</span>
                <button class="filter-btn" id="sort-synced" onclick="setCardSortMode('synced')">🏅 نفس فترة لوحة الشرف</button>
                <button class="filter-btn" id="sort-today" onclick="setCardSortMode('today')">☀️ سكور اليوم</button>
                <button class="filter-btn" id="sort-week" onclick="setCardSortMode('week')">🔥 سكور الأسبوع</button>
                <button class="filter-btn" id="sort-month" onclick="setCardSortMode('month')">👑 سكور الشهر</button>
                <button class="filter-btn" id="sort-all" onclick="setCardSortMode('all')">🏆 الإجمالي الكلي</button>
            </div>
        </div>

        <div class="cards-grid" id="cardsGrid"></div>

        <div class="section-header">
            <h2>⏱️ سجل الجلسات التفصيلي (من الساعة كذا للساعة كذا + تفصيل كل منصة والمسائل بالتوقيت)</h2>
            <div class="filter-buttons" id="userFilterButtons"></div>
        </div>

        <div class="table-card">
            <table class="sessions-table">
                <thead>
                    <tr>
                        <th>المتدرب</th>
                        <th>التاريخ</th>
                        <th>فترة الفتح (من ⬅️ إلى)</th>
                        <th>مدة النشاط الكلية</th>
                        <th>تفصيل الوقت والحلول لكل منصة</th>
                        <th>المسائل والأحداث بالتوقيت الدقيق (بالتايمز)</th>
                    </tr>
                </thead>
                <tbody id="sessionsTableBody"></tbody>
            </table>
        </div>
    </div>

    <!-- Create / Edit Trainee Profile Modal -->
    <div class="modal-backdrop" id="profileModal">
        <div class="modal-box">
            <div class="modal-header">
                <h3 id="modalTitle">➕ إنشاء بروفايل متدرب جديد</h3>
                <button class="close-btn" onclick="closeProfileModal()">&times;</button>
            </div>
            <form id="profileForm" onsubmit="saveProfileFromModal(event)">
                <input type="hidden" id="profId">
                <div class="form-group">
                    <label>👤 اسم المتدرب (الاسم المعروض في البروفايل) *</label>
                    <input type="text" id="profName" required placeholder="مثال: عمر عوض صابر">
                    <div class="form-hint">اكتب اسم الشخص عشان تربط تحته كل حساباته في المنصات المختلفة كشخص واحد.</div>
                </div>
                <div class="form-group">
                    <label>🟧 هاندل VJudge (اختياري)</label>
                    <input type="text" id="profVjudge" placeholder="مثال: Omar_Awad_Saber" dir="ltr">
                </div>
                <div class="form-group">
                    <label>🟦 هاندل Codeforces (اختياري)</label>
                    <input type="text" id="profCodeforces" placeholder="مثال: Lumino" dir="ltr">
                    <div class="form-hint">يرصد تلقائياً آخر ظهور أونلاين (حتى لو فتح يتصفح بدون حل) + كل المسائل والتوقيتات.</div>
                </div>
                <div class="form-group">
                    <label>⬜ هاندل AtCoder (اختياري)</label>
                    <input type="text" id="profAtcoder" placeholder="مثال: Lumino" dir="ltr">
                </div>
                <div class="form-group">
                    <label>🟩 رقم مستخدم CSES User ID (اختياري)</label>
                    <input type="text" id="profCses" placeholder="مثال: 12345" dir="ltr">
                </div>
                <div class="modal-footer">
                    <div>
                        <button type="button" class="btn btn-danger" id="btnDeleteProfile" style="display:none;" onclick="deleteCurrentProfile()">🗑️ حذف البروفايل</button>
                    </div>
                    <div style="display:flex; gap:8px;">
                        <button type="button" class="btn btn-outline" onclick="closeProfileModal()">إلغاء</button>
                        <button type="submit" class="btn btn-add" id="btnSaveProfile">💾 حفظ سحابي وبدء التتبع فوراً</button>
                    </div>
                </div>
            </form>
        </div>
    </div>

    <div class="toast" id="toastMsg"></div>

    <script>
        const INITIAL_DATA = {embedded_json};
        let appState = JSON.parse(JSON.stringify(INITIAL_DATA));
        let currentFilterUser = 'all';
        let leaderboardMode = 'week'; // 'today' | 'week' | 'month' | 'day' | 'custom_month' | 'range' | 'all'
        let cardSortMode = 'synced';  // 'synced' | 'today' | 'week' | 'month' | 'all'
        let selectedDayIso = '';
        let selectedMonthIso = '';
        let selectedRangeFrom = '';
        let selectedRangeTo = '';

        const ARABIC_DAYS = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
        const ARABIC_MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];

        function showToast(msg, duration = 4500) {{
            const el = document.getElementById('toastMsg');
            el.innerText = msg;
            el.style.display = 'block';
            setTimeout(() => {{ el.style.display = 'none'; }}, duration);
        }}

        function formatDurationJS(totalMins) {{
            totalMins = Math.round(totalMins || 0);
            if (totalMins <= 0) return '0 دقيقة';
            const h = Math.floor(totalMins / 60);
            const m = totalMins % 60;
            if (h > 0 && m > 0) return `${{h}} س و ${{m}} د`;
            if (h > 0) return `${{h}} ساعة`;
            return `${{m}} دقيقة`;
        }}

        function formatArabicDateJS(ms) {{
            const d = new Date(ms);
            return `${{ARABIC_DAYS[d.getDay()]}} ${{d.getDate()}} ${{ARABIC_MONTHS[d.getMonth()]}} ${{d.getFullYear()}}`;
        }}

        function formatIsoToArabicLabel(isoStr) {{
            if (!isoStr) return '';
            const parts = isoStr.split('-');
            if (parts.length === 3) {{
                const dt = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
                return `${{ARABIC_DAYS[dt.getDay()]}} ${{dt.getDate()}} ${{ARABIC_MONTHS[dt.getMonth()]}} ${{dt.getFullYear()}}`;
            }} else if (parts.length === 2) {{
                const mIdx = Number(parts[1]) - 1;
                return `شهر ${{ARABIC_MONTHS[mIdx] || parts[1]}} ${{parts[0]}}`;
            }}
            return isoStr;
        }}

        function formatArabicTimeJS(ms, withSec = false) {{
            const d = new Date(ms);
            let h = d.getHours();
            const m = String(d.getMinutes()).padStart(2, '0');
            const s = String(d.getSeconds()).padStart(2, '0');
            const period = h >= 12 ? 'م' : 'ص';
            h = h % 12 || 12;
            const hh = String(h).padStart(2, '0');
            return withSec ? `${{hh}}:${{m}}:${{s}} ${{period}}` : `${{hh}}:${{m}} ${{period}}`;
        }}

        function ratingToPointsAndTierJS(rating) {{
            const r = Math.round(rating || 1000);
            if (r <= 850) return {{ pts: 80, tier: '🟢 سهل' }};
            if (r <= 950) return {{ pts: 100, tier: '🟢 سهل' }};
            if (r <= 1050) return {{ pts: 130, tier: '🔵 فوق المبتدئ' }};
            if (r <= 1150) return {{ pts: 160, tier: '🔵 فوق المبتدئ' }};
            if (r <= 1250) return {{ pts: 195, tier: '🟣 متوسط' }};
            if (r <= 1350) return {{ pts: 235, tier: '🟣 متوسط' }};
            if (r <= 1450) return {{ pts: 280, tier: '🟠 فوق المتوسط' }};
            if (r <= 1550) return {{ pts: 335, tier: '🟠 فوق المتوسط' }};
            if (r <= 1650) return {{ pts: 400, tier: '🔴 صعب' }};
            if (r <= 1750) return {{ pts: 470, tier: '🔴 صعب' }};
            if (r <= 1850) return {{ pts: 550, tier: '🔴 صعب' }};
            if (r <= 1950) return {{ pts: 640, tier: '🔥 صعب جداً' }};
            if (r <= 2050) return {{ pts: 740, tier: '🔥 صعب جداً' }};
            if (r <= 2150) return {{ pts: 850, tier: '🔥 صعب جداً' }};
            return {{ pts: Math.round(960 + Math.max(0, r - 2200) * 0.6), tier: '👑 ماستر' }};
        }}

        function evaluateEventDifficultyJS(t) {{
            if (t.type === 'online_ping') return {{ difficulty: 0, diff_tier: '', prob_points: 0 }};
            if (t.difficulty && t.prob_points) {{
                return {{ difficulty: t.difficulty, diff_tier: t.diff_tier || ratingToPointsAndTierJS(t.difficulty).tier, prob_points: t.prob_points }};
            }}
            let rating = t.difficulty || 0;
            if (rating < 800) {{
                const pCode = String(t.probNum || t.problemName || '').toUpperCase();
                const m = pCode.match(/^(\\d+)([A-Z])/);
                if (m) {{
                    const isGym = m[1].length >= 6;
                    const ord = Math.max(0, m[2].charCodeAt(0) - 65);
                    rating = isGym ? Math.min(2300, 1200 + ord * 200) : Math.min(2500, 850 + ord * 280);
                }} else if ((t.platform || '').toLowerCase() === 'atcoder') {{
                    const suffix = String(t.probNum || '').toLowerCase().split('_').pop();
                    const map = {{ a: 800, b: 950, c: 1200, d: 1450, e: 1750, f: 2000, g: 2250, h: 2400 }};
                    rating = map[suffix] || 1200;
                }} else {{
                    rating = 1300;
                }}
            }}
            const info = ratingToPointsAndTierJS(rating);
            return {{ difficulty: rating, diff_tier: info.tier, prob_points: info.pts }};
        }}

        function calcScoreVal(probPts, subs, mins, sessCount) {{
            return Math.round((probPts || 0) + (mins || 0) * 1 + (subs || 0) * 5 + (sessCount || 0) * 15);
        }}

        function getSessionDateIso(s) {{
            if (s.date_iso) return s.date_iso;
            if (!s.start_ms) return '';
            const d = new Date(s.start_ms);
            const y = d.getFullYear();
            const m = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            return `${{y}}-${{m}}-${{day}}`;
        }}

        function getAllActiveDaysMap(users) {{
            const daysMap = {{}};
            (users || []).forEach(u => {{
                (u.sessions || []).forEach(s => {{
                    const iso = getSessionDateIso(s);
                    if (!iso) return;
                    if (!daysMap[iso]) {{
                        daysMap[iso] = {{
                            iso: iso,
                            date_str: s.date_str || formatIsoToArabicLabel(iso),
                            ac: 0,
                            subs: 0,
                            mins: 0,
                            usersSet: new Set()
                        }};
                    }}
                    daysMap[iso].ac += (s.accepted_count || 0);
                    daysMap[iso].subs += (s.submissions_count || 0);
                    daysMap[iso].mins += (s.duration_minutes || 0);
                    daysMap[iso].usersSet.add(u.id);
                }});
            }});
            return Object.values(daysMap).sort((a, b) => b.iso.localeCompare(a.iso));
        }}

        function ensureDateDefaults(users) {{
            const activeDays = getAllActiveDaysMap(users);
            const now = new Date();
            const todayIso = `${{now.getFullYear()}}-${{String(now.getMonth()+1).padStart(2,'0')}}-${{String(now.getDate()).padStart(2,'0')}}`;
            const monthIso = `${{now.getFullYear()}}-${{String(now.getMonth()+1).padStart(2,'0')}}`;
            if (!selectedDayIso) {{
                // Pick the most recent day with AC, or today
                const dayWithAc = activeDays.find(d => d.ac > 0);
                selectedDayIso = dayWithAc ? dayWithAc.iso : (activeDays[0] ? activeDays[0].iso : todayIso);
            }}
            if (!selectedMonthIso) selectedMonthIso = monthIso;
            if (!selectedRangeTo) selectedRangeTo = todayIso;
            if (!selectedRangeFrom) {{
                const weekAgo = new Date(Date.now() - 7 * 86400 * 1000);
                selectedRangeFrom = `${{weekAgo.getFullYear()}}-${{String(weekAgo.getMonth()+1).padStart(2,'0')}}-${{String(weekAgo.getDate()).padStart(2,'0')}}`;
            }}
            const dayInput = document.getElementById('customDayInput');
            if (dayInput && dayInput.value !== selectedDayIso) dayInput.value = selectedDayIso;
            const monthInput = document.getElementById('customMonthInput');
            if (monthInput && monthInput.value !== selectedMonthIso) monthInput.value = selectedMonthIso;
            const rFrom = document.getElementById('rangeFromInput');
            if (rFrom && rFrom.value !== selectedRangeFrom) rFrom.value = selectedRangeFrom;
            const rTo = document.getElementById('rangeToInput');
            if (rTo && rTo.value !== selectedRangeTo) rTo.value = selectedRangeTo;
        }}

        function computeUserStatsForMode(u, mode) {{
            const nowMs = Date.now();
            const todayStart = new Date();
            todayStart.setHours(0, 0, 0, 0);
            const todayStartMs = todayStart.getTime();
            const weekStartMs = nowMs - 7 * 86400 * 1000;
            const monthStartMs = nowMs - 30 * 86400 * 1000;

            const filterSessions = (pred) => (u.sessions || []).filter(pred);
            const collectProblemsFromSessions = (sessList) => {{
                const acProbsMap = {{}};
                sessList.forEach(s => {{
                    (s.timeline || []).forEach(t => {{
                        if (t.type === 'submission' && t.is_ac) {{
                            const key = `${{t.platform}}_${{t.probNum || t.problemName}}`;
                            const dInfo = evaluateEventDifficultyJS(t);
                            if (!acProbsMap[key] || dInfo.prob_points > acProbsMap[key].prob_points) {{
                                acProbsMap[key] = {{
                                    name: t.problemName || t.probNum,
                                    url: t.problemUrl || '#',
                                    platform: t.platform || '',
                                    time_str: t.time_str || '',
                                    difficulty: dInfo.difficulty,
                                    diff_tier: dInfo.diff_tier,
                                    prob_points: dInfo.prob_points
                                }};
                            }}
                        }}
                    }});
                }});
                return Object.values(acProbsMap).sort((a, b) => (b.difficulty || 0) - (a.difficulty || 0));
            }};

            const summarizeProblemsStats = (acProbs, totalSolvedCount, fallbackProbPts, fallbackAvgDiff, fallbackMaxDiff) => {{
                const recPts = acProbs.reduce((a, p) => a + (p.prob_points || 100), 0);
                const avgPts = acProbs.length > 0 ? (recPts / acProbs.length) : 120;
                const extraSolved = Math.max(0, totalSolvedCount - acProbs.length);
                const computedProbPts = Math.round(recPts + extraSolved * avgPts);
                const probPts = Math.max(fallbackProbPts || 0, computedProbPts);
                const avgDiff = acProbs.length > 0
                    ? Math.round(acProbs.reduce((a, p) => a + (p.difficulty || 1000), 0) / acProbs.length)
                    : (fallbackAvgDiff || 0);
                const maxDiff = acProbs.length > 0
                    ? Math.max(...acProbs.map(p => p.difficulty || 0))
                    : (fallbackMaxDiff || 0);
                return {{ probPts, avgDiff, maxDiff }};
            }};

            if (mode === 'today' || mode === 'week' || mode === 'month') {{
                const pObj = u[mode] || {{ solved: 0, subs: 0, time_minutes: 0, time_str: '0 دقيقة', sessions: 0 }};
                const thresh = mode === 'today' ? todayStartMs : (mode === 'week' ? weekStartMs : monthStartMs);
                const sIn = filterSessions(s => (s.end_ms || 0) >= thresh);
                const acProbs = collectProblemsFromSessions(sIn);
                const solved = Math.max(pObj.solved || 0, acProbs.length);
                const subs = pObj.subs || 0;
                const mins = pObj.time_minutes || 0;
                const sessCount = pObj.sessions || sIn.length;
                const pStats = summarizeProblemsStats(acProbs, solved, pObj.problem_points, pObj.avg_difficulty, pObj.max_difficulty);
                const score = pObj.score || calcScoreVal(pStats.probPts, subs, mins, sessCount);
                return {{
                    solved,
                    subs,
                    time_minutes: mins,
                    time_str: pObj.time_str || formatDurationJS(mins),
                    sessions: sessCount,
                    problem_points: pStats.probPts,
                    avg_difficulty: pStats.avgDiff,
                    max_difficulty: pStats.maxDiff,
                    score,
                    acProblems: acProbs
                }};
            }}

            if (mode === 'all') {{
                const sAll = u.sessions || [];
                const acProbs = collectProblemsFromSessions(sAll);
                const solved = Math.max(u.all_time_ac || 0, acProbs.length);
                const mins = sAll.reduce((a, s) => a + (s.duration_minutes || 0), 0);
                const subs = sAll.reduce((a, s) => a + (s.submissions_count || 0), 0);
                const sessCount = sAll.length;
                const pStats = summarizeProblemsStats(acProbs, solved, 0, u.avg_difficulty, u.max_difficulty);
                const score = u.all_time_score || calcScoreVal(pStats.probPts, subs, mins, sessCount);
                return {{
                    solved,
                    subs,
                    time_minutes: mins,
                    time_str: formatDurationJS(mins),
                    sessions: sessCount,
                    problem_points: pStats.probPts,
                    avg_difficulty: pStats.avgDiff,
                    max_difficulty: pStats.maxDiff,
                    score,
                    acProblems: acProbs
                }};
            }}

            // Custom Date / Month / Range modes
            let sFiltered = [];
            if (mode === 'day') {{
                sFiltered = filterSessions(s => getSessionDateIso(s) === selectedDayIso);
            }} else if (mode === 'custom_month') {{
                sFiltered = filterSessions(s => getSessionDateIso(s).startsWith(selectedMonthIso));
            }} else if (mode === 'range') {{
                sFiltered = filterSessions(s => {{
                    const dIso = getSessionDateIso(s);
                    return dIso && dIso >= selectedRangeFrom && dIso <= selectedRangeTo;
                }});
            }}

            const acProbs = collectProblemsFromSessions(sFiltered);
            const rawAcSum = sFiltered.reduce((a, s) => a + (s.accepted_count || 0), 0);
            const solved = acProbs.length > 0 ? acProbs.length : rawAcSum;
            const subs = sFiltered.reduce((a, s) => a + (s.submissions_count || 0), 0);
            const mins = sFiltered.reduce((a, s) => a + (s.duration_minutes || 0), 0);
            const sessCount = sFiltered.length;
            const pStats = summarizeProblemsStats(acProbs, solved, 0, 0, 0);
            const score = calcScoreVal(pStats.probPts, subs, mins, sessCount);
            return {{
                solved,
                subs,
                time_minutes: mins,
                time_str: formatDurationJS(mins),
                sessions: sessCount,
                problem_points: pStats.probPts,
                avg_difficulty: pStats.avgDiff,
                max_difficulty: pStats.maxDiff,
                score,
                acProblems: acProbs
            }};
        }}

        function getRankedUsersForMode(users, mode) {{
            return (users || []).map(u => ({{
                user: u,
                stats: computeUserStatsForMode(u, mode)
            }})).sort((a, b) => {{
                if (b.stats.score !== a.stats.score) return b.stats.score - a.stats.score;
                if (b.stats.solved !== a.stats.solved) return b.stats.solved - a.stats.solved;
                if (b.stats.time_minutes !== a.stats.time_minutes) return b.stats.time_minutes - a.stats.time_minutes;
                return (b.user.all_time_ac || 0) - (a.user.all_time_ac || 0);
            }});
        }}

        function getModeTitle(mode) {{
            if (mode === 'today') return '☀️ اليوم';
            if (mode === 'week') return '🔥 آخر 7 أيام (الأسبوع)';
            if (mode === 'month') return '👑 آخر 30 يوماً (الشهر)';
            if (mode === 'day') return `🎯 يوم ${{formatIsoToArabicLabel(selectedDayIso)}}`;
            if (mode === 'custom_month') return `📆 ${{formatIsoToArabicLabel(selectedMonthIso)}}`;
            if (mode === 'range') return `↔️ من ${{selectedRangeFrom}} إلى ${{selectedRangeTo}}`;
            if (mode === 'all') return '🏅 الإجمالي الكلي (All-Time)';
            return '';
        }}

        function setLeaderboardMode(mode) {{
            leaderboardMode = mode;
            renderDashboard();
        }}

        function setCardSortMode(mode) {{
            cardSortMode = mode;
            renderDashboard();
        }}

        function onCustomDateChange(val) {{
            if (!val) return;
            selectedDayIso = val;
            leaderboardMode = 'day';
            renderDashboard();
        }}

        function onCustomMonthChange(val) {{
            if (!val) return;
            selectedMonthIso = val;
            leaderboardMode = 'custom_month';
            renderDashboard();
        }}

        function onCustomRangeChange() {{
            const f = document.getElementById('rangeFromInput').value;
            const t = document.getElementById('rangeToInput').value;
            if (f) selectedRangeFrom = f;
            if (t) selectedRangeTo = t;
            leaderboardMode = 'range';
            renderDashboard();
        }}

        function selectQuickDay(iso) {{
            selectedDayIso = iso;
            leaderboardMode = 'day';
            renderDashboard();
        }}

        function renderChampionsAndLeaderboard(users) {{
            ensureDateDefaults(users);

            const rankedToday = getRankedUsersForMode(users, 'today');
            const rankedWeek = getRankedUsersForMode(users, 'week');
            const rankedMonth = getRankedUsersForMode(users, 'month');
            const customMode = (leaderboardMode === 'day' || leaderboardMode === 'custom_month' || leaderboardMode === 'range') ? leaderboardMode : 'day';
            const rankedCustom = getRankedUsersForMode(users, customMode);

            const buildChampCard = (title, icon, cssClass, rankedList, clickMode) => {{
                const top1 = rankedList[0];
                const top2 = rankedList[1];
                const top3 = rankedList[2];
                const hasActivity = top1 && top1.stats.score > 0;
                const winnerName = hasActivity ? top1.user.name : 'لا يوجد نشاط مسجل بعد';
                const winnerScore = hasActivity ? `${{top1.stats.score.toLocaleString()}} نقطة` : '0 نقطة';
                const winnerStats = hasActivity
                    ? `✅ حل <strong>${{top1.stats.solved}} AC</strong> (${{top1.stats.subs}} محاولة) • ⏱️ نشط <strong>${{top1.stats.time_str}}</strong>`
                    : 'اختر تاريخاً آخر أو انتظر تسجيل نشاط جديد';
                const runnersHtml = hasActivity
                    ? `<span>🥈 الثاني: <strong>${{top2 && top2.stats.score > 0 ? `${{top2.user.name}} (${{top2.stats.score}} ن)` : '—'}}</strong></span>
                       <span>🥉 الثالث: <strong>${{top3 && top3.stats.score > 0 ? `${{top3.user.name}} (${{top3.stats.score}} ن)` : '—'}}</strong></span>`
                    : `<span>اضغط هنا لعرض تفاصيل الترتيب الكامل</span>`;

                return `
                    <div class="champ-card ${{cssClass}}" onclick="setLeaderboardMode('${{clickMode}}')">
                        <div class="champ-label">
                            <span>${{icon}} ${{title}}</span>
                            <span class="champ-score-pill">🌟 ${{winnerScore}}</span>
                        </div>
                        <div class="champ-name">🥇 ${{winnerName}}</div>
                        <div class="champ-stats">${{winnerStats}}</div>
                        <div class="champ-runners">${{runnersHtml}}</div>
                    </div>
                `;
            }};

            const customLabel = customMode === 'day'
                ? `بطل يوم: ${{formatIsoToArabicLabel(selectedDayIso)}}`
                : (customMode === 'custom_month' ? `بطل ${{formatIsoToArabicLabel(selectedMonthIso)}}` : `بطل الفترة (${{selectedRangeFrom}} ⬅️ ${{selectedRangeTo}})`);

            document.getElementById('championsGrid').innerHTML =
                buildChampCard('أفضل متدرب اليوم (بطل اليوم)', '☀️', 'champ-today', rankedToday, 'today') +
                buildChampCard('أفضل متدرب في الأسبوع (آخر 7 أيام)', '🔥', 'champ-week', rankedWeek, 'week') +
                buildChampCard('أفضل متدرب في الشهر (آخر 30 يوماً)', '👑', 'champ-month', rankedMonth, 'month') +
                buildChampCard(customLabel, '🎯', 'champ-custom', rankedCustom, customMode);

            // Update Leaderboard Tabs UI
            ['today', 'week', 'month', 'day', 'custom_month', 'range', 'all'].forEach(m => {{
                const el = document.getElementById('tab-' + m);
                if (el) el.classList.toggle('active', leaderboardMode === m);
            }});
            document.getElementById('lbCurrentPeriodTitle').innerText = getModeTitle(leaderboardMode);

            // Render Quick Active Day Pills (up to 18 recent active days)
            const activeDays = getAllActiveDaysMap(users);
            const pillsEl = document.getElementById('activeDaysPills');
            if (pillsEl) {{
                pillsEl.innerHTML = activeDays.slice(0, 18).map(d => {{
                    const isAct = (leaderboardMode === 'day' && selectedDayIso === d.iso);
                    return `<button class="day-pill ${{isAct ? 'active' : ''}}" onclick="selectQuickDay('${{d.iso}}')" title="نشط فيه ${{d.usersSet.size}} متدربين — إجمالي الوقت ${{formatDurationJS(d.mins)}}">
                        ${{d.date_str}} (${{d.ac}} AC)
                    </button>`;
                }}).join('');
            }}

            // Compute Ranked List for Active Leaderboard Mode
            const currentRanked = getRankedUsersForMode(users, leaderboardMode);
            const maxScore = Math.max(...currentRanked.map(r => r.stats.score), 1);

            // Render Top 3 Podium
            const podiumEl = document.getElementById('podiumGrid');
            if (podiumEl) {{
                const podiumIcons = ['🥇', '🥈', '🥉'];
                const podiumTitles = ['المركز الأول (البطل)', 'المركز الثاني', 'المركز الثالث'];
                podiumEl.innerHTML = currentRanked.slice(0, 3).map((item, idx) => {{
                    const st = item.stats;
                    return `
                        <div class="podium-item podium-${{idx+1}}">
                            <div class="podium-rank-icon">${{podiumIcons[idx]}}</div>
                            <div style="flex:1;">
                                <div style="font-size:0.74rem; font-weight:800; color:#64748b;">${{podiumTitles[idx]}}</div>
                                <div style="font-size:1.05rem; font-weight:800; color:#0f172a; margin:2px 0;">${{item.user.name}}</div>
                                <div style="font-size:0.8rem; color:#334155;">
                                    <strong style="color:#b45309;">🌟 ${{st.score.toLocaleString()}} نقطة</strong>
                                    &nbsp;•&nbsp; ✅ <strong>${{st.solved}} AC</strong>
                                    &nbsp;•&nbsp; ⏱️ ${{st.time_str}}
                                </div>
                            </div>
                        </div>
                    `;
                }}).join('');
            }}

            // Render Leaderboard Table
            const lbBody = document.getElementById('leaderboardTableBody');
            if (lbBody) {{
                lbBody.innerHTML = currentRanked.map((item, idx) => {{
                    const u = item.user;
                    const st = item.stats;
                    const rankNum = idx + 1;
                    const rankClass = rankNum === 1 ? 'rank-1' : (rankNum === 2 ? 'rank-2' : (rankNum === 3 ? 'rank-3' : 'rank-other'));
                    const rankIcon = rankNum === 1 ? '🥇 #1' : (rankNum === 2 ? '🥈 #2' : (rankNum === 3 ? '🥉 #3' : `#${{rankNum}}`));
                    const pct = Math.min(100, Math.round((st.score / maxScore) * 100));

                    const platBadges = Object.keys(u.platforms || {{}}).map(pk =>
                        `<span class="plat-tag plat-${{pk}}" style="margin-left:4px;">${{pk}}: ${{u.platforms[pk].handle}}</span>`
                    ).join('');

                    const probsHtml = st.acProblems && st.acProblems.length > 0
                        ? st.acProblems.slice(0, 8).map(p =>
                            `<a href="${{p.url}}" target="_blank" style="display:inline-block; background:#dcfce7; color:#166534; padding:3px 8px; border-radius:6px; font-size:0.73rem; font-weight:700; text-decoration:none; margin:2px; border:1px solid #bbf7d0;">
                                ✅ ${{p.name}}
                                <span style="background:#fef3c7; color:#b45309; padding:1px 5px; border-radius:4px; margin-right:3px; font-weight:800;">
                                    ${{p.diff_tier || '🎯'}} ${{p.difficulty || ''}} (+${{p.prob_points || 100}}ن)
                                </span>
                            </a>`
                        ).join('') + (st.acProblems.length > 8 ? `<span style="font-size:0.74rem; color:#64748b; font-weight:700;"> +${{st.acProblems.length - 8}} مسألة أخرى</span>` : '')
                        : `<span style="color:#94a3b8; font-size:0.78rem;">${{st.solved > 0 ? `حل ${{st.solved}} مسألة AC` : 'لا توجد مسائل محلولة في هذه الفترة'}}</span>`;

                    const diffSummaryHtml = st.avg_difficulty > 0
                        ? `<div style="font-size:0.72rem; color:#b45309; font-weight:800; margin-top:4px;">🎯 متوسط الصعوبة: ${{st.avg_difficulty}} (أعلى: ${{st.max_difficulty}})</div>`
                        : '';

                    return `
                        <tr>
                            <td><span class="rank-chip ${{rankClass}}">${{rankIcon}}</span></td>
                            <td>
                                <div style="font-weight:800; color:#0f172a; font-size:0.95rem;">${{u.name}}</div>
                                <div style="margin-top:4px;">${{platBadges}}</div>
                            </td>
                            <td>
                                <div style="font-weight:800; font-size:1rem; color:#1e40af;">🌟 ${{st.score.toLocaleString()}} نقطة</div>
                                <div class="score-bar-wrap"><div class="score-bar-fill" style="width:${{pct}}%;"></div></div>
                                <div style="font-size:0.7rem; color:#64748b; margin-top:3px;">
                                    (${{(st.problem_points || 0).toLocaleString()}} لصعوبة المسائل + ${{st.time_minutes}} للوقت + ${{st.subs * 5}} للمحاولات + ${{st.sessions * 15}} للجلسات)
                                </div>
                            </td>
                            <td style="text-align:center;">
                                <span class="badge badge-ac" style="font-size:0.86rem; padding:4px 10px;">✅ ${{st.solved}} AC</span>
                                ${{diffSummaryHtml}}
                            </td>
                            <td style="text-align:center; font-weight:700; color:#334155;">${{st.subs}} محاولة (${{st.sessions}} جلسة)</td>
                            <td style="text-align:center;"><span class="dur-badge">⏱️ ${{st.time_str}}</span></td>
                            <td>${{probsHtml}}</td>
                        </tr>
                    `;
                }}).join('');
            }}

            return currentRanked;
        }}

        function renderDashboard() {{
            const users = appState.users || [];
            document.getElementById('lastUpdateText').innerText = '🕒 آخر تحديث: ' + (appState.updated_at || '');

            // 1. Render Champions & Leaderboard first
            renderChampionsAndLeaderboard(users);

            // 2. Determine sort order for Trainee Profile Cards
            const effectiveSortMode = cardSortMode === 'synced' ? leaderboardMode : cardSortMode;
            ['synced', 'today', 'week', 'month', 'all'].forEach(sm => {{
                const btn = document.getElementById('sort-' + sm);
                if (btn) btn.classList.toggle('active', cardSortMode === sm);
            }});
            const rankedForCards = getRankedUsersForMode(users, effectiveSortMode);
            const sortModeLabel = getModeTitle(effectiveSortMode);

            const cardsGrid = document.getElementById('cardsGrid');
            cardsGrid.innerHTML = rankedForCards.map((rankedItem, idx) => {{
                const u = rankedItem.user;
                const activeStats = rankedItem.stats;
                const rankNum = idx + 1;
                const rankClass = rankNum === 1 ? 'rank-1' : (rankNum === 2 ? 'rank-2' : (rankNum === 3 ? 'rank-3' : 'rank-other'));
                const rankMedal = rankNum === 1 ? '🥇 المركز #1' : (rankNum === 2 ? '🥈 المركز #2' : (rankNum === 3 ? '🥉 المركز #3' : `المركز #${{rankNum}}`));

                const todayScore = computeUserStatsForMode(u, 'today').score;
                const weekScore = computeUserStatsForMode(u, 'week').score;
                const monthScore = computeUserStatsForMode(u, 'month').score;
                const allScore = computeUserStatsForMode(u, 'all').score;

                const badgeClass = u.is_active_now ? 'badge-online' : 'badge-offline';
                const activePlats = (u.active_platforms_now && u.active_platforms_now.length) ? ` (${{u.active_platforms_now.join(' + ')}})` : '';
                const badgeText = u.is_active_now ? `🟢 متصل الآن${{activePlats}}` : '⚪ غير متصل حالياً';
                const avatarSrc = u.avatar || 'https://cdn.vjudge.net.cn/user/avatar/default.png';

                const plats = u.platforms || {{}};
                const platRows = Object.keys(plats).map(pk => {{
                    const pv = plats[pk];
                    const pStatus = pv.is_online
                        ? `<span class="badge badge-online" style="font-size:0.7rem;padding:2px 6px;">🟢 متصل الآن</span>`
                        : `<span style="color:#64748b;font-size:0.76rem;">⚪ ${{pv.last_seen_str}}</span>`;
                    return `
                        <tr>
                            <td>
                                <span class="plat-tag plat-${{pk}}">${{pk}}</span>
                                <a href="${{pv.url}}" target="_blank" style="font-weight:700;color:#0f172a;text-decoration:none;margin-right:4px;" dir="ltr">${{pv.handle}}</a>
                                ${{pv.extra ? `<div style="font-size:0.7rem;color:#64748b;">${{pv.extra}}</div>` : ''}}
                            </td>
                            <td style="text-align:center;">${{pStatus}}</td>
                            <td style="text-align:center;">
                                <strong>${{pv.today.time_str}}</strong>
                                <div style="font-size:0.72rem;color:#16a34a;">${{pv.today.solved}} AC (${{pv.today.subs}} محاولة)</div>
                            </td>
                            <td style="text-align:center;">
                                <strong>${{pv.week.time_str}}</strong>
                                <div style="font-size:0.72rem;color:#2563eb;">${{pv.week.solved}} AC (${{pv.week.subs}} محاولة)</div>
                            </td>
                            <td style="text-align:center;">
                                <strong>${{pv.month.time_str}}</strong>
                                <div style="font-size:0.72rem;color:#7c3aed;">${{pv.month.solved}} AC (${{pv.month.subs}} محاولة)</div>
                            </td>
                            <td style="text-align:center;font-weight:800;color:#0f172a;">${{pv.acAll}} AC</td>
                        </tr>
                    `;
                }}).join('');

                return `
                <div class="user-card" id="card-${{u.id}}">
                    <div class="user-header">
                        <img src="${{avatarSrc}}" alt="${{u.name}}" class="avatar" onerror="this.src='https://cdn.vjudge.net.cn/user/avatar/default.png'">
                        <div style="flex:1;">
                            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                                    <span class="rank-chip ${{rankClass}}">${{rankMedal}}</span>
                                    <h3 class="user-title">${{u.name}}</h3>
                                    <span style="background:#eff6ff; color:#1e40af; padding:3px 10px; border-radius:999px; font-size:0.76rem; font-weight:800;">
                                        🌟 ${{activeStats.score.toLocaleString()}} نقطة (${{sortModeLabel}})
                                    </span>
                                </div>
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <span class="badge ${{badgeClass}}">${{badgeText}}</span>
                                    <button class="btn btn-outline" onclick="openProfileModal('${{u.id}}')">🔗 ربط / تعديل المنصات</button>
                                </div>
                            </div>
                            <div style="font-size:0.8rem; color:#475569; margin-top:6px;">
                                آخر تواجد أو نشاط عام: <strong>${{u.last_seen_str}}</strong> | آخر حدث: <em>${{u.last_problem_str}}</em>
                            </div>
                        </div>
                    </div>

                    <div class="period-matrix">
                        <div class="matrix-cell">
                            <span class="matrix-title">📅 إجمالي اليوم (كل المنصات)</span>
                            <div class="matrix-val text-success">${{u.today.time_str}}</div>
                            <div class="matrix-sub">حل ${{u.today.solved}} مسائل AC (${{u.today.subs}} محاولة)</div>
                            <div style="font-size:0.74rem; font-weight:800; color:#15803d; margin-top:3px;">🌟 السكور: ${{todayScore.toLocaleString()}} نقطة</div>
                        </div>
                        <div class="matrix-cell">
                            <span class="matrix-title">🗓️ آخر 7 أيام (كل المنصات)</span>
                            <div class="matrix-val text-primary">${{u.week.time_str}}</div>
                            <div class="matrix-sub">حل ${{u.week.solved}} مسائل AC (${{u.week.sessions}} جلسات)</div>
                            <div style="font-size:0.74rem; font-weight:800; color:#1d4ed8; margin-top:3px;">🌟 السكور: ${{weekScore.toLocaleString()}} نقطة</div>
                        </div>
                        <div class="matrix-cell">
                            <span class="matrix-title">📊 آخر 30 يوماً (كل المنصات)</span>
                            <div class="matrix-val text-purple">${{u.month.time_str}}</div>
                            <div class="matrix-sub">حل ${{u.month.solved}} مسائل AC (${{u.month.sessions}} جلسة)</div>
                            <div style="font-size:0.74rem; font-weight:800; color:#6d28d9; margin-top:3px;">🌟 السكور: ${{monthScore.toLocaleString()}} نقطة</div>
                        </div>
                    </div>

                    <div style="margin-bottom:8px; font-size:0.8rem; font-weight:700; color:#334155;">📌 تفصيل نشاط وحلول كل منصة على حدة:</div>
                    <table class="plat-breakdown-table">
                        <thead>
                            <tr>
                                <th>المنصة والهاندل</th>
                                <th style="text-align:center;">الحالة</th>
                                <th style="text-align:center;">نشاط اليوم</th>
                                <th style="text-align:center;">نشاط 7 أيام</th>
                                <th style="text-align:center;">نشاط 30 يوماً</th>
                                <th style="text-align:center;">إجمالي الحل</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${{platRows || '<tr><td colspan="6" style="text-align:center;color:#94a3b8;">جاري مزامنة بيانات المنصات...</td></tr>'}}
                        </tbody>
                    </table>

                    <div class="peak-box">
                        <span>⏰ <strong>أوقات النشاط المعتادة:</strong> ${{u.peak_hours_str}}</span>
                        <span style="color:#b45309;font-weight:700;">🏆 الإجمالي الموحد: ${{u.all_time_ac}} مسألة AC (🌟 ${{allScore.toLocaleString()}} نقطة)</span>
                    </div>
                </div>
                `;
            }}).join('');

            const filterContainer = document.getElementById('userFilterButtons');
            let filterHtml = `<button class="filter-btn ${{currentFilterUser === 'all' ? 'active' : ''}}" onclick="setFilterUser('all')">عرض الكل (${{users.length}})</button>`;
            users.forEach(u => {{
                filterHtml += `<button class="filter-btn ${{currentFilterUser === u.id ? 'active' : ''}}" onclick="setFilterUser('${{u.id}}')">${{u.name}}</button>`;
            }});
            filterContainer.innerHTML = filterHtml;

            const tbody = document.getElementById('sessionsTableBody');
            let allRows = [];
            users.forEach(u => {{
                if (currentFilterUser !== 'all' && currentFilterUser !== u.id) return;
                (u.sessions || []).forEach(s => {{
                    allRows.push({{ user: u, session: s }});
                }});
            }});
            allRows.sort((a, b) => (b.session.end_ms || 0) - (a.session.end_ms || 0));

            tbody.innerHTML = allRows.slice(0, 120).map(item => {{
                const u = item.user;
                const s = item.session;
                const pb = s.platform_breakdown || {{}};
                const pbHtml = Object.keys(pb).map(pk => {{
                    const pv = pb[pk];
                    const extraPing = (pv.subs_count === 0 && pv.pings_count > 0) ? ' (تصفح أونلاين)' : ` (حل ${{pv.ac_count}} AC من ${{pv.subs_count}} محاولة)`;
                    return `
                        <div class="plat-mini-item">
                            <span class="plat-tag plat-${{pk}}">${{pk}}</span>
                            <span>نشط <strong>${{pv.duration_str}}</strong>${{extraPing}}</span>
                        </div>
                    `;
                }}).join('');

                const tlHtml = (s.timeline || []).map(t => {{
                    let statusBadge = '';
                    let diffBadge = '';
                    if (t.type === 'online_ping') {{
                        statusBadge = `<span class="badge badge-ping">👁️ متصل أونلاين</span>`;
                    }} else {{
                        const dInfo = evaluateEventDifficultyJS(t);
                        if (dInfo.difficulty > 0) {{
                            diffBadge = `<span style="background:#fef3c7;color:#b45309;padding:2px 7px;border-radius:6px;font-size:0.71rem;font-weight:800;white-space:nowrap;">${{dInfo.diff_tier}} (${{dInfo.difficulty}}) • ${{t.is_ac ? `+${{dInfo.prob_points}}ن` : '+5ن'}}</span>`;
                        }}
                        if (t.is_ac) {{
                            statusBadge = `<span class="badge badge-ac">✅ ${{t.status}}</span>`;
                        }} else {{
                            statusBadge = `<span class="badge badge-wa">❌ ${{t.status}}</span>`;
                        }}
                    }}
                    return `
                        <div class="timeline-item">
                            <span class="timeline-time">${{t.time_str}}</span>
                            <span class="plat-tag plat-${{t.platform}}">${{t.platform}}</span>
                            <a href="${{t.problemUrl}}" target="_blank" style="color:#0f172a;font-weight:600;text-decoration:none;flex:1;">${{t.problemName}}</a>
                            ${{diffBadge}}
                            ${{statusBadge}}
                        </div>
                    `;
                }}).join('');

                return `
                    <tr>
                        <td><strong>${{u.name}}</strong></td>
                        <td style="white-space:nowrap;">${{s.date_str}}</td>
                        <td style="white-space:nowrap;">
                            <span class="time-badge start-time">من ${{s.start_str}}</span>
                            <span style="margin:0 4px;color:#94a3b8;">⬅️</span>
                            <span class="time-badge end-time">إلى ${{s.end_str}}</span>
                        </td>
                        <td><span class="dur-badge">${{s.duration_str}}</span></td>
                        <td><div class="plat-mini-list">${{pbHtml}}</div></td>
                        <td><div class="timeline-list">${{tlHtml}}</div></td>
                    </tr>
                `;
            }}).join('');
        }}

        function setFilterUser(uid) {{
            currentFilterUser = uid;
            renderDashboard();
        }}

        function openProfileModal(profileId) {{
            const modal = document.getElementById('profileModal');
            const title = document.getElementById('modalTitle');
            const btnDel = document.getElementById('btnDeleteProfile');
            const trainees = appState.config.trainees || [];

            if (profileId) {{
                const prof = trainees.find(t => t.id === profileId);
                if (!prof) return;
                title.innerText = `🔗 تعديل وربط منصات المتدرب: ${{prof.name}}`;
                document.getElementById('profId').value = prof.id;
                document.getElementById('profName').value = prof.name || '';
                document.getElementById('profVjudge').value = (prof.handles && prof.handles.vjudge) || '';
                document.getElementById('profCodeforces').value = (prof.handles && prof.handles.codeforces) || '';
                document.getElementById('profAtcoder').value = (prof.handles && prof.handles.atcoder) || '';
                document.getElementById('profCses').value = (prof.handles && prof.handles.cses) || '';
                btnDel.style.display = 'inline-flex';
            }} else {{
                title.innerText = '➕ إنشاء بروفايل متدرب جديد';
                document.getElementById('profId').value = '';
                document.getElementById('profName').value = '';
                document.getElementById('profVjudge').value = '';
                document.getElementById('profCodeforces').value = '';
                document.getElementById('profAtcoder').value = '';
                document.getElementById('profCses').value = '';
                btnDel.style.display = 'none';
            }}
            modal.classList.add('open');
        }}

        function closeProfileModal() {{
            document.getElementById('profileModal').classList.remove('open');
        }}

        function buildInitialUserForProfile(prof, existingUser) {{
            let userObj = existingUser ? JSON.parse(JSON.stringify(existingUser)) : {{
                id: prof.id,
                name: prof.name,
                handles: prof.handles,
                avatar: '',
                is_active_now: false,
                active_platforms_now: [],
                last_seen_str: 'قيد المزامنة السحابية...',
                last_seen_ms: 0,
                last_problem_str: '—',
                all_time_ac: 0,
                today: {{ solved: 0, subs: 0, time_str: '0 دقيقة', time_minutes: 0, sessions: 0 }},
                week: {{ solved: 0, subs: 0, time_str: '0 دقيقة', time_minutes: 0, sessions: 0 }},
                month: {{ solved: 0, subs: 0, time_str: '0 دقيقة', time_minutes: 0, sessions: 0 }},
                peak_hours_str: 'غير محدد',
                platforms: {{}},
                sessions: []
            }};
            userObj.name = prof.name;
            userObj.handles = prof.handles || {{}};
            if (userObj.handles.vjudge && (!userObj.platforms['VJudge'] || userObj.platforms['VJudge'].handle !== userObj.handles.vjudge)) {{
                userObj.platforms['VJudge'] = {{
                    platform: 'VJudge',
                    handle: userObj.handles.vjudge,
                    url: `https://vjudge.net/user/${{userObj.handles.vjudge}}`,
                    extra: 'يُجلب عبر سيرفر GitHub تلقائياً (دورة كل 5-10 دقائق)',
                    is_online: false,
                    last_seen_str: '⏳ في دورة السيرفر القادمة',
                    last_seen_ms: 0,
                    acAll: 0,
                    attAll: 0,
                    today: {{ solved: 0, subs: 0, time_str: '0 د', time_minutes: 0 }},
                    week: {{ solved: 0, subs: 0, time_str: '0 د', time_minutes: 0 }},
                    month: {{ solved: 0, subs: 0, time_str: '0 د', time_minutes: 0 }}
                }};
            }} else if (!userObj.handles.vjudge) {{
                delete userObj.platforms['VJudge'];
            }}
            return userObj;
        }}

        // Clean up legacy bloated localStorage keys (>2.5MB) that caused QuotaExceededError and stuck 4:10 timestamps
        (function cleanupLegacyStorage() {{
            try {{
                let rescuedTrainees = null;
                let rescuedTs = 0;
                const rawV3 = localStorage.getItem('vj_tracker_cloud_state_v3');
                if (rawV3) {{
                    try {{
                        const p3 = JSON.parse(rawV3);
                        let ts3 = p3.ts || 0;
                        if (ts3 > 100000000000) ts3 = Math.floor(ts3 / 1000);
                        if (Array.isArray(p3.trainees) && p3.trainees.length > 0) {{
                            rescuedTrainees = p3.trainees;
                            rescuedTs = ts3;
                        }}
                    }} catch (e) {{}}
                    localStorage.removeItem('vj_tracker_cloud_state_v3');
                }}
                const rawV2 = localStorage.getItem('vj_tracker_cloud_profiles_v2');
                if (rawV2) {{
                    try {{
                        const p2 = JSON.parse(rawV2);
                        let ts2 = p2.ts || 0;
                        if (ts2 > 100000000000) ts2 = Math.floor(ts2 / 1000);
                        if (ts2 > rescuedTs && Array.isArray(p2.trainees) && p2.trainees.length > 0) {{
                            rescuedTrainees = p2.trainees;
                            rescuedTs = ts2;
                        }}
                    }} catch (e) {{}}
                    localStorage.removeItem('vj_tracker_cloud_profiles_v2');
                }}
                localStorage.removeItem('vj_tracker_cloud_profiles_v1');
                if (rescuedTrainees && !localStorage.getItem('vj_tracker_meta_v4')) {{
                    localStorage.setItem('vj_tracker_meta_v4', JSON.stringify({{
                        ts: rescuedTs,
                        updated_ms: 0,
                        updated_at: '',
                        trainees: rescuedTrainees
                    }}));
                }}
            }} catch (e) {{}}
        }})();

        function stampCurrentUpdateTime() {{
            const nowMs = Date.now();
            appState.updated_ms = nowMs;
            appState.updated_at = formatArabicDateJS(nowMs) + ' - ' + formatArabicTimeJS(nowMs) + ' (توقيت مصر)';
        }}

        function saveLocalCache(customTs) {{
            try {{
                let nowSec = customTs || (appState.config && appState.config.last_cloud_sync_ts) || Math.floor(Date.now() / 1000);
                if (nowSec > 100000000000) nowSec = Math.floor(nowSec / 1000);
                const trainees = (appState.config && appState.config.trainees) || [];
                // 1. Always save lightweight metadata (~2KB) FIRST so it never hits QuotaExceededError
                localStorage.setItem('vj_tracker_meta_v4', JSON.stringify({{
                    ts: nowSec,
                    updated_ms: appState.updated_ms || Date.now(),
                    updated_at: appState.updated_at || '',
                    trainees: trainees
                }}));
                // 2. Save compact user stats (~120KB total) with recent 20 sessions per user
                const compactUsersById = {{}};
                (appState.users || []).forEach(u => {{
                    if (u && u.id) {{
                        compactUsersById[u.id] = {{
                            ...u,
                            sessions: (u.sessions || []).slice(0, 20).map(s => ({{
                                ...s,
                                timeline: (s.timeline || []).slice(0, 15)
                            }}))
                        }};
                    }}
                }});
                localStorage.setItem('vj_tracker_users_v4', JSON.stringify(compactUsersById));
            }} catch (e) {{
                console.warn('saveLocalCache warning:', e);
            }}
        }}

        function getLocalCache() {{
            let best = {{ ts: 0, updated_ms: 0, updated_at: '', trainees: null, usersById: {{}} }};
            try {{
                const rawMeta = localStorage.getItem('vj_tracker_meta_v4');
                if (rawMeta) {{
                    const m = JSON.parse(rawMeta);
                    let ts = m.ts || 0;
                    if (ts > 100000000000) ts = Math.floor(ts / 1000);
                    if (Array.isArray(m.trainees) && m.trainees.length > 0) {{
                        best.ts = ts;
                        best.updated_ms = m.updated_ms || 0;
                        best.updated_at = m.updated_at || '';
                        best.trainees = m.trainees;
                    }}
                }}
            }} catch (e) {{}}
            try {{
                const rawUsers = localStorage.getItem('vj_tracker_users_v4');
                if (rawUsers) {{
                    best.usersById = JSON.parse(rawUsers) || {{}};
                }}
            }} catch (e) {{}}
            return best;
        }}

        function applyOverlayToState(targetState, overlayTrainees, overlayUsersById, overlayTs, cacheUpdatedMs = 0, cacheUpdatedAt = '') {{
            if (!targetState || !Array.isArray(overlayTrainees) || overlayTrainees.length === 0) return targetState;
            if (!targetState.config) targetState.config = {{}};
            targetState.config.trainees = overlayTrainees;
            if (overlayTs) {{
                targetState.config.last_cloud_sync_ts = Math.max(targetState.config.last_cloud_sync_ts || 0, overlayTs);
            }}
            const serverUpdatedMs = targetState.updated_ms || 0;
            const isCacheNewer = (cacheUpdatedMs || 0) >= serverUpdatedMs;
            if (isCacheNewer && cacheUpdatedAt) {{
                targetState.updated_ms = cacheUpdatedMs;
                targetState.updated_at = cacheUpdatedAt;
            }}
            const serverUsersMap = {{}};
            (targetState.users || []).forEach(u => {{
                if (u && u.id) serverUsersMap[u.id] = u;
            }});
            const currentUsersMap = {{}};
            (appState && appState.users ? appState.users : []).forEach(u => {{
                if (u && u.id) currentUsersMap[u.id] = u;
            }});
            const mergedUsers = [];
            for (const prof of overlayTrainees) {{
                const sUser = serverUsersMap[prof.id];
                const cUser = (overlayUsersById && overlayUsersById[prof.id]) || currentUsersMap[prof.id];
                if (isCacheNewer && cUser && cUser.sessions && cUser.sessions.length > 0) {{
                    const uCopy = JSON.parse(JSON.stringify(cUser));
                    uCopy.name = prof.name;
                    uCopy.handles = prof.handles;
                    if (sUser && sUser.platforms && sUser.platforms['VJudge']) {{
                        const cVj = uCopy.platforms && uCopy.platforms['VJudge'];
                        if (!cVj || (sUser.platforms['VJudge'].acAll || 0) >= (cVj.acAll || 0)) {{
                            if (!uCopy.platforms) uCopy.platforms = {{}};
                            uCopy.platforms['VJudge'] = sUser.platforms['VJudge'];
                        }}
                    }}
                    mergedUsers.push(uCopy);
                }} else if (sUser) {{
                    const uCopy = JSON.parse(JSON.stringify(sUser));
                    uCopy.name = prof.name;
                    uCopy.handles = prof.handles;
                    if (cUser && cUser.platforms) {{
                        ['Codeforces', 'AtCoder', 'CSES'].forEach(pk => {{
                            if (cUser.platforms[pk] && (!uCopy.platforms[pk] || cUser.platforms[pk].handle === (prof.handles && prof.handles[pk.toLowerCase()]))) {{
                                uCopy.platforms[pk] = cUser.platforms[pk];
                            }}
                        }});
                    }}
                    mergedUsers.push(uCopy);
                }} else if (cUser) {{
                    const uCopy = JSON.parse(JSON.stringify(cUser));
                    uCopy.name = prof.name;
                    uCopy.handles = prof.handles;
                    mergedUsers.push(uCopy);
                }} else {{
                    mergedUsers.push(buildInitialUserForProfile(prof, null));
                }}
            }}
            targetState.users = mergedUsers;
            return targetState;
        }}

        function applyLocalCacheToState(targetState) {{
            const local = getLocalCache();
            const serverTs = (targetState && targetState.config && targetState.config.last_cloud_sync_ts) || 0;
            const serverUpdatedMs = (targetState && targetState.updated_ms) || 0;
            if (local.trainees && (local.ts >= serverTs || (local.updated_ms || 0) >= serverUpdatedMs)) {{
                applyOverlayToState(
                    targetState,
                    local.trainees,
                    local.usersById,
                    Math.max(local.ts || 0, serverTs),
                    local.updated_ms,
                    local.updated_at
                );
            }}
            return targetState;
        }}

        // Immediately apply localStorage cache before the very first render so profiles NEVER vanish on Refresh (F5)
        applyLocalCacheToState(appState);

        async function fetchBrowserLiveStatsForProfile(prof) {{
            const nowMs = Date.now();
            const todayStart = new Date();
            todayStart.setHours(0, 0, 0, 0);
            const todayStartMs = todayStart.getTime();
            const weekStartMs = nowMs - 7 * 86400 * 1000;
            const monthStartMs = nowMs - 30 * 86400 * 1000;

            let existingUser = (appState.users || []).find(u => u.id === prof.id);
            let userObj = buildInitialUserForProfile(prof, existingUser);

            let allEvents = [];

            // Live fetch Codeforces directly in Browser
            const cfHandle = (prof.handles.codeforces || '').trim();
            if (cfHandle) {{
                try {{
                    const infoResp = await fetch(`https://codeforces.com/api/user.info?handles=${{encodeURIComponent(cfHandle)}}`);
                    const infoJson = await infoResp.json();
                    if (infoJson.status === 'OK' && infoJson.result && infoJson.result.length) {{
                        const uInfo = infoJson.result[0];
                        const resolvedHandle = uInfo.handle || cfHandle;
                        const lastOnlineMs = (uInfo.lastOnlineTimeSeconds || 0) * 1000;
                        if (!userObj.avatar && uInfo.titlePhoto) userObj.avatar = uInfo.titlePhoto;

                        const statResp = await fetch(`https://codeforces.com/api/user.status?handle=${{encodeURIComponent(resolvedHandle)}}&from=1&count=200`);
                        const statJson = await statResp.json();
                        const cfSubs = (statJson.status === 'OK' ? statJson.result : []) || [];

                        let cfEvents = cfSubs.map(s => {{
                            const p = s.problem || {{}};
                            const code = `${{p.contestId || ''}}${{p.index || ''}}`;
                            const isAc = s.verdict === 'OK';
                            return {{
                                time: (s.creationTimeSeconds || 0) * 1000,
                                type: 'submission',
                                platform: 'Codeforces',
                                probNum: code,
                                problemName: `${{code}} - ${{p.name || ''}}`,
                                problemUrl: `https://codeforces.com/contest/${{p.contestId}}/problem/${{p.index}}`,
                                status: isAc ? 'Accepted' : (s.verdict || '').replace(/_/g, ' '),
                                is_ac: isAc,
                                difficulty: p.rating || 0
                            }};
                        }});

                        if (lastOnlineMs > 0 && !cfEvents.some(e => Math.abs(e.time - lastOnlineMs) <= 120000)) {{
                            cfEvents.push({{
                                time: lastOnlineMs,
                                type: 'online_ping',
                                platform: 'Codeforces',
                                probNum: 'تصفح المنصة',
                                problemName: '👁️ فاتح كود فورسز (متصل أونلاين)',
                                problemUrl: `https://codeforces.com/profile/${{resolvedHandle}}`,
                                status: 'Online',
                                is_ac: false
                            }});
                        }}

                        allEvents.push(...cfEvents);
                        const cfSessions = clusterEventsJS(cfEvents, 30, 15);
                        const calcP = (thresh) => {{
                            const sIn = cfSessions.filter(s => s.end_ms >= thresh);
                            const eIn = cfEvents.filter(e => e.time >= thresh && e.type === 'submission');
                            const acSet = new Set(eIn.filter(e => e.is_ac).map(e => e.probNum));
                            const mins = sIn.reduce((acc, x) => acc + x.duration_minutes, 0);
                            return {{ solved: acSet.size, subs: eIn.length, time_minutes: mins, time_str: formatDurationJS(mins), sessions: sIn.length }};
                        }};
                        const allAcSet = new Set(cfEvents.filter(e => e.is_ac).map(e => e.probNum));
                        const maxCfMs = Math.max(lastOnlineMs, ...cfEvents.map(e => e.time), 0);
                        const isCfOnline = maxCfMs > 0 && (nowMs - maxCfMs) <= 30 * 60 * 1000;
                        const diffSec = Math.max(0, Math.floor((nowMs - maxCfMs) / 1000));
                        const lastStr = maxCfMs === 0 ? 'لا يوجد' : (diffSec < 60 ? 'متصل الآن' : (diffSec < 3600 ? `منذ ${{Math.floor(diffSec/60)}} د` : (diffSec < 86400 ? `منذ ${{Math.floor(diffSec/3600)}} س` : `منذ ${{Math.floor(diffSec/86400)}} يوم`)));

                        userObj.platforms['Codeforces'] = {{
                            platform: 'Codeforces',
                            handle: resolvedHandle,
                            url: `https://codeforces.com/profile/${{resolvedHandle}}`,
                            extra: uInfo.rating ? `Rating: ${{uInfo.rating}} (${{uInfo.rank}})` : 'Unrated',
                            is_online: isCfOnline,
                            last_seen_str: lastStr,
                            last_seen_ms: maxCfMs,
                            acAll: allAcSet.size,
                            attAll: cfSubs.length,
                            today: calcP(todayStartMs),
                            week: calcP(weekStartMs),
                            month: calcP(monthStartMs)
                        }};
                    }}
                }} catch (err) {{
                    console.warn('CF browser fetch error:', err);
                }}
            }} else {{
                delete userObj.platforms['Codeforces'];
            }}

            // Live fetch AtCoder directly in Browser
            const acHandle = (prof.handles.atcoder || '').trim();
            if (acHandle) {{
                try {{
                    const acResp = await fetch(`https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user=${{encodeURIComponent(acHandle)}}&from_second=0`);
                    const acRaw = await acResp.json();
                    if (Array.isArray(acRaw)) {{
                        acRaw.sort((a, b) => (b.epoch_second || 0) - (a.epoch_second || 0));
                        const acEvents = acRaw.slice(0, 200).map(s => {{
                            const isAc = s.result === 'AC';
                            return {{
                                time: (s.epoch_second || 0) * 1000,
                                type: 'submission',
                                platform: 'AtCoder',
                                probNum: s.problem_id || '',
                                problemName: `${{s.problem_id}} (${{s.contest_id}})`,
                                problemUrl: `https://atcoder.jp/contests/${{s.contest_id}}/tasks/${{s.problem_id}}`,
                                status: isAc ? 'Accepted' : s.result,
                                is_ac: isAc
                            }};
                        }});
                        allEvents.push(...acEvents);
                        const acSessions = clusterEventsJS(acEvents, 30, 15);
                        const calcP = (thresh) => {{
                            const sIn = acSessions.filter(s => s.end_ms >= thresh);
                            const eIn = acEvents.filter(e => e.time >= thresh && e.type === 'submission');
                            const acSet = new Set(eIn.filter(e => e.is_ac).map(e => e.probNum));
                            const mins = sIn.reduce((acc, x) => acc + x.duration_minutes, 0);
                            return {{ solved: acSet.size, subs: eIn.length, time_minutes: mins, time_str: formatDurationJS(mins), sessions: sIn.length }};
                        }};
                        const allAcSet = new Set(acEvents.filter(e => e.is_ac).map(e => e.probNum));
                        const maxAcMs = Math.max(...acEvents.map(e => e.time), 0);
                        const isAcOnline = maxAcMs > 0 && (nowMs - maxAcMs) <= 30 * 60 * 1000;
                        const diffSec = Math.max(0, Math.floor((nowMs - maxAcMs) / 1000));
                        const lastStr = maxAcMs === 0 ? 'لا يوجد' : (diffSec < 60 ? 'متصل الآن' : (diffSec < 3600 ? `منذ ${{Math.floor(diffSec/60)}} د` : (diffSec < 86400 ? `منذ ${{Math.floor(diffSec/3600)}} س` : `منذ ${{Math.floor(diffSec/86400)}} يوم`)));

                        userObj.platforms['AtCoder'] = {{
                            platform: 'AtCoder',
                            handle: acHandle,
                            url: `https://atcoder.jp/users/${{acHandle}}`,
                            extra: '',
                            is_online: isAcOnline,
                            last_seen_str: lastStr,
                            last_seen_ms: maxAcMs,
                            acAll: allAcSet.size,
                            attAll: acEvents.length,
                            today: calcP(todayStartMs),
                            week: calcP(weekStartMs),
                            month: calcP(monthStartMs)
                        }};
                    }}
                }} catch (err) {{
                    console.warn('AtCoder browser fetch error:', err);
                }}
            }} else {{
                delete userObj.platforms['AtCoder'];
            }}

            // Preserve any existing server-fetched VJudge events so merging with live CF/AtCoder works seamlessly
            if (existingUser && Array.isArray(existingUser.sessions) && prof.handles && prof.handles.vjudge) {{
                existingUser.sessions.forEach(s => {{
                    (s.timeline || []).forEach(t => {{
                        if (t.platform === 'VJudge' && t.time) {{
                            allEvents.push({{
                                time: t.time,
                                type: t.type || 'submission',
                                platform: 'VJudge',
                                probNum: t.probNum || '',
                                problemName: t.problemName || t.probNum || '',
                                problemUrl: t.problemUrl || '#',
                                status: t.status || '',
                                is_ac: !!t.is_ac,
                                difficulty: t.difficulty || 0,
                                diff_tier: t.diff_tier || '',
                                prob_points: t.prob_points || 0
                            }});
                        }}
                    }});
                }});
            }}

            if (allEvents.length > 0) {{
                userObj.sessions = clusterEventsJS(allEvents, 30, 15);
                const buildPeriodSummary = (threshMs, periodKey) => {{
                    const sIn = userObj.sessions.filter(s => s.end_ms >= threshMs);
                    const eIn = allEvents.filter(e => e.time >= threshMs && e.type === 'submission');
                    const solved = Object.values(userObj.platforms).reduce((a, p) => a + (p[periodKey] ? p[periodKey].solved : 0), 0);
                    const subs = Math.max(
                        eIn.length,
                        Object.values(userObj.platforms).reduce((a, p) => a + (p[periodKey] ? (p[periodKey].subs || 0) : 0), 0)
                    );
                    const mins = sIn.reduce((a, s) => a + s.duration_minutes, 0);
                    const acMap = {{}};
                    eIn.filter(e => e.is_ac).forEach(e => {{
                        const k = `${{e.platform}}_${{e.probNum || e.problemName}}`;
                        const dInfo = evaluateEventDifficultyJS(e);
                        if (!acMap[k] || dInfo.prob_points > acMap[k].prob_points) acMap[k] = dInfo;
                    }});
                    const acList = Object.values(acMap);
                    const recPts = acList.reduce((a, d) => a + (d.prob_points || 100), 0);
                    const avgPts = acList.length > 0 ? (recPts / acList.length) : 120;
                    const extraSolved = Math.max(0, solved - acList.length);
                    const probPts = Math.round(recPts + extraSolved * avgPts);
                    const avgDiff = acList.length > 0 ? Math.round(acList.reduce((a, d) => a + (d.difficulty || 1000), 0) / acList.length) : 0;
                    const maxDiff = acList.length > 0 ? Math.max(...acList.map(d => d.difficulty || 0)) : 0;
                    return {{
                        solved,
                        subs,
                        time_minutes: mins,
                        time_str: formatDurationJS(mins),
                        sessions: sIn.length,
                        problem_points: probPts,
                        avg_difficulty: avgDiff,
                        max_difficulty: maxDiff,
                        score: calcScoreVal(probPts, subs, mins, sIn.length)
                    }};
                }};
                userObj.today = buildPeriodSummary(todayStartMs, 'today');
                userObj.week = buildPeriodSummary(weekStartMs, 'week');
                userObj.month = buildPeriodSummary(monthStartMs, 'month');

                const latestEv = [...allEvents].sort((a, b) => b.time - a.time)[0];
                if (latestEv) {{
                    userObj.last_problem_str = `[${{latestEv.platform}}] ${{latestEv.problemName || latestEv.probNum}} (${{latestEv.status}})`;
                    userObj.last_problem_url = latestEv.problemUrl || '#';
                }}
            }}

            userObj.active_platforms_now = Object.keys(userObj.platforms).filter(k => userObj.platforms[k].is_online);
            userObj.is_active_now = userObj.active_platforms_now.length > 0;
            userObj.all_time_ac = Object.values(userObj.platforms).reduce((a, p) => a + (p.acAll || 0), 0);
            const latestMs = Math.max(...Object.values(userObj.platforms).map(p => p.last_seen_ms || 0), 0);
            if (latestMs > 0) {{
                const diffSec = Math.max(0, Math.floor((nowMs - latestMs) / 1000));
                userObj.last_seen_str = diffSec < 60 ? 'متصل الآن' : (diffSec < 3600 ? `منذ ${{Math.floor(diffSec/60)}} دقيقة` : (diffSec < 86400 ? `منذ ${{Math.floor(diffSec/3600)}} ساعة` : `منذ ${{Math.floor(diffSec/86400)}} يوم`));
            }}
            return userObj;
        }}

        function clusterEventsJS(events, maxGapMins = 30, codingBuffer = 15) {{
            if (!events || !events.length) return [];
            const sorted = [...events].sort((a, b) => a.time - b.time);
            const groups = [];
            let cur = [sorted[0]];
            for (let i = 1; i < sorted.length; i++) {{
                const gap = (sorted[i].time - cur[cur.length - 1].time) / 60000;
                if (gap <= maxGapMins) cur.push(sorted[i]);
                else {{ groups.push(cur); cur = [sorted[i]]; }}
            }}
            if (cur.length) groups.push(cur);

            return groups.map(grp => {{
                const first = grp[0];
                const last = grp[grp.length - 1];
                const buf = first.type === 'online_ping' ? 5 : codingBuffer;
                const startMs = first.time - buf * 60000;
                const endMs = last.time;
                const durMins = Math.max(5, Math.round((endMs - startMs) / 60000));
                const subs = grp.filter(e => e.type === 'submission');
                const pb = {{}};
                ['VJudge', 'Codeforces', 'AtCoder', 'CSES'].forEach(pk => {{
                    const pe = grp.filter(e => e.platform === pk);
                    if (pe.length) {{
                        const pBuf = pe[0].type === 'online_ping' ? 5 : codingBuffer;
                        const pDur = Math.min(durMins, Math.max(5, Math.round((pe[pe.length - 1].time - (pe[0].time - pBuf * 60000)) / 60000)));
                        pb[pk] = {{
                            duration_minutes: pDur,
                            duration_str: formatDurationJS(pDur),
                            subs_count: pe.filter(e => e.type === 'submission').length,
                            ac_count: pe.filter(e => e.type === 'submission' && e.is_ac).length,
                            pings_count: pe.filter(e => e.type === 'online_ping').length
                        }};
                    }}
                }});
                const dStart = new Date(startMs);
                const yIso = dStart.getFullYear();
                const mIso = String(dStart.getMonth() + 1).padStart(2, '0');
                const dayIso = String(dStart.getDate()).padStart(2, '0');
                const acCount = subs.filter(e => e.is_ac).length;
                const acPtsMap = {{}};
                subs.filter(e => e.is_ac).forEach(e => {{
                    const k = `${{e.platform}}_${{e.probNum || e.problemName}}`;
                    const dInfo = evaluateEventDifficultyJS(e);
                    if (!acPtsMap[k] || dInfo.prob_points > acPtsMap[k]) acPtsMap[k] = dInfo.prob_points;
                }});
                const sessionProbPts = Object.values(acPtsMap).reduce((a, v) => a + v, 0);
                return {{
                    date_iso: `${{yIso}}-${{mIso}}-${{dayIso}}`,
                    month_iso: `${{yIso}}-${{mIso}}`,
                    date_str: formatArabicDateJS(startMs),
                    start_str: formatArabicTimeJS(startMs),
                    end_str: formatArabicTimeJS(endMs),
                    start_ms: startMs,
                    end_ms: endMs,
                    duration_minutes: durMins,
                    duration_str: subs.length === 0 ? `${{formatDurationJS(durMins)}} (فتح وتصفح المنصة)` : `${{formatDurationJS(durMins)}} (اتصال متواصل)`,
                    submissions_count: subs.length,
                    accepted_count: acCount,
                    problem_points: sessionProbPts,
                    score: calcScoreVal(sessionProbPts, subs.length, durMins, 1),
                    platform_breakdown: pb,
                    timeline: [...grp].sort((a, b) => b.time - a.time).map(e => {{
                        const dInfo = evaluateEventDifficultyJS(e);
                        return {{
                            time: e.time,
                            time_str: formatArabicTimeJS(e.time, true),
                            platform: e.platform,
                            type: e.type,
                            probNum: e.probNum,
                            problemName: e.problemName,
                            problemUrl: e.problemUrl,
                            status: e.status,
                            is_ac: e.is_ac,
                            difficulty: dInfo.difficulty,
                            diff_tier: dInfo.diff_tier,
                            prob_points: dInfo.prob_points
                        }};
                    }})
                }};
            }}).sort((a, b) => b.end_ms - a.end_ms);
        }}

        async function syncProfilesToCloud(traineesList) {{
            const nowSec = Math.floor(Date.now() / 1000);
            if (appState && appState.config) {{
                appState.config.trainees = traineesList;
                appState.config.last_cloud_sync_ts = Math.max(appState.config.last_cloud_sync_ts || 0, nowSec);
            }}
            saveLocalCache(nowSec);

            const topic = (appState.config && appState.config.cloud_sync_topic) || 'vj_tracker_bodesaber_sync_v2';
            try {{
                const resp = await fetch(`https://ntfy.sh/${{topic}}`, {{
                    method: 'POST',
                    body: JSON.stringify({{
                        action: 'update_profiles',
                        timestamp: nowSec,
                        trainees: traineesList
                    }})
                }});
                if (resp.ok) {{
                    try {{
                        const rJson = await resp.json();
                        if (rJson && rJson.time) {{
                            const srvTs = Math.max(nowSec, rJson.time);
                            appState.config.last_cloud_sync_ts = srvTs;
                            saveLocalCache(srvTs);
                        }}
                    }} catch (e) {{}}
                }}
                showToast('☁️ تم حفظ البروفايل في السحابة 24/7 وتحديث البيانات فوراً!');
            }} catch (e) {{
                console.warn('Cloud sync post warning:', e);
                showToast('✅ تم حفظ البروفايل وتحديث البيانات!');
            }}
        }}

        async function loadCloudSyncedProfiles(forceRefetchAll = false) {{
            const topic = (appState.config && appState.config.cloud_sync_topic) || 'vj_tracker_bodesaber_sync_v2';
            let bestTs = (appState.config && appState.config.last_cloud_sync_ts) || 0;
            let bestTrainees = null;
            const localCache = getLocalCache();

            // 1. Check localStorage first
            if (localCache.trainees && localCache.ts >= bestTs) {{
                bestTs = localCache.ts;
                bestTrainees = localCache.trainees;
            }}

            // 2. Check ntfy.sh cloud storage (24h history across all devices/browsers)
            try {{
                const resp = await fetch(`https://ntfy.sh/${{topic}}/json?poll=1&since=24h`, {{ cache: 'no-store' }});
                if (resp.ok) {{
                    const text = await resp.text();
                    const lines = text.trim().split('\\n');
                    for (const line of lines) {{
                        if (!line.trim()) continue;
                        try {{
                            const msgObj = JSON.parse(line);
                            if (msgObj.event === 'message' && msgObj.time >= bestTs) {{
                                const payload = JSON.parse(msgObj.message || '{{}}');
                                if (payload.action === 'update_profiles' && Array.isArray(payload.trainees) && payload.trainees.length > 0) {{
                                    bestTs = msgObj.time;
                                    bestTrainees = payload.trainees;
                                }}
                            }}
                        }} catch (err) {{}}
                    }}
                }}
            }} catch (e) {{}}

            if (!bestTrainees && appState.config && Array.isArray(appState.config.trainees)) {{
                bestTrainees = appState.config.trainees;
            }}

            if (bestTrainees) {{
                applyOverlayToState(appState, bestTrainees, localCache.usersById, bestTs, localCache.updated_ms, localCache.updated_at);
                saveLocalCache(bestTs);
                renderDashboard();

                const toFetch = bestTrainees.filter(prof => {{
                    const existingU = (appState.users || []).find(u => u.id === prof.id);
                    const needsCf = prof.handles && prof.handles.codeforces && (!existingU || !existingU.platforms || !existingU.platforms['Codeforces']);
                    const needsAc = prof.handles && prof.handles.atcoder && (!existingU || !existingU.platforms || !existingU.platforms['AtCoder']);
                    const needsSessions = (prof.handles && (prof.handles.codeforces || prof.handles.atcoder)) && (!existingU || !existingU.sessions || existingU.sessions.length === 0);
                    return forceRefetchAll || needsCf || needsAc || needsSessions;
                }});

                const batchSize = 4;
                for (let i = 0; i < toFetch.length; i += batchSize) {{
                    const batch = toFetch.slice(i, i + batchSize);
                    const updatedBatch = await Promise.all(batch.map(prof => fetchBrowserLiveStatsForProfile(prof)));
                    updatedBatch.forEach(updatedU => {{
                        if (!updatedU) return;
                        const idx = appState.users.findIndex(u => u.id === updatedU.id);
                        if (idx >= 0) appState.users[idx] = updatedU;
                        else appState.users.push(updatedU);
                    }});
                    stampCurrentUpdateTime();
                    saveLocalCache(bestTs);
                    renderDashboard();
                }}
            }}
        }}

        async function saveProfileFromModal(e) {{
            e.preventDefault();
            const btn = document.getElementById('btnSaveProfile');
            btn.disabled = true;
            btn.innerText = '⏳ جاري الحفظ السحابي والربط...';

            const idInput = document.getElementById('profId').value.trim();
            const nameInput = document.getElementById('profName').value.trim();
            const vjInput = document.getElementById('profVjudge').value.trim();
            const cfInput = document.getElementById('profCodeforces').value.trim();
            const acInput = document.getElementById('profAtcoder').value.trim();
            const csesInput = document.getElementById('profCses').value.trim();

            if (!vjInput && !cfInput && !acInput && !csesInput) {{
                alert('يرجى إدخال هاندل واحد على الأقل في أي منصة (VJudge أو Codeforces أو AtCoder أو CSES).');
                btn.disabled = false;
                btn.innerText = '💾 حفظ سحابي وبدء التتبع فوراً';
                return;
            }}

            let trainees = appState.config.trainees || [];
            const pid = idInput || ('user_' + Date.now());
            const newProf = {{
                id: pid,
                name: nameInput,
                handles: {{
                    vjudge: vjInput,
                    codeforces: cfInput,
                    atcoder: acInput,
                    cses: csesInput
                }}
            }};

            const existingIdx = trainees.findIndex(t => t.id === pid);
            if (existingIdx >= 0) trainees[existingIdx] = newProf;
            else trainees.push(newProf);
            appState.config.trainees = trainees;

            // 1. Immediately create/update user card & save to localStorage BEFORE any network await
            const existingUser = (appState.users || []).find(u => u.id === pid);
            const initialUserObj = buildInitialUserForProfile(newProf, existingUser);
            const uIdx0 = (appState.users || []).findIndex(u => u.id === pid);
            if (uIdx0 >= 0) appState.users[uIdx0] = initialUserObj;
            else appState.users.push(initialUserObj);

            const nowSec = Math.floor(Date.now() / 1000);
            appState.config.last_cloud_sync_ts = Math.max(appState.config.last_cloud_sync_ts || 0, nowSec);
            stampCurrentUpdateTime();
            saveLocalCache(nowSec);
            renderDashboard();
            closeProfileModal();

            btn.disabled = false;
            btn.innerText = '💾 حفظ سحابي وبدء التتبع فوراً';

            // 2. Sync to ntfy.sh cloud and fetch live stats in parallel, saving full stats to localStorage when done
            syncProfilesToCloud(trainees);
            const updatedUserObj = await fetchBrowserLiveStatsForProfile(newProf);
            const uIdx = (appState.users || []).findIndex(u => u.id === pid);
            if (uIdx >= 0) appState.users[uIdx] = updatedUserObj;
            else appState.users.push(updatedUserObj);
            stampCurrentUpdateTime();
            saveLocalCache(appState.config.last_cloud_sync_ts);
            renderDashboard();
        }}

        async function deleteCurrentProfile() {{
            const pid = document.getElementById('profId').value.trim();
            if (!pid) return;
            if (!confirm('هل أنت متأكد من حذف هذا البروفايل من المتابعة؟')) return;

            appState.config.trainees = (appState.config.trainees || []).filter(t => t.id !== pid);
            appState.users = (appState.users || []).filter(u => u.id !== pid);
            const nowSec = Math.floor(Date.now() / 1000);
            appState.config.last_cloud_sync_ts = Math.max(appState.config.last_cloud_sync_ts || 0, nowSec);
            stampCurrentUpdateTime();
            saveLocalCache(nowSec);
            renderDashboard();
            closeProfileModal();
            await syncProfilesToCloud(appState.config.trainees);
        }}

        async function triggerLiveRefresh() {{
            const btn = document.getElementById('btnLiveRefresh');
            btn.disabled = true;
            btn.innerText = '⏳ جاري التحديث السحابي...';
            showToast('🔄 جاري جلب أحدث البيانات السحابية وفحص حالة الاتصال...');

            // Immediately stamp current time and persist to localStorage so even an instant F5 refresh never reverts the time
            stampCurrentUpdateTime();
            saveLocalCache(appState.config && appState.config.last_cloud_sync_ts);
            renderDashboard();

            // 1. Fetch latest data.json from GitHub Pages cloud & merge local cache so added profiles never disappear
            try {{
                const r = await fetch('data.json?t=' + Date.now(), {{ cache: 'no-store' }});
                if (r.ok) {{
                    const d = await r.json();
                    if (d && d.users) {{
                        appState = applyLocalCacheToState(d);
                        renderDashboard();
                    }}
                }}
            }} catch (e) {{}}

            // 2. Merge any newer cloud-synced profile changes from ntfy.sh / localStorage and force live refresh
            await loadCloudSyncedProfiles(true);

            stampCurrentUpdateTime();
            saveLocalCache(appState.config && appState.config.last_cloud_sync_ts);
            renderDashboard();
            showToast('✅ تم تحديث كافة المنصات سحابياً بنجاح!');
            btn.disabled = false;
            btn.innerText = '🔄 تحديث البيانات الآن';
        }}

        // On Page Load: localStorage cache is already applied synchronously; render immediately, then sync data.json & cloud
        window.addEventListener('DOMContentLoaded', async () => {{
            renderDashboard();
            try {{
                const r = await fetch('data.json?t=' + Date.now(), {{ cache: 'no-store' }});
                if (r.ok) {{
                    const d = await r.json();
                    if (d && d.users) {{
                        appState = applyLocalCacheToState(d);
                        renderDashboard();
                    }}
                }}
            }} catch (e) {{}}
            const isStale = (Date.now() - (appState.updated_ms || 0)) > 60 * 1000;
            if (isStale) {{
                stampCurrentUpdateTime();
                saveLocalCache(appState.config && appState.config.last_cloud_sync_ts);
                renderDashboard();
            }}
            await loadCloudSyncedProfiles(isStale);
        }});

        // 5-minute Countdown Timer
        let secondsLeft = 300;
        const countdownEl = document.getElementById('countdown');
        setInterval(() => {{
            secondsLeft--;
            if (secondsLeft <= 0) {{
                secondsLeft = 300;
                triggerLiveRefresh();
            }} else {{
                const m = Math.floor(secondsLeft / 60);
                const s = secondsLeft % 60;
                countdownEl.innerText = `التحديث القادم خلال: ${{String(m).padStart(2, '0')}}:${{String(s).padStart(2, '0')}}`;
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

def run_once():
    config = tc.load_config()
    config = tc.sync_profiles_from_cloud(config)
    trainees = config.get("trainees", [])
    gap_min = config.get("session_gap_minutes", 30)
    buffer_min = config.get("coding_buffer_minutes", 15)
    limit = config.get("fetch_limit", 200)

    pings_history = tc.load_pings_history()
    print(f"[*] Starting 24/7 Cloud multi-platform analysis for {len(trainees)} trainee profiles...")
    users_data = []

    for prof in trainees:
        print(f"  -> Analyzing profile: {prof['name']} ({prof['handles']})...")
        stats = tc.analyze_trainee_profile(
            prof,
            pings_history,
            session_gap_min=gap_min,
            coding_buffer=buffer_min,
            fetch_limit=limit
        )
        users_data.append(stats)
        time.sleep(0.3)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    tc.save_pings_history(pings_history)

    print("[*] Generating HTML dashboard, data.json, CSV, and Markdown reports...")
    generate_html_dashboard(users_data, config)
    generate_csv_report(users_data)
    generate_markdown_report(users_data)
    print("[✓] All reports generated successfully!")
    return users_data, config

if __name__ == "__main__":
    run_once()
