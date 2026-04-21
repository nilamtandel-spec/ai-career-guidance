from werkzeug.security import generate_password_hash, check_password_hash
from modules.db import get_db_connection

def register_user(name, email, password):
    if not name or not email or not password:
        return False, "All fields are required."

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return False, "Email already registered."

    hashed_password = generate_password_hash(password)
    cursor.execute(
        "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
        (name, email, hashed_password)
    )
    conn.commit()
    conn.close()
    return True, "Registration successful."

def login_user(email, password):
    if not email or not password:
        return False, "Email and password are required."

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return False, "User not found."

    if not check_password_hash(user["password"], password):
        return False, "Invalid password."

    return True, user

def login_admin(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE username = ?", (username,))
    admin = cursor.fetchone()
    conn.close()

    if not admin:
        return False, "Admin not found."

    if not check_password_hash(admin["password"], password):
        return False, "Invalid password."

    return True, admin
