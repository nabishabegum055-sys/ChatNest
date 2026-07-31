import os
import sqlite3

from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    redirect,
    url_for,
    session
)

from werkzeug.security import generate_password_hash, check_password_hash

# Gmail API
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


app = Flask(__name__)

app.secret_key = "chatnest-secret-key-2026"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "database.db")

# ==================================================
# GMAIL SETTINGS
# ==================================================

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]

GMAIL_CREDENTIALS = os.path.join(BASE_DIR, "credentials.json")
GMAIL_TOKEN = os.path.join(BASE_DIR, "token.json")


# ==================================================
# DATABASE INITIALIZATION
# ==================================================

def init_db():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            image_url TEXT DEFAULT '',
            status TEXT DEFAULT 'Delivered',
            is_starred INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# ==================================================
# ADD MESSAGE
# ==================================================

def add_message(platform, sender, message, image_url=""):

    init_db()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO messages
        (platform, sender, message, image_url)
        VALUES (?, ?, ?, ?)
    """, (
        platform,
        sender,
        message,
        image_url
    ))

    conn.commit()
    conn.close()


# ==================================================
# LOAD MESSAGES
# ==================================================

def load_messages(search_query=None):

    init_db()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if search_query:

        query = f"%{search_query}%"

        cursor.execute("""
            SELECT
                id,
                platform,
                sender,
                message,
                image_url,
                status,
                is_starred,
                timestamp
            FROM messages
            WHERE sender LIKE ?
               OR message LIKE ?
               OR platform LIKE ?
            ORDER BY id DESC
        """, (
            query,
            query,
            query
        ))

    else:

        cursor.execute("""
            SELECT
                id,
                platform,
                sender,
                message,
                image_url,
                status,
                is_starred,
                timestamp
            FROM messages
            ORDER BY id DESC
        """)

    rows = cursor.fetchall()
    conn.close()

    messages = []

    for row in rows:

        messages.append({
            "id": row[0],
            "platform": row[1],
            "sender": row[2],
            "message": row[3],
            "image_url": row[4],
            "status": row[5],
            "is_starred": row[6],
            "timestamp": row[7]
        })

    return messages


init_db()


# ==================================================
# GMAIL SERVICE
# ==================================================

def get_gmail_service():

    creds = None

    # Existing token irundha use pannum
    if os.path.exists(GMAIL_TOKEN):

        try:
            creds = Credentials.from_authorized_user_file(
                GMAIL_TOKEN,
                GMAIL_SCOPES
            )

        except Exception as e:
            print("Token load error:", e)
            creds = None

    # Token invalid / missing
    if not creds or not creds.valid:

        # Refresh token irundha refresh pannum
        if creds and creds.expired and creds.refresh_token:

            try:
                creds.refresh(Request())

            except Exception as e:
                print("Token refresh error:", e)
                creds = None

        # Fresh Google login
        if not creds:

            if not os.path.exists(GMAIL_CREDENTIALS):
                raise FileNotFoundError(
                    "credentials.json file not found in project folder."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                GMAIL_CREDENTIALS,
                GMAIL_SCOPES
            )

            creds = flow.run_local_server(port=0)

        # Save token
        with open(GMAIL_TOKEN, "w") as token:
            token.write(creds.to_json())

    service = build(
        "gmail",
        "v1",
        credentials=creds
    )

    return service


# ==================================================
# FETCH GMAIL MESSAGES
# ==================================================

def load_gmail_messages():

    service = get_gmail_service()

    result = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        maxResults=20
    ).execute()

    gmail_items = result.get("messages", [])

    emails = []

    for item in gmail_items:

        msg = service.users().messages().get(
            userId="me",
            id=item["id"],
            format="metadata",
            metadataHeaders=[
                "From",
                "Subject",
                "Date"
            ]
        ).execute()

        headers = msg.get(
            "payload",
            {}
        ).get(
            "headers",
            []
        )

        sender = "Unknown"
        subject = "(No Subject)"
        date = ""

        for header in headers:

            name = header.get(
                "name",
                ""
            ).lower()

            value = header.get(
                "value",
                ""
            )

            if name == "from":
                sender = value

            elif name == "subject":
                subject = value

            elif name == "date":
                date = value

        emails.append({
            "id": msg.get("id"),
            "platform": "Email",
            "sender": sender,
            "subject": subject,
            "message": msg.get("snippet", ""),
            "timestamp": date,
            "status": "Received",
            "image_url": "",
            "is_starred": 0
        })

    return emails


# ==================================================
# HOME
# ==================================================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# ==================================================
# SIGNUP
# ==================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not name or not email or not password:

            return """
                <h3>All fields are required.</h3>
                <a href="/signup">Go Back</a>
            """

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            conn.close()

            return """
                <h3>Email already registered.</h3>
                <a href="/login">Sign In</a>
            """

        hashed_password = generate_password_hash(
            password
        )

        cursor.execute("""
            INSERT INTO users
            (name, email, password)
            VALUES (?, ?, ?)
        """, (
            name,
            email,
            hashed_password
        ))

        conn.commit()
        conn.close()

        return redirect(
            url_for("login")
        )

    return render_template(
        "signup.html"
    )


# ==================================================
# LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        conn = sqlite3.connect(DB_NAME)

        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """, (
            email,
        ))

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            session["user_email"] = user["email"]

            return redirect(
                url_for("dashboard")
            )

        return """
            <h3>Invalid email or password.</h3>
            <a href="/login">Try Again</a>
        """

    return render_template(
        "login.html"
    )


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ==================================================
# DASHBOARD
# ==================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    return render_template(
        "dashboard.html",
        user_name=session.get(
            "user_name"
        )
    )


