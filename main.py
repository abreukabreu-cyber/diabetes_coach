from flask import Flask, render_template, request, redirect, url_for, session
import os, sqlite3, json

APP_SECRET = os.environ.get("APP_SECRET", "dev-secret-change-me")
ADMIN_CODE = os.environ.get("ADMIN_CODE", "ADMIN-123")
PREMIUM_CODE = os.environ.get("PREMIUM_CODE", "PREMIUM-123")
DB_PATH = os.environ.get("DB_PATH", "progress.db")
TASKS_PATH = os.environ.get("TASKS_PATH", "tasks.json")
CHECKOUT_LINK = os.environ.get("CHECKOUT_LINK", "")

app = Flask(__name__)
app.secret_key = APP_SECRET

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS progress (
        user TEXT NOT NULL,
        week INTEGER NOT NULL,
        day INTEGER NOT NULL,
        completed INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (user, week, day)
    )
    """)
    conn.commit()
    conn.close()

def load_tasks():
    if not os.path.exists(TASKS_PATH):
        return {"weeks": {}}
    with open(TASKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_tasks(data):
    with open(TASKS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_completed_days(user, week):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS n FROM progress WHERE user=? AND week=? AND completed=1", (user, week))
    n = c.fetchone()["n"]
    conn.close()
    return n

def mark_day_complete(user, week, day):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO progress (user, week, day, completed) VALUES (?, ?, ?, 1)",
              (user, week, day))
    conn.commit()
    conn.close()

def setup():

    init_db()
    if not os.path.exists(TASKS_PATH):
        default = {
            "weeks": {
                "1": [
                    ["Drink warm water on waking", "5 min morning light", "Optional: note fasting glucose"],
                    ["5-min walk after lunch", "Swap sweet chai for unsweetened tea", "Plate 50/25/25 at main meal"],
                    ["Add cinnamon to a snack", "Yogurt + cucumber or peanuts", "Extra 500 ml water today"],
                    ["Reduce rice by 25% (smaller cup)", "Start meal with salad/veggies", "5-min walk after dinner"],
                    ["Dal with extra veggies", "Use ghee instead of refined oil", "Sleep 30 min earlier"],
                    ["Try a millet (ragi/bajra) once", "Add protein: paneer or eggs", "Hydration check: pale urine"],
                    ["Review the week", "Prepare next week's shopping list", "Gentle 10-min walk"]
                ],
                "2": [
                    ["5-min walk after 2 meals", "Track steps (manual)", "Stretch calves 2×"],
                    ["Chair sit-to-stand 2×10", "Slow chewing (10+ chews/bite)", "Add raw veg before carbs"],
                    ["Swap fruit juice for whole fruit", "Salt lassi unsweetened", "Sleep routine: fixed hour"],
                    ["Veg stir-fry in ghee", "Half-plate veggies at lunch", "Breathing 3×1 min"],
                    ["Egg bhurji or paneer bhurji", "Spices: fenugreek + turmeric", "Post-dinner stroll"],
                    ["Try brown rice or millet", "Protein at breakfast", "Hydration timer 3×"],
                    ["Reflect: best habit", "Plan 2 easy dinners", "10-min walk with family"]
                ]
            }
        }
        save_tasks(default)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            return render_template("login.html", error="Enter a valid email.")
        session["user"] = email
        return redirect(url_for("home"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    user = session["user"]
    tasks = load_tasks()
    week = 1
    week_key = str(week)
    week_tasks = tasks.get("weeks", {}).get(week_key, [])
    completed = get_completed_days(user, week)
    day = min(completed + 1, 7) if week_tasks else 1
    current_tasks = week_tasks[day-1] if week_tasks else []
    progress_pct = int((completed / 7) * 100) if week_tasks else 0
    return render_template("home.html",
                           user=user,
                           week=week,
                           day=day,
                           tasks=current_tasks,
                           completed=completed,
                           progress_pct=progress_pct)

@app.route("/complete_day", methods=["POST"])
def complete_day():
    if "user" not in session:
        return redirect(url_for("login"))
    user = session["user"]
    week = int(request.form.get("week", "1"))
    day = int(request.form.get("day", "1"))
    mark_day_complete(user, week, day)
    return redirect(url_for("home" if week == 1 else "week_view", week=week))

@app.route("/week/<int:week>")
def week_view(week):
    if "user" not in session:
        return redirect(url_for("login"))
    if week == 1:
        return redirect(url_for("home"))
    premium = session.get("premium", False)
    if not premium:
        return render_template("locked.html", week=week, checkout_link=CHECKOUT_LINK)

    user = session["user"]
    tasks = load_tasks()
    week_key = str(week)
    week_tasks = tasks.get("weeks", {}).get(week_key, [])
    completed = get_completed_days(user, week)
    day = min(completed + 1, min(len(week_tasks), 7)) if week_tasks else 1
    current_tasks = week_tasks[day-1] if week_tasks else []
    total_days = len(week_tasks) if week_tasks else 7
    progress_pct = int((completed / max(total_days,1)) * 100) if week_tasks else 0
    return render_template("week.html",
                           user=user,
                           week=week,
                           day=day,
                           tasks=current_tasks,
                           completed=completed,
                           progress_pct=progress_pct,
                           total_days=total_days)

@app.route("/unlock", methods=["POST"])
def unlock():
    code = request.form.get("code", "").strip()
    if code == PREMIUM_CODE:
        session["premium"] = True
        next_week = int(request.form.get("week", "2") or "2")
        return redirect(url_for("week_view", week=next_week))
    return render_template("locked.html", week=int(request.form.get("week", "2")), error="Invalid code.", checkout_link=CHECKOUT_LINK)


@app.route("/progress")
def progress():
    if "user" not in session:
        return redirect(url_for("login"))
    user = session["user"]
    w1 = get_completed_days(user, 1)
    w2 = get_completed_days(user, 2)
    w3 = get_completed_days(user, 3)
    w4 = get_completed_days(user, 4)
    return render_template("progress.html", w1=w1, w2=w2, w3=w3, w4=w4)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    authed = session.get("admin", False)
    if request.method == "POST" and not authed:
        if request.form.get("code", "") == ADMIN_CODE:
            session["admin"] = True
            authed = True
        else:
            return render_template("admin.html", authed=False, error="Invalid admin code.")
    if not authed:
        return render_template("admin.html", authed=False)

    tasks = load_tasks()
    if request.method == "POST" and authed and "tasks_json" in request.form:
        try:
            data = json.loads(request.form["tasks_json"])
            save_tasks(data)
            tasks = data
            msg = "Tasks saved."
        except Exception as e:
            return render_template("admin.html", authed=True, tasks_json=request.form["tasks_json"], error=f"JSON error: {e}")
        return render_template("admin.html", authed=True, tasks_json=json.dumps(tasks, ensure_ascii=False, indent=2), msg=msg)
    return render_template("admin.html", authed=True, tasks_json=json.dumps(tasks, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    # roda a configuração inicial (cria DB e tasks.json se faltar)
    setup()
    # inicia o servidor
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
