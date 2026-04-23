from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from config import Config
from db import init_db, get_db_connection
from auth import register_user, login_user, login_admin
from recommendation import calculate_recommendation, save_result
import google.generativeai as genai
import os

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')
app.config.from_object(Config)

# Gemini Client
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

# Init DB
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
            answer_map[str(question["id"])] = request.form.get(
                f"question_{question['id']}"
            )

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

    return render_template(
        "result.html",
        top_category=top_category,
        careers=careers
    )


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
        "what is mca": "MCA stands for Master of Computer Applications. It is a strong higher education option after BCA or BSc IT for software and IT careers.",
        "mca": "MCA is a strong option after BCA or BSc IT if you want advanced knowledge in software development, programming, databases, and IT careers.",
        "what is bba": "BBA stands for Bachelor of Business Administration. It is useful for students interested in management, marketing, HR, finance, and business careers.",
        "bba": "BBA is a good course for students interested in business, management, sales, HR, and entrepreneurship.",
        "what is bcom": "BCom stands for Bachelor of Commerce. It is suitable for students interested in accounts, banking, finance, taxation, and business.",
        "bcom": "BCom is best for students interested in commerce, banking, accounting, finance, taxation, and business management.",
        "what is data science": "Data Science is a field where data is analyzed to find patterns, insights, and predictions using statistics, programming, and machine learning.",
        "data science": "Data Science is an excellent career for students who like logic, numbers, coding, and business insights. Useful skills include Python, SQL, statistics, and machine learning.",
        "what is cyber security": "Cyber Security is the field of protecting computers, networks, and data from hacking, threats, and digital attacks.",
        "cyber security": "Cyber Security is a strong career option for students interested in networking, ethical hacking, digital protection, and security systems.",
        "cybersecurity": "Cyber Security is a strong career option for students interested in networking, ethical hacking, digital protection, and security systems.",
        "what is ui ux": "UI/UX means User Interface and User Experience Design. It focuses on making websites and apps easy, attractive, and user-friendly.",
        "ui ux": "UI/UX Design is a great career for creative students who enjoy design, app layouts, website interfaces, and user-friendly digital products.",
        "ui/ux": "UI/UX Design is a great career for creative students who enjoy design, app layouts, website interfaces, and user-friendly digital products.",
        "animation": "Animation is a creative field where you can work in films, games, advertising, digital media, and content creation.",
        "what is animation": "Animation is the process of creating moving visuals using drawings, graphics, or software. It offers careers in films, gaming, VFX, and media.",

        "best career after bca": "After BCA, strong career options include Software Developer, Web Developer, App Developer, Data Analyst, UI/UX Designer, Cyber Security Analyst, and MCA for higher studies.",
        "best career after bsc it": "After BSc IT, good career options include Software Developer, Data Analyst, Web Developer, Cloud Engineer, Cyber Security Analyst, System Administrator, and MCA or MSc IT.",
        "best career after mba": "After MBA, strong career options include Marketing Manager, HR Manager, Business Analyst, Sales Manager, Operations Manager, Financial Analyst, and Entrepreneur.",
        "best career after commerce": "After Commerce, strong career options include CA, CS, CMA, BCom, BBA, Banking, Finance, Digital Marketing, Business Analytics, and Law.",
        "best career after arts": "After Arts, strong career options include BA, Law, Journalism, Psychology, Social Work, Design, Hotel Management, Event Management, Animation, and Government job preparation.",
        "best career after science": "After Science, strong options include Engineering, Pharmacy, BSc IT, BCA, Biotechnology, Nursing, Design, Pure Sciences, Architecture, and AI-related courses.",
        "career in coding": "If you like coding, good career options include Software Developer, Web Developer, App Developer, Full Stack Developer, Data Analyst, and AI Engineer.",
        "career in finance": "Finance careers include Accountant, Financial Analyst, Investment Banker, Tax Consultant, Auditor, Banking Professional, and MBA Finance roles.",
        "career in management": "Management careers include HR, Marketing, Operations, Sales, Business Development, Project Management, and Entrepreneurship.",
        "career in design": "Design careers include UI/UX Designer, Graphic Designer, Animator, Fashion Designer, Product Designer, Interior Designer, and Communication Designer.",

        "best course after 12th science": "After 12th Science, popular courses include Engineering, Pharmacy, BSc IT, BCA, Biotechnology, Nursing, Architecture, Design, and pure science courses.",
        "best course after 12th commerce": "After 12th Commerce, good courses include BCom, BBA, CA, CS, CMA, Banking, Finance, Digital Marketing, Hotel Management, and Law.",
        "best course after 12th arts": "After 12th Arts, you can choose BA, BJMC, Law, Psychology, Design, Hotel Management, Animation, Social Work, and Event Management.",
        "courses after pcm": "After PCM, top courses include Engineering, BSc Computer Science, BSc IT, Architecture, Aviation, Design, Data Science, and Defence-related careers.",
        "courses after pcb": "After PCB, strong options include MBBS, BDS, BAMS, BHMS, Nursing, Pharmacy, Biotechnology, Microbiology, and Allied Health Sciences.",
        "courses without maths": "Without Maths, you can still go for BCA in some colleges, BBA, Law, Design, Hotel Management, Media, Psychology, and many non-engineering courses.",
        "career after low percentage": "Even with low percentage, you can build a strong career through skill-based courses, certifications, diploma programs, digital skills, design, coding, or management pathways.",
        "diploma after 12th": "Diploma courses after 12th include Diploma in Engineering, Design, Animation, Hotel Management, Computer Applications, Digital Marketing, and Nursing-related fields.",
        "degree after 12th": "Degree options after 12th depend on your stream. Popular ones include BTech, BCA, BSc IT, BCom, BBA, BA, BDes, and Law.",
        "best private college courses": "The best private college course depends on your interests. In general, BTech, BCA, BSc IT, BBA, Design, Law, and Pharmacy are popular choices.",

        "how to become software developer": "To become a Software Developer, learn programming languages like Python, Java, or C++, practice coding, build projects, use GitHub, and apply for internships or fresher roles.",
        "how to become data analyst": "To become a Data Analyst, learn Excel, SQL, Python, statistics, and Power BI or Tableau. Build projects using data dashboards and analysis.",
        "how to become ethical hacker": "To become an Ethical Hacker, learn networking, Linux, security basics, penetration testing tools, and ethical hacking concepts. Certifications can help.",
        "how to become web developer": "To become a Web Developer, learn HTML, CSS, JavaScript, and a backend language like Python or PHP. Build websites and publish projects online.",
        "how to become app developer": "To become an App Developer, learn Android development, Flutter, React Native, or Kotlin. Build sample apps and upload them to a portfolio.",
        "how to become ai engineer": "To become an AI Engineer, learn Python, machine learning, mathematics, data handling, and model building. Start with data science and ML projects.",
        "python career scope": "Python has excellent career scope in software development, data science, automation, AI, web development, and backend programming.",
        "java career scope": "Java has strong career scope in enterprise software, backend development, Android development, and large-scale application systems.",
        "cloud computing jobs": "Cloud Computing jobs include Cloud Engineer, DevOps Engineer, Cloud Administrator, Solutions Architect, and Infrastructure Engineer.",
        "full stack developer scope": "Full Stack Development has strong scope because companies value developers who can work on both frontend and backend systems.",

        "bca salary in india": "BCA freshers can start around 2.5 to 5 LPA depending on skills, city, and company. Strong skills can increase salary faster.",
        "mba salary in india": "MBA salary depends on specialization and college. Freshers may start around 4 to 10 LPA, while top colleges can offer more.",
        "data analyst salary": "A Data Analyst fresher in India may start around 4 to 8 LPA depending on skills like SQL, Excel, Python, and Power BI.",
        "software engineer salary": "Software Engineer salary depends on skills and company. Freshers may start around 3.5 to 8 LPA, with higher packages in strong companies.",
        "ui ux designer salary": "UI/UX Designers can start around 3 to 7 LPA, and experienced designers can earn much more with strong portfolios.",
        "cyber security salary": "Cyber Security professionals can start around 4 to 8 LPA, and salaries increase significantly with certifications and experience.",
        "fresher it salary": "IT fresher salary usually depends on role and skill level. It may range from 2.5 to 6 LPA or more.",
        "highest paying jobs after graduation": "Some high-paying jobs after graduation include Software Developer, Data Scientist, Product Manager, Investment Banker, Management Consultant, and Cloud Engineer.",
        "career with high salary": "High-salary careers often include Data Science, Software Engineering, AI, Cyber Security, Finance, Management, and specialized technical roles.",
        "jobs after bsc it salary": "After BSc IT, salaries usually depend on role and skills. Common starting range is around 3 to 6 LPA, with good growth after experience.",

        "skills for software job": "Important skills for software jobs include programming, problem solving, databases, DSA basics, GitHub, testing, and communication.",
        "skills for mba students": "MBA students should build communication, leadership, presentation, Excel, decision-making, analytical thinking, and networking skills.",
        "skills for data science": "Important data science skills include Python, SQL, statistics, machine learning basics, Excel, data visualization, and problem solving.",
        "communication skills importance": "Communication skills are very important in every career because they help in teamwork, interviews, presentations, leadership, and professional growth.",
        "best technical skills in 2026": "Strong technical skills for 2026 include Python, AI tools, Data Analytics, Cloud, Cyber Security, Full Stack Development, UI/UX, and Automation.",
        "skills after bca": "After BCA, build Python, Java, web development, SQL, cloud basics, GitHub projects, and interview preparation skills.",
        "coding skills roadmap": "A coding roadmap should start with one language, then DSA basics, projects, GitHub, databases, web basics, and interview practice.",
        "excel skills for jobs": "Excel is very useful for jobs in business, analysis, operations, HR, and finance. Learn formulas, pivot tables, charts, and data cleaning.",
        "interview skills": "Interview skills include confidence, good communication, clarity, resume knowledge, technical basics, body language, and preparation.",
        "resume skills": "A resume should highlight technical skills, tools, certifications, internships, projects, achievements, and communication strengths.",

        "career in graphic design": "Graphic Design is a good career for creative students who enjoy visuals, branding, social media design, and digital communication.",
        "career in ui ux": "UI/UX is one of the best creative-tech careers. It mixes design, user psychology, product thinking, and digital experience.",
        "career in animation": "Animation offers careers in gaming, film, content creation, media, education, and digital entertainment.",
        "career in gaming": "Gaming careers include Game Designer, Game Developer, 3D Artist, Animator, Level Designer, and QA Tester.",
        "career in vfx": "VFX is a strong creative field for students interested in film, motion graphics, editing, and digital effects.",
        "career in photography": "Photography can lead to careers in fashion, product, wedding, commercial, travel, journalism, and content creation.",
        "career in fashion design": "Fashion Design is suitable for creative students interested in clothing, styling, trends, branding, and apparel creation.",
        "career in communication design": "Communication Design combines visual design, branding, media, and digital creativity for effective communication.",
        "career in digital media": "Digital Media offers careers in content creation, video editing, branding, digital campaigns, design, and online marketing.",
        "career in content creation": "Content creation can become a strong career through writing, video, design, teaching, reviewing, or niche-based social media work.",

        "mba specializations": "Popular MBA specializations include Marketing, Finance, HR, Operations, Business Analytics, International Business, and Entrepreneurship.",
        "marketing career options": "Marketing careers include Digital Marketer, Brand Manager, Sales Manager, Content Strategist, SEO Analyst, and Product Marketing roles.",
        "hr career options": "HR careers include Recruiter, HR Executive, Talent Acquisition Specialist, Learning and Development Officer, and HR Manager.",
        "finance career options": "Finance careers include Accountant, Auditor, Financial Analyst, Banker, Tax Consultant, Investment Analyst, and Risk Analyst.",
        "entrepreneurship after college": "Entrepreneurship after college can be a great option if you have a business idea, leadership ability, and willingness to learn and take risks.",
        "business analyst career": "Business Analyst is a good career for students who like problem solving, data, communication, and business process improvement.",
        "operations management career": "Operations careers focus on planning, efficiency, supply chain, workflow, and business process management.",
        "banking career options": "Banking careers include PO, Clerk, Relationship Manager, Credit Analyst, Loan Officer, and Financial Services roles.",
        "investment banking scope": "Investment Banking offers high-growth careers but usually needs strong finance knowledge, analytical ability, and often higher studies or top institutions.",
        "family business mba useful": "Yes, MBA can be very useful for family business because it improves finance, management, strategy, operations, and growth planning.",

        "study abroad after graduation": "Study abroad after graduation is a good option if you want international exposure, specialized education, and global career opportunities.",
        "jobs abroad after bca": "After BCA, jobs abroad may require strong skills, experience, certifications, and sometimes higher studies like MCA or MS.",
        "future jobs in ai": "Future jobs in AI include AI Engineer, Machine Learning Engineer, Data Scientist, Prompt Designer, AI Product Specialist, and Automation roles.",
        "best careers in 2030": "Careers expected to grow strongly by 2030 include AI, Data Science, Cloud Computing, Cyber Security, Healthcare, Renewable Energy, and Digital Business.",
        "remote jobs future": "Remote jobs will continue growing in software, design, content, data, support, consulting, and digital marketing.",
        "career after automation": "Automation will replace some tasks, but careers in AI, analytics, product design, management, problem solving, and creativity will remain strong.",
        "jobs safe from ai": "Jobs that strongly involve creativity, leadership, strategy, empathy, communication, design, and complex decision-making are safer from AI replacement.",
        "international mba scope": "International MBA can provide strong global exposure, networking, and career opportunities, but it should be chosen carefully because it can be expensive.",
        "skills for future jobs": "Future job skills include adaptability, digital literacy, communication, AI awareness, problem solving, coding, data analysis, and creativity.",
        "ai replacing jobs": "AI may automate some repetitive work, but it will also create new jobs. Students should focus on future-ready skills instead of fearing AI.",

        "i am confused about career": "That is normal. Start by identifying your interests, strengths, favorite subjects, and long-term goals. Then choose a course or career path that matches them.",
        "which course suits me": "Tell me your stream, favorite subjects, and interests. Then I can suggest a more suitable course for you.",
        "how to choose career": "Choose a career based on your interests, skills, personality, strengths, future demand, and willingness to learn. Never choose only by pressure or trend.",
        "low marks what to do": "Low marks do not end your future. Focus on skill-building, practical learning, certifications, and choosing a field that matches your strengths.",
        "no interest in studies what career": "If you are not interested in traditional study, consider skill-based areas like design, digital marketing, photography, animation, sales, UI/UX, or entrepreneurship.",
        "i like computers what should i do": "If you like computers, strong options include BCA, BSc IT, Computer Engineering, Cyber Security, Data Analytics, Cloud, or Web Development.",
        "i like business what should i do": "If you like business, consider BBA, BCom, MBA, Marketing, Entrepreneurship, Finance, Business Analytics, or family business management.",
        "i like design what should i do": "If you like design, consider UI/UX, Graphic Design, Animation, Fashion Design, Product Design, or Communication Design.",
        "i want government job path": "For government jobs, choose a graduation course you can manage well, then prepare for SSC, Banking, UPSC, State PSC, Railways, or other exams.",
        "best career for me": "Tell me your stream, your interests, what subjects you enjoy, and whether you like coding, business, design, or helping people. Then I can guide better.",

        "hello": "Hello! I am your Career Guidance Assistant. You can ask me about careers, courses, salaries, future scope, or skills.",
        "hi": "Hi! I can help you with course selection, career options, skills, and job-related guidance.",
        "hii": "Hello! Ask me anything about careers, courses, future scope, or jobs.",
        "hey": "Hey! I am here to help you with career guidance.",
        "course": "Please tell me which field or stream you are interested in, and I will suggest suitable courses.",
        "career": "Please tell me your stream or interest area like IT, design, business, or healthcare, and I will guide you.",
        "salary": "Salary depends on your course, role, city, company, and most importantly your skills. Strong skills improve salary a lot.",
        "skills": "Good skills include communication, problem solving, digital tools, teamwork, and domain-specific technical skills.",
        "jobs": "Tell me the field you are interested in, such as IT, management, finance, design, or government jobs, and I will suggest roles."
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
    app.run(host="0.0.0.0", port=port)from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from config import Config
