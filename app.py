from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from config import Config
from db import init_db, get_db_connection
from auth import register_user, login_user, login_admin
from recommendation import calculate_recommendation, save_result
from openai import OpenAI
import os

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')
app.config.from_object(Config)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        success, message = register_user(name, email, password)
        if success:
            flash(message, "success")
            return redirect(url_for("login"))
        flash(message, "danger")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        success, result = login_user(email, password)
        if success:
            session["user_id"] = result["id"]
            session["user_name"] = result["name"]
            return redirect(url_for("dashboard"))
        flash(result, "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user_name=session.get("user_name"))

@app.route("/assessment", methods=["GET", "POST"])
def assessment():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions")
    questions = cursor.fetchall()
    conn.close()

    if request.method == "POST":
        answer_map = {}
        for question in questions:
            answer_map[str(question["id"])] = request.form.get(f"question_{question['id']}")

        top_category, careers = calculate_recommendation(answer_map)

        if not top_category or not careers:
            flash("Please answer all questions properly.", "danger")
            return redirect(url_for("assessment"))

        save_result(session["user_id"], top_category, careers)
        session["top_category"] = top_category
        session["recommended_ids"] = [career["id"] for career in careers]
        return redirect(url_for("result"))

    return render_template("assessment.html", questions=questions)

@app.route("/result")
def result():
    if "user_id" not in session:
        return redirect(url_for("login"))

    top_category = session.get("top_category")
    recommended_ids = session.get("recommended_ids", [])
    careers = []

    if recommended_ids:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(recommended_ids))
        cursor.execute(f"SELECT * FROM careers WHERE id IN ({placeholders})", tuple(recommended_ids))
        careers = cursor.fetchall()
        conn.close()

    return render_template("result.html", top_category=top_category, careers=careers)

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM results WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],))
    results = cursor.fetchall()
    conn.close()
    return render_template("history.html", results=results)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        success, result = login_admin(username, password)
        if success:
            session["admin_id"] = result["id"]
            session["admin_name"] = result["username"]
            return redirect(url_for("admin_dashboard"))
        flash(result, "danger")

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
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 10")
    users = cursor.fetchall()
    cursor.execute("""
        SELECT results.*, users.name
        FROM results
        JOIN users ON results.user_id = users.id
        ORDER BY results.created_at DESC
        LIMIT 15
    """)
    results = cursor.fetchall()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_results=total_results,
        users=users,
        results=results
    )

# =========================
# AI Chatbot Page
# =========================
@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

# =========================
# AI Chat API
# =========================
@app.route("/ask-ai", methods=["POST"])
def ask_ai():
    user_message = request.json.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "Please type a question."})

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=f"""
You are a helpful AI Career Guidance Assistant for students.
Give clear, professional, and easy-to-understand answers.
Keep answers focused on careers, skills, courses, jobs, and future scope.

Student Question:
{user_message}
"""
        )

        return jsonify({"reply": response.output_text})

 except Exception as e:
    return jsonify({"reply": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
