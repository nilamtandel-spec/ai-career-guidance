from collections import defaultdict
from db import get_db_connection

def calculate_recommendation(answer_map):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions")
    questions = cursor.fetchall()

    score_map = defaultdict(int)

    for question in questions:
        qid = str(question["id"])
        selected = answer_map.get(qid)

        if selected == "A":
            score_map[question["category_a"]] += 1
        elif selected == "B":
            score_map[question["category_b"]] += 1
        elif selected == "C":
            score_map[question["category_c"]] += 1
        elif selected == "D":
            score_map[question["category_d"]] += 1

    if not score_map:
        conn.close()
        return None, []

    top_category = max(score_map, key=score_map.get)
    cursor.execute("SELECT * FROM careers WHERE category = ?", (top_category,))
    careers = cursor.fetchall()
    conn.close()

    return top_category, careers

def save_result(user_id, top_category, careers):
    career_names = ", ".join([career["career_name"] for career in careers])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO results (user_id, top_category, recommended_careers) VALUES (?, ?, ?)",
        (user_id, top_category, career_names)
    )
    conn.commit()
    conn.close()
