from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3

app = Flask(__name__, template_folder=".")
app.secret_key = "careerpilot_secret_key"


# ===============================
# DATABASE CONNECTION
# ===============================
def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# ===============================
# HOME PAGE
# ===============================
@app.route("/")
def index():
    return render_template("index.html")


# ===============================
# LOGIN
# ===============================
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


# ===============================
# REGISTER
# ===============================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

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

    return render_template("register.html")


# ===============================
# USER DASHBOARD
# ===============================
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

    conn.close()

    return render_template(
        "dashboard.html",
        user_name=session["user_name"],
        total_results=total_results
    )


# ===============================
# ADMIN LOGIN
# ===============================
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


# ===============================
# ADMIN DASHBOARD
# ===============================
@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total Users
    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()["total_users"]

    # Total Results
    cursor.execute("SELECT COUNT(*) AS total_results FROM results")
    total_results = cursor.fetchone()["total_results"]

    # Today Users
    cursor.execute("""
        SELECT COUNT(*) AS today_users
        FROM users
        WHERE DATE(created_at)=DATE('now')
    """)
    today_users = cursor.fetchone()["today_users"]

    # Today Results
    cursor.execute("""
        SELECT COUNT(*) AS today_results
        FROM results
        WHERE DATE(created_at)=DATE('now')
    """)
    today_results = cursor.fetchone()["today_results"]

    # Recent Users
    cursor.execute("""
        SELECT name,email,created_at
        FROM users
        ORDER BY id DESC
        LIMIT 10
    """)
    users = cursor.fetchall()

    # Top Categories
    cursor.execute("""
        SELECT top_category, COUNT(*) AS total
        FROM results
        GROUP BY top_category
        ORDER BY total DESC
        LIMIT 5
    """)
    top_categories = cursor.fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_results=total_results,
        today_users=today_users,
        today_results=today_results,
        users=users,
        top_categories=top_categories
    )


# ===============================
# CHATBOT
# ===============================
@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")


# ===============================
# HISTORY
# ===============================
@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM results WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],)
    )

    results = cursor.fetchall()
    conn.close()

    return render_template("history.html", results=results)


# ===============================
# LOGOUT
# ===============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ===============================
# RUN APP
# ===============================
if __name__ == "__main__":
    app.run(debug=True)
