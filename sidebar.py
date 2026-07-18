import time
from nicegui import ui, app

from config import ONLINE_THRESHOLD_SECONDS
from styles import pulse_dot_html

def render_sidebar(admin: bool, db, on_navigate=None):
    pages = (
        ["Tests", "Live Quiz", "Leaderboard"] if admin
        else ["Tests", "Practice", "Leaderboard"]
    )
    
    # This safely creates the top-level LeftDrawer
    with ui.left_drawer().classes('bg-[#10151f] border-r border-[#e7eaf029] p-4 flex flex-col justify-between'):
        nav_menu(pages, on_navigate)
        roster_menu(db)

@ui.refreshable
def nav_menu(pages, on_navigate):
    current_page = app.storage.user.get("nav_page", pages[0])
    if current_page not in pages:
        current_page = pages[0]
        app.storage.user["nav_page"] = current_page

    with ui.column().classes('w-full'):
        ui.label("Navigate").classes("text-lg font-bold mb-4 text-[#e7eaf0]")
        
        for page in pages:
            is_active = current_page == page
            
            def handle_click(p=page):
                app.storage.user["nav_page"] = p
                nav_menu.refresh(pages, on_navigate) # Update button colors locally
                if on_navigate:
                    on_navigate() # Tell the main page to change
            
            btn = ui.button(page, on_click=handle_click).classes('w-full mb-2 justify-start')
            if is_active:
                btn.props('color=primary')
            else:
                btn.props('flat color=white text-color=grey-4')

        ui.separator().classes('my-6 bg-[#e7eaf029]')

@ui.refreshable
def roster_menu(db):
    with ui.column().classes('w-full mt-auto'):
        ui.label("Online Now").classes("text-lg font-bold mb-4 text-[#e7eaf0]")

        current_time = time.time()
        users_sorted = sorted(
            db["users"].items(),
            key=lambda kv: (current_time - kv[1].get("last_seen", 0) >= ONLINE_THRESHOLD_SECONDS, kv[0]),
        )

        for user, info in users_sorted:
            is_online = current_time - info.get("last_seen", 0) < ONLINE_THRESHOLD_SECONDS
            role_tag = "ADMIN" if info.get("role") == "admin" else "STUDENT"
            name_class = "roster-name" if is_online else "roster-name offline"

            ui.html(
                f"""
                <div class="roster-row">
                    {pulse_dot_html(is_online)}
                    <span class="{name_class}">{user.capitalize()}</span>
                    <span class="roster-role-tag">{role_tag}</span>
                </div>
                """
            )

        ui.separator().classes('my-6 bg-[#e7eaf029]')
        
        def handle_logout():
            app.storage.user.update({
                'logged_in': False,
                'username': "",
                'role': ""
            })
            app.storage.user.pop("nav_page", None)
            ui.navigate.reload()
            
        ui.button("Log Out", on_click=handle_logout).props('outline color=negative').classes('w-full')