from db import init_db, get_db_connection
from auth import register_user, login_user, login_admin
from recommendation import calculate_recommendation, save_result
import google.generativeai as genai
import os

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')
app.config.from_object(Config)

# Gemini Client
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

# Init DB
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
            answer_map[str(question["id"])] = request.form.get(
                f"question_{question['id']}"
            )

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

    return render_template(
        "result.html",
        top_category=top_category,
        careers=careers
    )


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
        "what is mca": "MCA stands for Master of Computer Applications. It is a strong higher education option after BCA or BSc IT for software and IT careers.",
        "mca": "MCA is a strong option after BCA or BSc IT if you want advanced knowledge in software development, programming, databases, and IT careers.",
        "what is bba": "BBA stands for Bachelor of Business Administration. It is useful for students interested in management, marketing, HR, finance, and business careers.",
        "bba": "BBA is a good course for students interested in business, management, sales, HR, and entrepreneurship.",
        "what is bcom": "BCom stands for Bachelor of Commerce. It is suitable for students interested in accounts, banking, finance, taxation, and business.",
        "bcom": "BCom is best for students interested in commerce, banking, accounting, finance, taxation, and business management.",
        "what is data science": "Data Science is a field where data is analyzed to find patterns, insights, and predictions using statistics, programming, and machine learning.",
        "data science": "Data Science is an excellent career for students who like logic, numbers, coding, and business insights. Useful skills include Python, SQL, statistics, and machine learning.",
        "what is cyber security": "Cyber Security is the field of protecting computers, networks, and data from hacking, threats, and digital attacks.",
        "cyber security": "Cyber Security is a strong career option for students interested in networking, ethical hacking, digital protection, and security systems.",
        "cybersecurity": "Cyber Security is a strong career option for students interested in networking, ethical hacking, digital protection, and security systems.",
        "what is ui ux": "UI/UX means User Interface and User Experience Design. It focuses on making websites and apps easy, attractive, and user-friendly.",
        "ui ux": "UI/UX Design is a great career for creative students who enjoy design, app layouts, website interfaces, and user-friendly digital products.",
        "ui/ux": "UI/UX Design is a great career for creative students who enjoy design, app layouts, website interfaces, and user-friendly digital products.",
        "animation": "Animation is a creative field where you can work in films, games, advertising, digital media, and content creation.",
        "what is animation": "Animation is the process of creating moving visuals using drawings, graphics, or software. It offers careers in films, gaming, VFX, and media.",

        "best career after bca": "After BCA, strong career options include Software Developer, Web Developer, App Developer, Data Analyst, UI/UX Designer, Cyber Security Analyst, and MCA for higher studies.",
        "best career after bsc it": "After BSc IT, good career options include Software Developer, Data Analyst, Web Developer, Cloud Engineer, Cyber Security Analyst, System Administrator, and MCA or MSc IT.",
        "best career after mba": "After MBA, strong career options include Marketing Manager, HR Manager, Business Analyst, Sales Manager, Operations Manager, Financial Analyst, and Entrepreneur.",
        "best career after commerce": "After Commerce, strong career options include CA, CS, CMA, BCom, BBA, Banking, Finance, Digital Marketing, Business Analytics, and Law.",
        "best career after arts": "After Arts, strong career options include BA, Law, Journalism, Psychology, Social Work, Design, Hotel Management, Event Management, Animation, and Government job preparation.",
        "best career after science": "After Science, strong options include Engineering, Pharmacy, BSc IT, BCA, Biotechnology, Nursing, Design, Pure Sciences, Architecture, and AI-related courses.",
        "career in coding": "If you like coding, good career options include Software Developer, Web Developer, App Developer, Full Stack Developer, Data Analyst, and AI Engineer.",
        "career in finance": "Finance careers include Accountant, Financial Analyst, Investment Banker, Tax Consultant, Auditor, Banking Professional, and MBA Finance roles.",
        "career in management": "Management careers include HR, Marketing, Operations, Sales, Business Development, Project Management, and Entrepreneurship.",
        "career in design": "Design careers include UI/UX Designer, Graphic Designer, Animator, Fashion Designer, Product Designer, Interior Designer, and Communication Designer.",

        "best course after 12th science": "After 12th Science, popular courses include Engineering, Pharmacy, BSc IT, BCA, Biotechnology, Nursing, Architecture, Design, and pure science courses.",
        "best course after 12th commerce": "After 12th Commerce, good courses include BCom, BBA, CA, CS, CMA, Banking, Finance, Digital Marketing, Hotel Management, and Law.",
        "best course after 12th arts": "After 12th Arts, you can choose BA, BJMC, Law, Psychology, Design, Hotel Management, Animation, Social Work, and Event Management.",
        "courses after pcm": "After PCM, top courses include Engineering, BSc Computer Science, BSc IT, Architecture, Aviation, Design, Data Science, and Defence-related careers.",
        "courses after pcb": "After PCB, strong options include MBBS, BDS, BAMS, BHMS, Nursing, Pharmacy, Biotechnology, Microbiology, and Allied Health Sciences.",
        "courses without maths": "Without Maths, you can still go for BCA in some colleges, BBA, Law, Design, Hotel Management, Media, Psychology, and many non-engineering courses.",
        "career after low percentage": "Even with low percentage, you can build a strong career through skill-based courses, certifications, diploma programs, digital skills, design, coding, or management pathways.",
        "diploma after 12th": "Diploma courses after 12th include Diploma in Engineering, Design, Animation, Hotel Management, Computer Applications, Digital Marketing, and Nursing-related fields.",
        "degree after 12th": "Degree options after 12th depend on your stream. Popular ones include BTech, BCA, BSc IT, BCom, BBA, BA, BDes, and Law.",
        "best private college courses": "The best private college course depends on your interests. In general, BTech, BCA, BSc IT, BBA, Design, Law, and Pharmacy are popular choices.",

        "how to become software developer": "To become a Software Developer, learn programming languages like Python, Java, or C++, practice coding, build projects, use GitHub, and apply for internships or fresher roles.",
        "how to become data analyst": "To become a Data Analyst, learn Excel, SQL, Python, statistics, and Power BI or Tableau. Build projects using data dashboards and analysis.",
        "how to become ethical hacker": "To become an Ethical Hacker, learn networking, Linux, security basics, penetration testing tools, and ethical hacking concepts. Certifications can help.",
        "how to become web developer": "To become a Web Developer, learn HTML, CSS, JavaScript, and a backend language like Python or PHP. Build websites and publish projects online.",
        "how to become app developer": "To become an App Developer, learn Android development, Flutter, React Native, or Kotlin. Build sample apps and upload them to a portfolio.",
        "how to become ai engineer": "To become an AI Engineer, learn Python, machine learning, mathematics, data handling, and model building. Start with data science and ML projects.",
        "python career scope": "Python has excellent career scope in software development, data science, automation, AI, web development, and backend programming.",
        "java career scope": "Java has strong career scope in enterprise software, backend development, Android development, and large-scale application systems.",
        "cloud computing jobs": "Cloud Computing jobs include Cloud Engineer, DevOps Engineer, Cloud Administrator, Solutions Architect, and Infrastructure Engineer.",
        "full stack developer scope": "Full Stack Development has strong scope because companies value developers who can work on both frontend and backend systems.",

        "bca salary in india": "BCA freshers can start around 2.5 to 5 LPA depending on skills, city, and company. Strong skills can increase salary faster.",
        "mba salary in india": "MBA salary depends on specialization and college. Freshers may start around 4 to 10 LPA, while top colleges can offer more.",
        "data analyst salary": "A Data Analyst fresher in India may start around 4 to 8 LPA depending on skills like SQL, Excel, Python, and Power BI.",
        "software engineer salary": "Software Engineer salary depends on skills and company. Freshers may start around 3.5 to 8 LPA, with higher packages in strong companies.",
        "ui ux designer salary": "UI/UX Designers can start around 3 to 7 LPA, and experienced designers can earn much more with strong portfolios.",
        "cyber security salary": "Cyber Security professionals can start around 4 to 8 LPA, and salaries increase significantly with certifications and experience.",
        "fresher it salary": "IT fresher salary usually depends on role and skill level. It may range from 2.5 to 6 LPA or more.",
        "highest paying jobs after graduation": "Some high-paying jobs after graduation include Software Developer, Data Scientist, Product Manager, Investment Banker, Management Consultant, and Cloud Engineer.",
        "career with high salary": "High-salary careers often include Data Science, Software Engineering, AI, Cyber Security, Finance, Management, and specialized technical roles.",
        "jobs after bsc it salary": "After BSc IT, salaries usually depend on role and skills. Common starting range is around 3 to 6 LPA, with good growth after experience.",

        "skills for software job": "Important skills for software jobs include programming, problem solving, databases, DSA basics, GitHub, testing, and communication.",
        "skills for mba students": "MBA students should build communication, leadership, presentation, Excel, decision-making, analytical thinking, and networking skills.",
        "skills for data science": "Important data science skills include Python, SQL, statistics, machine learning basics, Excel, data visualization, and problem solving.",
        "communication skills importance": "Communication skills are very important in every career because they help in teamwork, interviews, presentations, leadership, and professional growth.",
        "best technical skills in 2026": "Strong technical skills for 2026 include Python, AI tools, Data Analytics, Cloud, Cyber Security, Full Stack Development, UI/UX, and Automation.",
        "skills after bca": "After BCA, build Python, Java, web development, SQL, cloud basics, GitHub projects, and interview preparation skills.",
        "coding skills roadmap": "A coding roadmap should start with one language, then DSA basics, projects, GitHub, databases, web basics, and interview practice.",
        "excel skills for jobs": "Excel is very useful for jobs in business, analysis, operations, HR, and finance. Learn formulas, pivot tables, charts, and data cleaning.",
        "interview skills": "Interview skills include confidence, good communication, clarity, resume knowledge, technical basics, body language, and preparation.",
        "resume skills": "A resume should highlight technical skills, tools, certifications, internships, projects, achievements, and communication strengths.",

        "career in graphic design": "Graphic Design is a good career for creative students who enjoy visuals, branding, social media design, and digital communication.",
        "career in ui ux": "UI/UX is one of the best creative-tech careers. It mixes design, user psychology, product thinking, and digital experience.",
        "career in animation": "Animation offers careers in gaming, film, content creation, media, education, and digital entertainment.",
        "career in gaming": "Gaming careers include Game Designer, Game Developer, 3D Artist, Animator, Level Designer, and QA Tester.",
        "career in vfx": "VFX is a strong creative field for students interested in film, motion graphics, editing, and digital effects.",
        "career in photography": "Photography can lead to careers in fashion, product, wedding, commercial, travel, journalism, and content creation.",
        "career in fashion design": "Fashion Design is suitable for creative students interested in clothing, styling, trends, branding, and apparel creation.",
        "career in communication design": "Communication Design combines visual design, branding, media, and digital creativity for effective communication.",
        "career in digital media": "Digital Media offers careers in content creation, video editing, branding, digital campaigns, design, and online marketing.",
        "career in content creation": "Content creation can become a strong career through writing, video, design, teaching, reviewing, or niche-based social media work.",

        "mba specializations": "Popular MBA specializations include Marketing, Finance, HR, Operations, Business Analytics, International Business, and Entrepreneurship.",
        "marketing career options": "Marketing careers include Digital Marketer, Brand Manager, Sales Manager, Content Strategist, SEO Analyst, and Product Marketing roles.",
        "hr career options": "HR careers include Recruiter, HR Executive, Talent Acquisition Specialist, Learning and Development Officer, and HR Manager.",
        "finance career options": "Finance careers include Accountant, Auditor, Financial Analyst, Banker, Tax Consultant, Investment Analyst, and Risk Analyst.",
        "entrepreneurship after college": "Entrepreneurship after college can be a great option if you have a business idea, leadership ability, and willingness to learn and take risks.",
        "business analyst career": "Business Analyst is a good career for students who like problem solving, data, communication, and business process improvement.",
        "operations management career": "Operations careers focus on planning, efficiency, supply chain, workflow, and business process management.",
        "banking career options": "Banking careers include PO, Clerk, Relationship Manager, Credit Analyst, Loan Officer, and Financial Services roles.",
        "investment banking scope": "Investment Banking offers high-growth careers but usually needs strong finance knowledge, analytical ability, and often higher studies or top institutions.",
        "family business mba useful": "Yes, MBA can be very useful for family business because it improves finance, management, strategy, operations, and growth planning.",

        "study abroad after graduation": "Study abroad after graduation is a good option if you want international exposure, specialized education, and global career opportunities.",
        "jobs abroad after bca": "After BCA, jobs abroad may require strong skills, experience, certifications, and sometimes higher studies like MCA or MS.",
        "future jobs in ai": "Future jobs in AI include AI Engineer, Machine Learning Engineer, Data Scientist, Prompt Designer, AI Product Specialist, and Automation roles.",
        "best careers in 2030": "Careers expected to grow strongly by 2030 include AI, Data Science, Cloud Computing, Cyber Security, Healthcare, Renewable Energy, and Digital Business.",
        "remote jobs future": "Remote jobs will continue growing in software, design, content, data, support, consulting, and digital marketing.",
        "career after automation": "Automation will replace some tasks, but careers in AI, analytics, product design, management, problem solving, and creativity will remain strong.",
        "jobs safe from ai": "Jobs that strongly involve creativity, leadership, strategy, empathy, communication, design, and complex decision-making are safer from AI replacement.",
        "international mba scope": "International MBA can provide strong global exposure, networking, and career opportunities, but it should be chosen carefully because it can be expensive.",
        "skills for future jobs": "Future job skills include adaptability, digital literacy, communication, AI awareness, problem solving, coding, data analysis, and creativity.",
        "ai replacing jobs": "AI may automate some repetitive work, but it will also create new jobs. Students should focus on future-ready skills instead of fearing AI.",

        "i am confused about career": "That is normal. Start by identifying your interests, strengths, favorite subjects, and long-term goals. Then choose a course or career path that matches them.",
        "which course suits me": "Tell me your stream, favorite subjects, and interests. Then I can suggest a more suitable course for you.",
        "how to choose career": "Choose a career based on your interests, skills, personality, strengths, future demand, and willingness to learn. Never choose only by pressure or trend.",
        "low marks what to do": "Low marks do not end your future. Focus on skill-building, practical learning, certifications, and choosing a field that matches your strengths.",
        "no interest in studies what career": "If you are not interested in traditional study, consider skill-based areas like design, digital marketing, photography, animation, sales, UI/UX, or entrepreneurship.",
        "i like computers what should i do": "If you like computers, strong options include BCA, BSc IT, Computer Engineering, Cyber Security, Data Analytics, Cloud, or Web Development.",
        "i like business what should i do": "If you like business, consider BBA, BCom, MBA, Marketing, Entrepreneurship, Finance, Business Analytics, or family business management.",
        "i like design what should i do": "If you like design, consider UI/UX, Graphic Design, Animation, Fashion Design, Product Design, or Communication Design.",
        "i want government job path": "For government jobs, choose a graduation course you can manage well, then prepare for SSC, Banking, UPSC, State PSC, Railways, or other exams.",
        "best career for me": "Tell me your stream, your interests, what subjects you enjoy, and whether you like coding, business, design, or helping people. Then I can guide better.",

        "hello": "Hello! I am your Career Guidance Assistant. You can ask me about careers, courses, salaries, future scope, or skills.",
        "hi": "Hi! I can help you with course selection, career options, skills, and job-related guidance.",
        "hii": "Hello! Ask me anything about careers, courses, future scope, or jobs.",
        "hey": "Hey! I am here to help you with career guidance.",
        "course": "Please tell me which field or stream you are interested in, and I will suggest suitable courses.",
        "career": "Please tell me your stream or interest area like IT, design, business, or healthcare, and I will guide you.",
        "salary": "Salary depends on your course, role, city, company, and most importantly your skills. Strong skills improve salary a lot.",
        "skills": "Good skills include communication, problem solving, digital tools, teamwork, and domain-specific technical skills.",
        "jobs": "Tell me the field you are interested in, such as IT, management, finance, design, or government jobs, and I will suggest roles."
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
