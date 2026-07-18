import time
from nicegui import ui, app

from database import load_db, register_user, DatabaseUnavailableError

def render_hero(db):
    total_students = len([u for u, i in db["users"].items() if i["role"] == "student"])
    open_tests = len([t for t in db.get("full_tests", {}).values() if t["status"] == "open"])

    ui.html(
        f"""
        <div class="hero-wrap">
            <div class="hero-eyebrow anim-in">
                <span class="pulse-dot"></span> LIVE SESSION
            </div>
            <div class="hero-title anim-in-delay-1">Practice like it's <em>results day</em>.</div>
            <p class="hero-sub anim-in-delay-2">
                Chapter-wise practice, full-length timed mock tests, and a leaderboard
                that actually tracks who's improving.
            </p>
        </div>
        """
    )
    ui.html(
        f"""
        <div class="vitals-strip anim-in-delay-2">
            <div class="vital-stat"><div class="num mono-num">{total_students}</div><div class="label">Students Enrolled</div></div>
            <div class="vital-stat"><div class="num mono-num">{open_tests}</div><div class="label">Tests Open Now</div></div>
        </div>
        """
    )

def render_login_signup():
    try:
        db = load_db()
    except DatabaseUnavailableError:
        ui.notify("Can't reach the database right now. Please wait a few seconds and refresh the page.", type="negative")
        return # Equivalent to st.stop() in this context

    render_hero(db)

    # Center the login box (replaces st.columns([1, 1.4, 1]))
    with ui.row().classes('w-full justify-center mt-8'):
        # The central form container
        with ui.column().classes('w-full max-w-md'):
            
            with ui.tabs().classes('w-full') as portal_tabs:
                tab_student = ui.tab("Student Login")
                tab_admin = ui.tab("Admin Login")

            with ui.tab_panels(portal_tabs, value=tab_student).classes('w-full bg-transparent p-0'):
                
                # --- STUDENT LOGIN/REGISTER PANEL ---
                with ui.tab_panel(tab_student).classes('p-0 mt-2'):
                    with ui.card().classes('w-full p-6'):
                        
                        with ui.tabs().classes('w-full') as sub_tabs:
                            sub_log = ui.tab("Log In")
                            sub_reg = ui.tab("Create Account")

                        with ui.tab_panels(sub_tabs, value=sub_log).classes('w-full bg-transparent p-0'):
                            
                            # Log In Section
                            with ui.tab_panel(sub_log).classes('p-0 mt-4'):
                                login_username = ui.input("Username").classes('w-full mb-2')
                                login_password = ui.input("Password", password=True, password_toggle_button=True).classes('w-full mb-4')
                                
                                def handle_login():
                                    user_val = login_username.value.strip().lower() if login_username.value else ""
                                    pass_val = login_password.value
                                    
                                    try:
                                        current_db = load_db()
                                    except DatabaseUnavailableError:
                                        ui.notify("Can't reach the database right now. Please try again in a few seconds.", type="negative")
                                        return
                                        
                                    user = current_db["users"].get(user_val)
                                    if user and user["password"] == pass_val and user["role"] == "student":
                                        app.storage.user.update({
                                            'logged_in': True,
                                            'username': user_val,
                                            'role': 'student'
                                        })
                                        ui.navigate.reload() # Refresh page to hit the router in app.py
                                    else:
                                        ui.notify("Incorrect username or password.", type="negative")

                                ui.button("Log In", on_click=handle_login).props('color=primary').classes('w-full')

                            # Create Account Section
                            with ui.tab_panel(sub_reg).classes('p-0 mt-4'):
                                new_username = ui.input("Choose Username").classes('w-full mb-2')
                                new_password = ui.input("Choose Password", password=True, password_toggle_button=True).classes('w-full mb-4')
                                
                                def handle_register():
                                    user_val = new_username.value.strip().lower() if new_username.value else ""
                                    pass_val = new_password.value
                                    
                                    if not user_val or not pass_val:
                                        ui.notify("Please fill in both fields.", type="warning")
                                        return
                                    if user_val == "admin":
                                        ui.notify("That username is reserved.", type="negative")
                                        return
                                    if len(user_val) < 3:
                                        ui.notify("Username too short (minimum 3 characters).", type="warning")
                                        return
                                        
                                    new_user_data = {
                                        "password": pass_val,
                                        "role": "student",
                                        "lifetime_score": 0,
                                        "last_seen": time.time(),
                                        "blocked": False,
                                        "avatar_color": "#5b5fef",
                                    }
                                    
                                    try:
                                        result = register_user(user_val, new_user_data)
                                    except DatabaseUnavailableError:
                                        result = "error"

                                    if result == "taken":
                                        ui.notify("That username is already taken.", type="negative")
                                    elif result == "error":
                                        ui.notify("Could not reach the database. Please try again.", type="negative")
                                    else:
                                        ui.notify("Account created. Switch to the Log In tab.", type="positive")
                                        # Auto-switch back to the login tab and prefill the username
                                        sub_tabs.value = sub_log
                                        login_username.value = user_val

                                ui.button("Create Account", on_click=handle_register).classes('w-full')

                # --- ADMIN LOGIN PANEL ---
                with ui.tab_panel(tab_admin).classes('p-0 mt-2'):
                    with ui.card().classes('w-full p-6'):
                        ui.label("Admin Access").classes('text-lg font-bold mb-4')
                        admin_password = ui.input("Password", password=True, password_toggle_button=True).classes('w-full mb-4')
                        
                        def handle_admin_login():
                            pass_val = admin_password.value
                            try:
                                current_db = load_db()
                            except DatabaseUnavailableError:
                                ui.notify("Can't reach the database right now. Please try again in a few seconds.", type="negative")
                                return
                            
                            if current_db["users"]["admin"]["password"] == pass_val:
                                app.storage.user.update({
                                    'logged_in': True,
                                    'username': 'admin',
                                    'role': 'admin'
                                })
                                ui.navigate.reload()
                            else:
                                ui.notify("Incorrect password.", type="negative")

                        ui.button("Log In", on_click=handle_admin_login).props('color=primary').classes('w-full')
