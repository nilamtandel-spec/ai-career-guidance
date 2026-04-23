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
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None

# Init DB
init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")


@app.route("/ask-ai", methods=["POST"])
def ask_ai():
    user_message = request.json.get("message", "").strip().lower()

    if not user_message:
        return jsonify({"reply": "Please type a question."})

    # FREE fallback chatbot
    qa = {
        "hi": "Hello 👋 I am AI Career Guidance Bot.",
        "hello": "Hello 👋 Ask me any career question.",
        "bca": "BCA is best for coding, software jobs, app development, IT careers.",
        "mba": "MBA is best for management, HR, marketing, finance careers.",
        "bsc it": "BSc IT is best for IT, software, cloud, networking jobs.",
        "cyber security": "Cyber Security is excellent future career in hacking prevention.",
        "ui ux": "UI/UX is great creative career in app and website design.",
        "after 12th science": "After 12th Science: Engineering, BCA, BSc IT, Pharmacy, Design.",
        "after 12th commerce": "After Commerce: BCom, BBA, CA, CS, MBA path.",
        "after 12th arts": "After Arts: BA, Law, Design, Psychology, Journalism.",
        "salary": "Salary depends on skills, city, company and experience.",
        "job": "Tell me your course name, I will suggest jobs.",
    }

    for q in qa:
        if q in user_message:
            return jsonify({"reply": qa[q]})

    # Gemini AI if available
    if model:
        try:
            response = model.generate_content(user_message)
            return jsonify({"reply": response.text})
        except:
            pass

    return jsonify({"reply": "Please ask about careers, courses, salary, jobs, or future scope."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
