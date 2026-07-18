import os
import asyncio
from nicegui import ui, app

from config import setup_page, AUTOREFRESH_MS
from styles import inject_css
from database import load_db, touch_user_last_seen, DatabaseUnavailableError
from auth import render_login_signup
from admin_dashboard import render_admin_dashboard
from student_dashboard import render_student_dashboard

# Setup and CSS inject
setup_page()
inject_css()

@ui.page('/')
def main_page():
    # ---------------- LOAD + TOUCH PRESENCE ----------------
    try:
        db = load_db()
    except DatabaseUnavailableError:
        ui.notify("Lost connection to the database. Retrying...", type="negative")
        return # Stop rendering page

    # ---------------- SESSION STATE ----------------
    # In NiceGUI, we use app.storage.user for user-specific session data
    logged_in = app.storage.user.get("logged_in", False)
    username = app.storage.user.get("username", "")
    role = app.storage.user.get("role", "")

    # ---------------- LIVE SYNC ----------------
    # ui.timer automatically loops at the given interval (in seconds)
    def sync_db():
        try:
            nonlocal db
            db = load_db()
        except DatabaseUnavailableError:
            pass
            
    ui.timer(AUTOREFRESH_MS / 1000.0, sync_db)

    # ---------------- LOGIN GATE & ROUTING ----------------
    if not logged_in:
        render_login_signup()
        return

    touch_user_last_seen(username)

    if role == "admin":
        render_admin_dashboard(db)
    elif role == "student":
        render_student_dashboard(db)


if __name__ in {"__main__", "__mp_main__"}:
    # Render assigns the PORT environment variable dynamically.
    # We default to 8080 for local testing.
    port = int(os.environ.get('PORT', 8080))
    
    # storage_secret is required to encrypt the browser cookies for user sessions.
    ui.run(
        host='0.0.0.0', 
        port=port, 
        storage_secret='super_secret_key_change_me' # IMPORTANT: Change this to a random string!
    )
