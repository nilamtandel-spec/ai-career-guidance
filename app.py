from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import wikipedia
from duckduckgo_search import DDGS

app = Flask(__name__, template_folder=".")
app.secret_key = "careerpilot_secret_key"


def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            top_category TEXT,
            score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_message TEXT,
            bot_reply TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO users(name,email,password) VALUES(?,?,?)",
                (name, email, password)
            )

            conn.commit()
            conn.close()

            flash("Registration successful", "success")
            return redirect(url_for("login"))

        except:
            flash("Email already exists", "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        )

        user = cursor.fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid login details", "danger")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) as total_results FROM results WHERE user_id=?",
        (session["user_id"],)
    )
    total_results = cursor.fetchone()["total_results"]

    cursor.execute(
        "SELECT COUNT(*) as total_chats FROM chat_history WHERE user_id=?",
        (session["user_id"],)
    )
    total_chats = cursor.fetchone()["total_chats"]

    conn.close()

    return render_template(
        "dashboard.html",
        user_name=session["user_name"],
        total_results=total_results,
        total_chats=total_chats
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin123":
            session["admin_id"] = 1
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin login", "danger")

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()["total_users"]

    cursor.execute("SELECT COUNT(*) AS total_results FROM results")
    total_results = cursor.fetchone()["total_results"]

    cursor.execute("SELECT COUNT(*) AS total_chats FROM chat_history")
    total_chats = cursor.fetchone()["total_chats"]

    cursor.execute("""
        SELECT name,email,created_at
        FROM users
        ORDER BY id DESC
        LIMIT 10
    """)
    users = cursor.fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_results=total_results,
        total_chats=total_chats,
        users=users
    )


@app.route("/chatbot")
def chatbot():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("chatbot.html")


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        msg = data.get("message", "").strip()

        if not msg:
            reply = "Please type your question."

        else:
            reply = ""

            try:
                reply = wikipedia.summary(msg, sentences=2)
            except:
                pass

            if not reply:
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.text(msg, max_results=1))
                        if results:
                            reply = results[0].get("body", "")
                except:
                    pass

            if not reply:
                reply = "Sorry, I could not find the answer right now."

        if "user_id" in session:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO chat_history(user_id, user_message, bot_reply) VALUES(?,?,?)",
                (session["user_id"], msg, reply)
            )

            conn.commit()
            conn.close()

        return jsonify({"reply": reply})

    except Exception as e:
        print("Chat Error:", e)
        return jsonify({"reply": "Something went wrong."})


@app.route("/assessment", methods=["GET", "POST"])
def assessment():
    if "user_id" not in session:
        return redirect(url_for("login"))

    questions = [

    {
    "id":1,
    "question_text":"Which activity do you enjoy the most?",
    "option_a":"Solving computer problems",
    "option_b":"Drawing / Designing",
    "option_c":"Leading a team",
    "option_d":"Helping people"
    },

    {
    "id":2,
    "question_text":"Which subject do you like most?",
    "option_a":"Computer / Mathematics",
    "option_b":"Art / Media",
    "option_c":"Commerce / Economics",
    "option_d":"Psychology / Communication"
    },

    {
    "id":3,
    "question_text":"How do you usually solve problems?",
    "option_a":"Using logic and analysis",
    "option_b":"Using creativity",
    "option_c":"Planning strategy",
    "option_d":"Talking with others"
    },

    {
    "id":4,
    "question_text":"Which work environment suits you best?",
    "option_a":"Tech office / Lab",
    "option_b":"Creative studio",
    "option_c":"Corporate office",
    "option_d":"Public interaction place"
    },

    {
    "id":5,
    "question_text":"Which tool would you prefer to use?",
    "option_a":"Laptop / Software",
    "option_b":"Camera / Design tools",
    "option_c":"Reports / Business tools",
    "option_d":"Phone / Communication tools"
    },

    {
    "id":6,
    "question_text":"What type of task excites you most?",
    "option_a":"Building apps / websites",
    "option_b":"Creating videos / graphics",
    "option_c":"Running business projects",
    "option_d":"Guiding students / customers"
    },

    {
    "id":7,
    "question_text":"What is your strongest skill?",
    "option_a":"Technical thinking",
    "option_b":"Creative imagination",
    "option_c":"Leadership ability",
    "option_d":"Communication skill"
    },

    {
    "id":8,
    "question_text":"Which career sounds best to you?",
    "option_a":"Software Engineer",
    "option_b":"Graphic Designer",
    "option_c":"Business Manager",
    "option_d":"Counsellor / HR"
    },

    {
    "id":9,
    "question_text":"How do you prefer to work?",
    "option_a":"With systems and data",
    "option_b":"With ideas and visuals",
    "option_c":"With targets and plans",
    "option_d":"With people and support"
    },

    {
    "id":10,
    "question_text":"What motivates you more?",
    "option_a":"Innovation",
    "option_b":"Creativity",
    "option_c":"Success and growth",
    "option_d":"Helping others succeed"
    },

    {
    "id":11,
    "question_text":"Which college stream interests you most?",
    "option_a":"IT / Engineering",
    "option_b":"Design / Animation",
    "option_c":"Management / Commerce",
    "option_d":"Humanities / Communication"
    },

    {
    "id":12,
    "question_text":"How do friends describe you?",
    "option_a":"Smart and logical",
    "option_b":"Creative and stylish",
    "option_c":"Confident leader",
    "option_d":"Friendly and supportive"
    },

    {
    "id":13,
    "question_text":"Which future role do you imagine?",
    "option_a":"Tech Expert",
    "option_b":"Creative Artist",
    "option_c":"CEO / Entrepreneur",
    "option_d":"Mentor / Advisor"
    },

    {
    "id":14,
    "question_text":"Which challenge would you enjoy?",
    "option_a":"Fixing software issue",
    "option_b":"Designing a brand logo",
    "option_c":"Managing company growth",
    "option_d":"Solving customer problem"
    },

    {
    "id":15,
    "question_text":"What matters most in your career?",
    "option_a":"Innovation and technology",
    "option_b":"Expression and creativity",
    "option_c":"Money and leadership",
    "option_d":"Meaningful human impact"
    }

    ]

    if request.method == "POST":

        a_count = 0
        b_count = 0
        c_count = 0
        d_count = 0

        for question in questions:
            answer = request.form.get(f"question_{question['id']}")

            if answer == "A":
                a_count += 1
            elif answer == "B":
                b_count += 1
            elif answer == "C":
                c_count += 1
            elif answer == "D":
                d_count += 1

        scores = {
            "Technology / IT Career": a_count,
            "Design / Creative Career": b_count,
            "Management / Business Career": c_count,
            "Communication / HR Career": d_count
        }

        top_category = max(scores, key=scores.get)
        top_score = scores[top_category]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO results(user_id, top_category, score) VALUES(?,?,?)",
            (session["user_id"], top_category, top_score)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("result"))

    return render_template("assessment.html", questions=questions)


@app.route("/result")
def result():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT top_category, score, created_at
        FROM results
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],))
    latest_result = cursor.fetchone()

    cursor.execute("""
        SELECT top_category, score, created_at
        FROM results
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 5
    """, (session["user_id"],))
    history = cursor.fetchall()

    conn.close()

    return render_template(
        "result.html",
        result=latest_result,
        history=history
    )

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_message, bot_reply, created_at
        FROM chat_history
        WHERE user_id=?
        ORDER BY id DESC
    """, (session["user_id"],))

    chats = cursor.fetchall()
    conn.close()

    return render_template("history.html", chats=chats)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=True
    )
