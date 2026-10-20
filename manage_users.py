import os
import sys
import json
import urllib.request
import re
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
TRACKER_SCRIPT = os.path.join(SCRIPT_DIR, "tracker.py")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"trainees": []}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def verify_vjudge_handle(handle):
    url = f"https://vjudge.net/user/{handle}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r'id=["\']profile-header-data["\']>(.*?)</script>', html)
            if m:
                data = json.loads(m.group(1))
                return True, data.get("counts", {}).get("acAll", 0)
    except Exception:
        pass
    return False, 0

def add_trainee(handle):
    handle = handle.strip()
    if not handle:
        print("[!] خطأ: لم يتم إدخال اسم مستخدم.")
        return

    cfg = load_config()
    trainees = cfg.get("trainees", [])

    # Check if handle already exists
    existing_handles = []
    for t in trainees:
        if isinstance(t, str):
            existing_handles.append(t.lower())
        elif isinstance(t, dict):
            existing_handles.append(t.get("vjudge", "").lower())

    if handle.lower() in existing_handles:
        print(f"[!] المتدرب '{handle}' موجود بالفعل في قائمة المتابعة.")
        return

    print(f"[*] جاري التحقق من حساب '{handle}' على VJudge...")
    exists, ac_count = verify_vjudge_handle(handle)
    if exists:
        print(f"[✓] تم العثور على الحساب بنجاح! (إجمالي المسائل المحلولة: {ac_count})")
    else:
        print(f"[?] تحذير: لم نتمكن من التحقق من وجود الحساب على VJudge (قد يكون الاسم مكتوباً بشكل غير دقيق).")
        choice = input("هل ترغب في إضافته على أي حال؟ (y/n): ").strip().lower()
        if choice not in ("y", "yes", "نعم"):
            print("[-] تم إلغاء الإضافة.")
            return

    # Add to trainees list
    trainees.append(handle)
    cfg["trainees"] = trainees
    save_config(cfg)
    print(f"[✓] تمت إضافة '{handle}' إلى ملف الإعدادات بنجاح.")

    # Run tracker immediately to update dashboard
    print("[*] جاري سحب بيانات المتدرب وتحديث لوحة التحكم...")
    try:
        subprocess.run([sys.executable, TRACKER_SCRIPT], check=True)
    except Exception as e:
        print(f"[!] تحذير أثناء تشغيل السكريبت: {e}")

    # Auto push to GitHub
    sync_to_github(f"Add new trainee: {handle}")

def remove_trainee(handle):
    handle = handle.strip()
    cfg = load_config()
    trainees = cfg.get("trainees", [])
    new_trainees = []
    found = False

    for t in trainees:
        t_name = t if isinstance(t, str) else t.get("vjudge", "")
        if t_name.lower() == handle.lower():
            found = True
        else:
            new_trainees.append(t)

    if not found:
        print(f"[!] المتدرب '{handle}' غير موجود في القائمة.")
        return

    cfg["trainees"] = new_trainees
    save_config(cfg)
    print(f"[✓] تم حذف '{handle}' من قائمة المتابعة بنجاح.")

    # Rebuild dashboard
    subprocess.run([sys.executable, TRACKER_SCRIPT], check=True)
    sync_to_github(f"Remove trainee: {handle}")

def list_trainees():
    cfg = load_config()
    trainees = cfg.get("trainees", [])
    print(f"\nقائمة المتدربين الحالية ({len(trainees)} متدرب):")
    print("=" * 40)
    for i, t in enumerate(trainees, 1):
        name = t if isinstance(t, str) else t.get("vjudge", t.get("name", "Unknown"))
        print(f"{i}. {name}")
    print("=" * 40)

def sync_to_github(commit_msg):
    try:
        print("[*] جاري رفع التحديثات إلى GitHub لتفعيل المراقبة السحابية 24/7...")
        subprocess.run(["git", "add", "."], cwd=SCRIPT_DIR, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=SCRIPT_DIR, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "push", "origin", "main"], cwd=SCRIPT_DIR, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[✓] تم الرفع إلى GitHub بنجاح! السيرفرات السحابية تتابع المتدرب الجديد الآن.")
    except Exception as e:
        print(f"[-] ملاحظة: لم يتم الرفع تلقائياً ({e}). يمكنك عمل git push يدوياً.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ("add", "-a", "+"):
            if len(sys.argv) > 2:
                add_trainee(sys.argv[2])
            else:
                h = input("ادخل اسم الـ Handle للمتدرب الجديد: ")
                add_trainee(h)
        elif cmd in ("remove", "rm", "delete", "-d"):
            if len(sys.argv) > 2:
                remove_trainee(sys.argv[2])
            else:
                h = input("ادخل اسم الـ Handle المراد حذفه: ")
                remove_trainee(h)
        elif cmd in ("list", "ls"):
            list_trainees()
        else:
            # treat as handle directly to add
            add_trainee(sys.argv[1])
    else:
        print("\n--- إدارة المتدربين على VJudge Tracker ---")
        print("1. إضافة متدرب جديد (Add)")
        print("2. حذف متدرب (Remove)")
        print("3. عرض قائمة المتدربين (List)")
        choice = input("اختر رقم العملية (1-3): ").strip()
        if choice == "1":
            h = input("ادخل اسم الـ Handle للمتدرب الجديد على VJudge: ")
            add_trainee(h)
        elif choice == "2":
            h = input("ادخل اسم الـ Handle المراد حذفه: ")
            remove_trainee(h)
        elif choice == "3":
            list_trainees()
