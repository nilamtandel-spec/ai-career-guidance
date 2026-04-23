@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total assessments taken by this user
    cursor.execute(
        "SELECT COUNT(*) AS total_results FROM results WHERE user_id = ?",
        (session["user_id"],)
    )
    total_results = cursor.fetchone()["total_results"]

    # Unique categories explored
    cursor.execute(
        "SELECT COUNT(DISTINCT top_category) AS unique_categories FROM results WHERE user_id = ?",
        (session["user_id"],)
    )
    unique_categories = cursor.fetchone()["unique_categories"]

    # Latest result
    cursor.execute(
        """
        SELECT top_category, recommended_careers, created_at
        FROM results
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (session["user_id"],)
    )
    latest_result = cursor.fetchone()

    # Recent 5 activities
    cursor.execute(
        """
        SELECT top_category, recommended_careers, created_at
        FROM results
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (session["user_id"],)
    )
    recent_results = cursor.fetchall()

    # Results in last 7 days
    cursor.execute(
        """
        SELECT COUNT(*) AS recent_results_count
        FROM results
        WHERE user_id = ?
        AND DATE(created_at) >= DATE('now', '-7 day')
        """,
        (session["user_id"],)
    )
    recent_results_count = cursor.fetchone()["recent_results_count"]

    conn.close()

    # Dynamic progress score
    readiness_score = 20
    if total_results > 0:
        readiness_score += 35
    if unique_categories > 0:
        readiness_score += min(unique_categories * 10, 20)
    if recent_results_count > 0:
        readiness_score += min(recent_results_count * 5, 25)

    readiness_score = min(readiness_score, 100)

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name"),
        total_results=total_results,
        unique_categories=unique_categories,
        recent_results_count=recent_results_count,
        readiness_score=readiness_score,
        latest_result=latest_result,
        recent_results=recent_results
    )
