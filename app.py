from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os

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
        msg = data.get("message", "").lower().strip()

        if not msg:
            reply = "Please type your question."

        elif "admission" in msg:
            reply = "Admission process includes registration, documents submission and fee payment."

        elif "fees" in msg or "fee" in msg:
            reply = "Fees depend on selected course. Please tell course name."

        elif "scholarship" in msg:
            reply = "Scholarship is available based on eligibility, merit and entrance exam performance."

        elif "placement" in msg:
            reply = "Placement support includes training, resume preparation, interview guidance and company placement assistance."

        elif "hostel" in msg:
            reply = "Hostel facility is available with required student amenities. Fees depend on campus and room type."

        elif "course" in msg:
            reply = "Courses are available in Engineering, IT, Management, Law, Pharmacy, Design and Science."

        elif "career" in msg or "it" in msg:
            reply = "IT career options include Software Developer, Web Developer, Data Analyst, Cyber Security Analyst and AI/ML Developer."

        elif "hello" in msg or "hi" in msg or "hii" in msg:
            reply = "Hello 👋 How can I help you today?"

        else:
            reply = "Please share your course interest, qualification and location so I can guide you better."

        # Save chat history
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
        return jsonify({"reply": "Something went wrong. Please try again."})


@app.route("/assessment")
def assessment():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("assessment.html")


@app.route("/result")
def result():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("result.html")


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