# ==================================================
# GET NORMAL MESSAGES API
# ==================================================

@app.route("/api/messages", methods=["GET"])
def fetch_messages():

    if "user_id" not in session:

        return jsonify({
            "status": "error",
            "message": "Login required"
        }), 401

    try:

        search = request.args.get("q")

        messages = load_messages(
            search
        )

        return jsonify(
            messages
        )

    except Exception as e:

        print(
            "Load message error:",
            e
        )

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ==================================================
# GMAIL API
# ==================================================

@app.route("/api/gmail", methods=["GET"])
def fetch_gmail():

    if "user_id" not in session:

        return jsonify({
            "status": "error",
            "message": "Login required"
        }), 401

    try:

        emails = load_gmail_messages()

        print(
            "Gmail messages loaded:",
            len(emails)
        )

        return jsonify(
            emails
        )

    except Exception as e:

        print(
            "Gmail error:",
            e
        )

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ==================================================
# GMAIL TRASH API
# ==================================================

@app.route("/api/gmail/trash/<message_id>", methods=["POST"])
def trash_gmail_message(message_id):

    if "user_id" not in session:
        return jsonify({
            "status": "error",
            "message": "Login required"
        }), 401

    try:
        service = get_gmail_service()

        service.users().messages().trash(
            userId="me",
            id=message_id
        ).execute()

        return jsonify({
            "status": "success",
            "message": "Gmail message moved to Trash"
        })

    except Exception as e:
        print("Gmail trash error:", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ==================================================
# SEND MESSAGE API
# ==================================================

@app.route("/api/send", methods=["POST"])
def send_message():

    if "user_id" not in session:

        return jsonify({
            "status": "error",
            "message": "Login required"
        }), 401

    try:

        data = request.get_json(
            silent=True
        ) or {}

        platform = data.get(
            "platform",
            "Web"
        )

        sender = session.get(
            "user_name",
            "Admin"
        )

        message = data.get(
            "message",
            ""
        )

        image_url = data.get(
            "image_url",
            ""
        )

        if (
            not message.strip()
            and
            not image_url.strip()
        ):

            return jsonify({
                "status": "error",
                "message": "Message cannot be empty"
            }), 400

        add_message(
            platform,
            sender,
            message,
            image_url
        )

        print(
            f"Message saved: "
            f"{platform} | "
            f"{sender} | "
            f"{message}"
        )

        return jsonify({
            "status": "success",
            "message": "Message sent successfully"
        })

    except Exception as e:

        print(
            "Send message error:",
            e
        )

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ==================================================
# DELETE MESSAGE API
# ==================================================

@app.route(
    "/api/delete/<int:msg_id>",
    methods=["DELETE"]
)
def delete_message(msg_id):

    if "user_id" not in session:

        return jsonify({
            "status": "error",
            "message": "Login required"
        }), 401

    try:

        conn = sqlite3.connect(
            DB_NAME
        )

        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM messages WHERE id = ?",
            (msg_id,)
        )

        conn.commit()
        conn.close()

        return jsonify({
            "status": "success"
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ==================================================
# TELEGRAM WEBHOOK
# ==================================================

@app.route(
    "/telegram-webhook",
    methods=["POST"]
)
def telegram_webhook():

    data = request.get_json(
        silent=True
    ) or {}

    message_data = data.get(
        "message"
    )

    if message_data:

        chat = message_data.get(
            "chat",
            {}
        )

        text = message_data.get(
            "text",
            ""
        )

        sender_name = chat.get(
            "first_name",
            "Telegram User"
        )

        if text:

            add_message(
                "Telegram",
                sender_name,
                text
            )

    return jsonify({
        "status": "ok"
    })


# ==================================================
# WHATSAPP WEBHOOK
# ==================================================

@app.route(
    "/whatsapp-webhook",
    methods=["POST"]
)
def whatsapp_webhook():

    incoming_msg = request.values.get(
        "Body",
        ""
    )

    sender = request.values.get(
        "From",
        ""
    )

    print(
        f"New WhatsApp Message Received: "
        f"'{incoming_msg}' from {sender}"
    )

    if incoming_msg.strip():

        add_message(
            "WhatsApp",
            sender,
            incoming_msg
        )

    return "OK", 200


# ==================================================
# RUN
# ==================================================
# ==================================================
# SMS WEBHOOK
# ==================================================

@app.route("/api/sms", methods=["POST"])
def receive_sms():
    try:
        # Accept JSON or normal form data
        data = request.get_json(silent=True) or {}

        sender = (
            data.get("sender")
            or data.get("number")
            or data.get("from")
            or request.form.get("sender")
            or request.form.get("number")
            or request.form.get("from")
            or "Unknown"
        )

        message = (
            data.get("message")
            or data.get("body")
            or data.get("text")
            or request.form.get("message")
            or request.form.get("body")
            or request.form.get("text")
            or ""
        )

        sender = str(sender).strip()
        message = str(message).strip()

        if not message:
            return jsonify({
                "status": "error",
                "message": "SMS message is empty"
            }), 400

        add_message(
            "SMS",
            sender,
            message
        )

        print("SMS RECEIVED")
        print("From:", sender)
        print("Message:", message)

        return jsonify({
            "status": "success",
            "message": "SMS saved successfully"
        }), 200

    except Exception as e:
        print("SMS ERROR:", e)

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":

    init_db()

    print(
        "ChatNest running on "
        "http://127.0.0.1:5000"
    )

    app.run(
        host="0.0.0.0",
        debug=True,
        port=5000
    )
