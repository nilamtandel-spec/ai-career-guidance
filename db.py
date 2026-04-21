import sqlite3
from pathlib import Path
from config import Config
from werkzeug.security import generate_password_hash

def get_db_connection():
    Path("instance").mkdir(exist_ok=True)
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            category_a TEXT NOT NULL,
            category_b TEXT NOT NULL,
            category_c TEXT NOT NULL,
            category_d TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS careers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            career_name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            required_skills TEXT NOT NULL,
            courses TEXT NOT NULL,
            salary_range TEXT NOT NULL,
            future_scope TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            top_category TEXT NOT NULL,
            recommended_careers TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM admins")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )

    cursor.execute("SELECT COUNT(*) FROM questions")
    if cursor.fetchone()[0] == 0:
        questions = [
            (
                "Which activity do you enjoy the most?",
                "Coding programs",
                "Designing posters or interfaces",
                "Managing people and events",
                "Teaching and explaining concepts",
                "Technology", "Design", "Management", "Education"
            ),
            (
                "Which subject do you like the most?",
                "Computer Science",
                "Arts / Design",
                "Business Studies",
                "Psychology / Education",
                "Technology", "Design", "Management", "Education"
            ),
            (
                "What type of work would you prefer?",
                "Problem solving using logic",
                "Creative visual work",
                "Leadership and planning",
                "Helping others learn",
                "Technology", "Design", "Management", "Education"
            ),
            (
                "What are you best at?",
                "Analytical thinking",
                "Creativity",
                "Decision making",
                "Communication and guidance",
                "Technology", "Design", "Management", "Education"
            ),
            (
                "Which career sounds most interesting to you?",
                "Software Developer",
                "UI/UX Designer",
                "Project Manager",
                "Teacher / Counselor",
                "Technology", "Design", "Management", "Education"
            ),
            (
                "How do you like to solve tasks?",
                "With logic and systems",
                "With creativity and visuals",
                "With planning and teamwork",
                "With explanation and support",
                "Technology", "Design", "Management", "Education"
            )
        ]
        cursor.executemany("""
            INSERT INTO questions (
                question_text, option_a, option_b, option_c, option_d,
                category_a, category_b, category_c, category_d
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, questions)

    cursor.execute("SELECT COUNT(*) FROM careers")
    if cursor.fetchone()[0] == 0:
        careers = [
            (
                "Software Developer",
                "Technology",
                "Develops websites, applications, and software systems.",
                "Python, Java, problem solving, logic",
                "BSc IT, BCA, MCA, Python, Web Development",
                "4 LPA - 12 LPA",
                "Very high demand in IT companies and startups"
            ),
            (
                "Data Analyst",
                "Technology",
                "Analyzes data to generate useful business insights.",
                "Excel, SQL, Python, statistics",
                "Data Analytics, SQL, Power BI, Python",
                "4 LPA - 10 LPA",
                "Growing demand in every industry"
            ),
            (
                "UI/UX Designer",
                "Design",
                "Designs user-friendly digital products and app interfaces.",
                "Figma, creativity, design thinking",
                "UI/UX Design, Graphic Design, Product Design",
                "3 LPA - 10 LPA",
                "High demand in tech and product companies"
            ),
            (
                "Graphic Designer",
                "Design",
                "Creates visual designs for brands, media, and marketing.",
                "Photoshop, Canva, Illustrator, creativity",
                "Graphic Design, Multimedia, Visual Communication",
                "2.5 LPA - 8 LPA",
                "Good opportunities in marketing and branding"
            ),
            (
                "Project Manager",
                "Management",
                "Plans, executes, and manages projects and teams.",
                "Leadership, planning, communication",
                "BBA, MBA, Project Management courses",
                "5 LPA - 15 LPA",
                "Strong growth in IT, business, and operations"
            ),
            (
                "HR Executive",
                "Management",
                "Handles recruitment, employee support, and HR processes.",
                "Communication, organization, leadership",
                "BBA, MBA HR, Communication Skills",
                "3 LPA - 8 LPA",
                "Stable corporate career option"
            ),
            (
                "Teacher",
                "Education",
                "Teaches students and helps them understand subjects clearly.",
                "Communication, patience, subject knowledge",
                "B.Ed, Teaching Certifications, Subject Courses",
                "2.5 LPA - 7 LPA",
                "Respected and stable profession"
            ),
            (
                "Career Counselor",
                "Education",
                "Guides students in career planning and decision making.",
                "Communication, empathy, guidance",
                "Psychology, Counseling, Career Guidance courses",
                "3 LPA - 9 LPA",
                "Growing need in schools and colleges"
            )
        ]
        cursor.executemany("""
            INSERT INTO careers (
                career_name, category, description, required_skills,
                courses, salary_range, future_scope
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, careers)

    conn.commit()
    conn.close()
