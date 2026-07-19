import time
from nicegui import ui, app

from config import ONLINE_THRESHOLD_SECONDS
from styles import pulse_dot_html

# Icon per nav page - keeps the sidebar from being a wall of plain buttons
_PAGE_ICONS = {
    "Tests": "assignment",
    "Live Quiz": "bolt",
    "Practice": "school",
    "Leaderboard": "emoji_events",
}


def render_sidebar(admin: bool, db, on_navigate=None) -> str:
    """Renders the left drawer (nav + roster) and returns the currently active page."""
    pages = (
        ["Tests", "Live Quiz", "Leaderboard"] if admin
        else ["Tests", "Practice", "Leaderboard"]
    )

    with ui.left_drawer().classes('app-drawer p-0 flex flex-col justify-between'):
        with ui.column().classes('w-full p-4 flex-grow'):
            _render_brand(admin)
            nav_menu(pages, on_navigate)
        with ui.column().classes('w-full p-4'):
            roster_menu(db)

    current_page = app.storage.user.get("nav_page", pages[0])
    if current_page not in pages:
        current_page = pages[0]
        app.storage.user["nav_page"] = current_page
    return current_page


def _render_brand(admin: bool):
    role_text = "Admin Console" if admin else "Student Portal"
    ui.html(
        f"""
        <div class="drawer-brand">
            <div class="drawer-brand-mark">N</div>
            <div>
                <div class="drawer-brand-title">NEET Console</div>
                <div class="drawer-brand-sub">{role_text}</div>
            </div>
        </div>
        """
    )


@ui.refreshable
def nav_menu(pages, on_navigate):
    current_page = app.storage.user.get("nav_page", pages[0])
    if current_page not in pages:
        current_page = pages[0]
        app.storage.user["nav_page"] = current_page

    with ui.column().classes('w-full gap-1 mt-2'):
        for page in pages:
            is_active = current_page == page
            icon = _PAGE_ICONS.get(page, "circle")

            def handle_click(p=page):
                app.storage.user["nav_page"] = p
                nav_menu.refresh(pages, on_navigate)
                if on_navigate:
                    on_navigate()

            row_class = "nav-item active" if is_active else "nav-item"
            with ui.row().classes(row_class).on('click', handle_click):
                ui.icon(icon).classes('nav-item-icon')
                ui.label(page).classes('nav-item-label')


@ui.refreshable
def roster_menu(db):
    with ui.column().classes('w-full'):
        ui.label("ONLINE NOW").classes("roster-heading")

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

        ui.separator().classes('my-4 bg-[#e7eaf029]')

        def handle_logout():
            app.storage.user.update({
                'logged_in': False,
                'username': "",
                'role': ""
            })
            app.storage.user.pop("nav_page", None)
            ui.navigate.reload()

        ui.button("Log Out", on_click=handle_logout, icon="logout").props('outline color=negative').classes('w-full')
