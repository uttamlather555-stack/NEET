from nicegui import ui

# ----------------------------
# PAGE CONFIG
# ----------------------------
def setup_page():
    # In NiceGUI, page layout (wide/boxed) is handled via CSS or container classes.
    # We set the browser tab title here.
    ui.page_title("NEET Test Console")

# ----------------------------
# MISC
# ----------------------------
ONLINE_THRESHOLD_SECONDS = 15
AUTOREFRESH_MS = 3000

# ----------------------------
# FULL-LENGTH TEST DEFAULTS
# ----------------------------
DEFAULT_TEST_DURATION_MINUTES = 180  # 3 hours
DEFAULT_TEST_QUESTION_COUNT = 180
DEFAULT_MARKS_CORRECT = 4
DEFAULT_MARKS_WRONG = -1
DIFFICULTY_LEVELS = ["Easy", "Medium", "Hard"]
