from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from config import Config
from db import init_db, get_db_connection
from auth import register_user, login_user, login_admin
from recommendation import calculate_recommendation, save_result
import google.generativeai as genai
import os

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')
app.config.from_object(Config)

# Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
else:
    model = None

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
        cursor.execute(
            f"SELECT * FROM careers WHERE id IN ({placeholders})",
            tuple(recommended_ids)
        )
        careers = cursor.fetchall()
        conn.close()

    return render_template("result.html", top_category=top_category, careers=careers)


@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM results WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],)
    )
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


@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")


@app.route("/ask-ai", methods=["POST"])
def ask_ai():
    user_message = request.json.get("message", "").strip()
    msg = user_message.lower()

    if not user_message:
        return jsonify({"reply": "Please type a question."})

    fallback_reply = None

    qa_pairs = {
        "what is bca": "BCA stands for Bachelor of Computer Applications. It is a good course for students interested in programming, software development, web development, databases, and IT careers.",
        "bca": "BCA is a strong course for students interested in coding, software development, web development, app development, and IT careers. After BCA, you can go for MCA, certifications, or software jobs.",
        "what is bsc it": "BSc IT stands for Bachelor of Science in Information Technology. It focuses on programming, databases, networking, software, web technologies, and IT systems.",
        "bsc it": "BSc IT is a very good option for students interested in programming, networking, databases, cloud, software testing, and IT support roles.",
        "what is mba": "MBA stands for Master of Business Administration. It is a management degree that helps students build careers in HR, Marketing, Finance, Operations, and Business Leadership.",
        "mba": "MBA is best for students who want careers in management, marketing, HR, finance, operations, or entrepreneurship.",
        "cyber security": "Cyber Security is a strong career option for students interested in networking, ethical hacking, digital protection, and security systems.",
        "ui ux": "UI/UX Design is a great career for creative students who enjoy design, app layouts, website interfaces, and user-friendly digital products.",
        "best career after bca": "After BCA, strong career options include Software Developer, Web Developer, App Developer, Data Analyst, UI/UX Designer, Cyber Security Analyst, and MCA for higher studies.",
        "best career after bsc it": "After BSc IT, good career options include Software Developer, Data Analyst, Web Developer, Cloud Engineer, Cyber Security Analyst, System Administrator, and MCA or MSc IT.",
        "best course after 12th science": "After 12th Science, popular courses include Engineering, Pharmacy, BSc IT, BCA, Biotechnology, Nursing, Architecture, Design, and pure science courses.",
        "best course after 12th commerce": "After 12th Commerce, good courses include BCom, BBA, CA, CS, CMA, Banking, Finance, Digital Marketing, Hotel Management, and Law.",
        "best course after 12th arts": "After 12th Arts, you can choose BA, BJMC, Law, Psychology, Design, Hotel Management, Animation, Social Work, and Event Management.",
        "software engineer salary": "Software Engineer salary depends on skills and company. Freshers may start around 3.5 to 8 LPA, with higher packages in strong companies.",
        "data analyst salary": "A Data Analyst fresher in India may start around 4 to 8 LPA depending on skills like SQL, Excel, Python, and Power BI.",
        "hello": "Hello! I am your Career Guidance Assistant. You can ask me about careers, courses, salaries, future scope, or skills.",
        "hi": "Hi! I can help you with course selection, career options, skills, and job-related guidance."
    }

    for question, answer in qa_pairs.items():
        if question in msg:
            fallback_reply = answer
            break

    if not fallback_reply:
        if "science" in msg and "after 12th" in msg:
            fallback_reply = "After 12th Science, options include Engineering, Pharmacy, BSc IT, BCA, Biotechnology, Design, and many professional science fields."
        elif "commerce" in msg and "after 12th" in msg:
            fallback_reply = "After 12th Commerce, options include BCom, BBA, CA, CS, Banking, Finance, Digital Marketing, and Law."
        elif "arts" in msg and "after 12th" in msg:
            fallback_reply = "After 12th Arts, options include BA, Law, Psychology, Design, Journalism, Hotel Management, Animation, and Social Work."
        elif "computer" in msg or "it" in msg:
            fallback_reply = "If you are interested in computers and IT, strong paths include BCA, BSc IT, Software Development, Data Analytics, Cyber Security, and Cloud Computing."
        elif "management" in msg or "business" in msg:
            fallback_reply = "If you like business and management, strong options include BBA, MBA, Marketing, HR, Finance, Business Analytics, and Entrepreneurship."
        elif "design" in msg or "creative" in msg:
            fallback_reply = "If you like creativity and design, strong options include UI/UX, Graphic Design, Animation, Product Design, and Digital Media."

    if model:
        try:
            prompt = f"""
You are a helpful AI Career Guidance Assistant for students.

Give clear, simple, practical, and professional answers.

Focus on:
- careers
- courses
- skills
- jobs
- salary
- future scope

Student Question:
{user_message}
"""
            response = model.generate_content(prompt)
            reply = response.text if hasattr(response, "text") else None

            if reply and reply.strip():
                return jsonify({"reply": reply})

        except Exception:
            pass

    if fallback_reply:
        return jsonify({"reply": fallback_reply})

    return jsonify({
        "reply": "I can help with career guidance. Ask me about BCA, BSc IT, MBA, Data Science, UI/UX, Cyber Security, salary, skills, or career options after 12th."
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
