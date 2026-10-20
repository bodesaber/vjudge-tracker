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
    lines = [
        "# 📊 تقرير متابعة نشاط المتدربين الشامل 24/7 (VJudge + Codeforces + AtCoder + CSES)",
        f"**تاريخ التحديث:** {now_str} (بتوقيت مصر - قاعدة الـ 30 دقيقة للاتصال المتواصل)",
        "",
        "## 1. ملخص البروفايلات والنشاط العام",
        "| المتدرب | الحالة | آخر ظهور | اليوم | آخر 7 أيام | آخر 30 يوماً | المنصات المربوطة |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]
    for u in users_data:
        status_icon = f"🟢 متصل ({', '.join(u['active_platforms_now'])})" if u["is_active_now"] else "⚪ غير متصل"
        plats_info = ", ".join([f"{pk}: `{pv['handle']}` ({pv['acAll']} AC)" for pk, pv in u["platforms"].items()])
        lines.append(
            f"| **{u['name']}** | {status_icon} | {u['last_seen_str']} | **{u['today']['solved']} AC** ({u['today']['time_str']}) | **{u['week']['solved']} AC** ({u['week']['time_str']}) | **{u['month']['solved']} AC** ({u['month']['time_str']}) | {plats_info} |"
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
                <p>تعمل 24 ساعة في السحاب بالكامل بدون الحاجة لجهازك — إدارة البروفايلات وربط المنصات مباشرة من المتصفح</p>
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
                ☁️ <strong>تعمل سحابياً 24/7 (Cloud Native):</strong> هذه المنصة تعمل على سيرفرات السحابة على مدار 24 ساعة حتى وجهازك مغلق تماماً. يمكنك إضافة متدرب أو ربط حساباته عبر (<strong>VJudge و Codeforces و AtCoder و CSES</strong>) من زر <strong>"🔗 ربط / تعديل المنصات"</strong>، ويتم حفظها في السحابة فوراً وتطبيق قاعدة الـ <strong>30 دقيقة</strong> للجلسات المتصلة.
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

        function renderDashboard() {{
            const users = appState.users || [];
            document.getElementById('lastUpdateText').innerText = '🕒 آخر تحديث: ' + (appState.updated_at || '');

            const cardsGrid = document.getElementById('cardsGrid');
            cardsGrid.innerHTML = users.map(u => {{
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
                                <h3 class="user-title">${{u.name}}</h3>
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
                        </div>
                        <div class="matrix-cell">
                            <span class="matrix-title">🗓️ آخر 7 أيام (كل المنصات)</span>
                            <div class="matrix-val text-primary">${{u.week.time_str}}</div>
                            <div class="matrix-sub">حل ${{u.week.solved}} مسائل AC (${{u.week.sessions}} جلسات)</div>
                        </div>
                        <div class="matrix-cell">
                            <span class="matrix-title">📊 آخر 30 يوماً (كل المنصات)</span>
                            <div class="matrix-val text-purple">${{u.month.time_str}}</div>
                            <div class="matrix-sub">حل ${{u.month.solved}} مسائل AC (${{u.month.sessions}} جلسة)</div>
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
                        <span style="color:#b45309;font-weight:700;">🏆 الإجمالي الموحد: ${{u.all_time_ac}} مسألة AC</span>
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
                    if (t.type === 'online_ping') {{
                        statusBadge = `<span class="badge badge-ping">👁️ متصل أونلاين</span>`;
                    }} else if (t.is_ac) {{
                        statusBadge = `<span class="badge badge-ac">✅ ${{t.status}}</span>`;
                    }} else {{
                        statusBadge = `<span class="badge badge-wa">❌ ${{t.status}}</span>`;
                    }}
                    return `
                        <div class="timeline-item">
                            <span class="timeline-time">${{t.time_str}}</span>
                            <span class="plat-tag plat-${{t.platform}}">${{t.platform}}</span>
                            <a href="${{t.problemUrl}}" target="_blank" style="color:#0f172a;font-weight:600;text-decoration:none;flex:1;">${{t.problemName}}</a>
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

        async function fetchBrowserLiveStatsForProfile(prof) {{
            const nowMs = Date.now();
            const todayStart = new Date();
            todayStart.setHours(0, 0, 0, 0);
            const todayStartMs = todayStart.getTime();
            const weekStartMs = nowMs - 7 * 86400 * 1000;
            const monthStartMs = nowMs - 30 * 86400 * 1000;

            let existingUser = (appState.users || []).find(u => u.id === prof.id);
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
            userObj.handles = prof.handles;

            if (prof.handles.vjudge && (!userObj.platforms['VJudge'] || userObj.platforms['VJudge'].handle !== prof.handles.vjudge)) {{
                userObj.platforms['VJudge'] = {{
                    platform: 'VJudge',
                    handle: prof.handles.vjudge,
                    url: `https://vjudge.net/user/${{prof.handles.vjudge}}`,
                    extra: 'تتم المزامنة عبر السيرفر السحابي 24/7',
                    is_online: false,
                    last_seen_str: 'قيد الجلب السحابي',
                    last_seen_ms: 0,
                    acAll: 0,
                    attAll: 0,
                    today: {{ solved: 0, subs: 0, time_str: '0 د', time_minutes: 0 }},
                    week: {{ solved: 0, subs: 0, time_str: '0 د', time_minutes: 0 }},
                    month: {{ solved: 0, subs: 0, time_str: '0 د', time_minutes: 0 }}
                }};
            }} else if (!prof.handles.vjudge) {{
                delete userObj.platforms['VJudge'];
            }}

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
                                is_ac: isAc
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

            if (allEvents.length > 0 && (!existingUser || !prof.handles.vjudge)) {{
                userObj.sessions = clusterEventsJS(allEvents, 30, 15);
                const sToday = userObj.sessions.filter(s => s.end_ms >= todayStartMs);
                const sWeek = userObj.sessions.filter(s => s.end_ms >= weekStartMs);
                const sMonth = userObj.sessions.filter(s => s.end_ms >= monthStartMs);
                userObj.today = {{
                    solved: Object.values(userObj.platforms).reduce((a, p) => a + (p.today ? p.today.solved : 0), 0),
                    subs: allEvents.filter(e => e.time >= todayStartMs && e.type === 'submission').length,
                    time_minutes: sToday.reduce((a, s) => a + s.duration_minutes, 0),
                    time_str: formatDurationJS(sToday.reduce((a, s) => a + s.duration_minutes, 0)),
                    sessions: sToday.length
                }};
                userObj.week = {{
                    solved: Object.values(userObj.platforms).reduce((a, p) => a + (p.week ? p.week.solved : 0), 0),
                    subs: allEvents.filter(e => e.time >= weekStartMs && e.type === 'submission').length,
                    time_minutes: sWeek.reduce((a, s) => a + s.duration_minutes, 0),
                    time_str: formatDurationJS(sWeek.reduce((a, s) => a + s.duration_minutes, 0)),
                    sessions: sWeek.length
                }};
                userObj.month = {{
                    solved: Object.values(userObj.platforms).reduce((a, p) => a + (p.month ? p.month.solved : 0), 0),
                    subs: allEvents.filter(e => e.time >= monthStartMs && e.type === 'submission').length,
                    time_minutes: sMonth.reduce((a, s) => a + s.duration_minutes, 0),
                    time_str: formatDurationJS(sMonth.reduce((a, s) => a + s.duration_minutes, 0)),
                    sessions: sMonth.length
                }};
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
                return {{
                    date_str: formatArabicDateJS(startMs),
                    start_str: formatArabicTimeJS(startMs),
                    end_str: formatArabicTimeJS(endMs),
                    start_ms: startMs,
                    end_ms: endMs,
                    duration_minutes: durMins,
                    duration_str: subs.length === 0 ? `${{formatDurationJS(durMins)}} (فتح وتصفح المنصة)` : `${{formatDurationJS(durMins)}} (اتصال متواصل)`,
                    submissions_count: subs.length,
                    accepted_count: subs.filter(e => e.is_ac).length,
                    platform_breakdown: pb,
                    timeline: [...grp].sort((a, b) => b.time - a.time).map(e => ({{
                        time_str: formatArabicTimeJS(e.time, true),
                        platform: e.platform,
                        type: e.type,
                        probNum: e.probNum,
                        problemName: e.problemName,
                        problemUrl: e.problemUrl,
                        status: e.status,
                        is_ac: e.is_ac
                    }}))
                }};
            }}).sort((a, b) => b.end_ms - a.end_ms);
        }}

        async function syncProfilesToCloud(traineesList) {{
            const nowSec = Math.floor(Date.now() / 1000);
            localStorage.setItem('vj_tracker_cloud_profiles_v2', JSON.stringify({{
                ts: nowSec,
                trainees: traineesList
            }}));

            const topic = (appState.config && appState.config.cloud_sync_topic) || 'vj_tracker_bodesaber_sync_v2';
            try {{
                await fetch(`https://ntfy.sh/${{topic}}`, {{
                    method: 'POST',
                    body: JSON.stringify({{
                        action: 'update_profiles',
                        timestamp: nowSec,
                        trainees: traineesList
                    }})
                }});
                showToast('☁️ تم حفظ البروفايل في السحابة 24/7 وتحديث البيانات فوراً!');
            }} catch (e) {{
                console.warn('Cloud sync post warning:', e);
                showToast('✅ تم حفظ البروفايل وتحديث البيانات!');
            }}
        }}

        async function loadCloudSyncedProfiles() {{
            const topic = (appState.config && appState.config.cloud_sync_topic) || 'vj_tracker_bodesaber_sync_v2';
            let bestTs = (appState.config && appState.config.last_cloud_sync_ts) || 0;
            let bestTrainees = null;

            // 1. Check localStorage first
            try {{
                const localRaw = localStorage.getItem('vj_tracker_cloud_profiles_v2');
                if (localRaw) {{
                    const parsed = JSON.parse(localRaw);
                    if (parsed.ts > bestTs && Array.isArray(parsed.trainees)) {{
                        bestTs = parsed.ts;
                        bestTrainees = parsed.trainees;
                    }}
                }}
            }} catch (e) {{}}

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
                            if (msgObj.event === 'message' && msgObj.time > bestTs) {{
                                const payload = JSON.parse(msgObj.message || '{{}}');
                                if (payload.action === 'update_profiles' && Array.isArray(payload.trainees)) {{
                                    bestTs = msgObj.time;
                                    bestTrainees = payload.trainees;
                                }}
                            }}
                        }} catch (err) {{}}
                    }}
                }}
            }} catch (e) {{}}

            if (bestTrainees) {{
                appState.config.trainees = bestTrainees;
                appState.config.last_cloud_sync_ts = bestTs;
                // Keep only users in bestTrainees and fetch any newly added/updated profiles
                const validIds = new Set(bestTrainees.map(t => t.id));
                appState.users = (appState.users || []).filter(u => validIds.has(u.id));
                for (const prof of bestTrainees) {{
                    const updatedU = await fetchBrowserLiveStatsForProfile(prof);
                    const idx = appState.users.findIndex(u => u.id === prof.id);
                    if (idx >= 0) appState.users[idx] = updatedU;
                    else appState.users.push(updatedU);
                }}
                renderDashboard();
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

            const updatedUserObj = await fetchBrowserLiveStatsForProfile(newProf);
            const uIdx = (appState.users || []).findIndex(u => u.id === pid);
            if (uIdx >= 0) appState.users[uIdx] = updatedUserObj;
            else appState.users.push(updatedUserObj);

            renderDashboard();
            closeProfileModal();
            await syncProfilesToCloud(trainees);

            btn.disabled = false;
            btn.innerText = '💾 حفظ سحابي وبدء التتبع فوراً';
        }}

        async function deleteCurrentProfile() {{
            const pid = document.getElementById('profId').value.trim();
            if (!pid) return;
            if (!confirm('هل أنت متأكد من حذف هذا البروفايل من المتابعة؟')) return;

            appState.config.trainees = (appState.config.trainees || []).filter(t => t.id !== pid);
            appState.users = (appState.users || []).filter(u => u.id !== pid);
            renderDashboard();
            closeProfileModal();
            await syncProfilesToCloud(appState.config.trainees);
        }}

        async function triggerLiveRefresh() {{
            const btn = document.getElementById('btnLiveRefresh');
            btn.disabled = true;
            btn.innerText = '⏳ جاري التحديث السحابي...';
            showToast('🔄 جاري جلب أحدث البيانات السحابية وفحص حالة الاتصال...');

            // 1. Fetch latest data.json from GitHub Pages cloud
            try {{
                const r = await fetch('data.json?t=' + Date.now(), {{ cache: 'no-store' }});
                if (r.ok) {{
                    const d = await r.json();
                    if (d && d.users) appState = d;
                }}
            }} catch (e) {{}}

            // 2. Merge any newer cloud-synced profile changes from ntfy.sh / localStorage
            await loadCloudSyncedProfiles();

            // 3. Also refresh live Codeforces & AtCoder status directly in browser
            const trainees = appState.config.trainees || [];
            for (let i = 0; i < trainees.length; i++) {{
                const updatedU = await fetchBrowserLiveStatsForProfile(trainees[i]);
                const idx = appState.users.findIndex(u => u.id === trainees[i].id);
                if (idx >= 0) appState.users[idx] = updatedU;
                else appState.users.push(updatedU);
            }}
            appState.updated_at = formatArabicDateJS(Date.now()) + ' - ' + formatArabicTimeJS(Date.now()) + ' (توقيت مصر)';
            renderDashboard();
            showToast('✅ تم تحديث كافة المنصات سحابياً بنجاح!');
            btn.disabled = false;
            btn.innerText = '🔄 تحديث البيانات الآن';
        }}

        // On Page Load: render immediately, then sync latest data.json & cloud profiles
        window.addEventListener('DOMContentLoaded', async () => {{
            renderDashboard();
            try {{
                const r = await fetch('data.json?t=' + Date.now(), {{ cache: 'no-store' }});
                if (r.ok) {{
                    const d = await r.json();
                    if (d && d.updated_ms >= (appState.updated_ms || 0)) {{
                        appState = d;
                        renderDashboard();
                    }}
                }}
            }} catch (e) {{}}
            await loadCloudSyncedProfiles();
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
