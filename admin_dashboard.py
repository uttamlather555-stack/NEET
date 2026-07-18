import time
import html as html_lib
from nicegui import ui, app
import asyncio

from database import save_db, DatabaseUnavailableError
from quiz import (
    generate_question, start_quiz, lock_and_reveal, clear_quiz,
    start_auto_quiz, advance_auto_quiz, time_left, is_time_up,
    parse_pasted_questions, start_bank_quiz, render_leaderboard,
    create_full_test, open_full_test, close_full_test, render_full_test_leaderboard,
    full_test_time_left,
)
from ai_providers import has_any_keys_configured, AllProvidersExhaustedError
from sidebar import render_sidebar
from chapters import SUBJECTS, get_chapters
from config import DEFAULT_TEST_DURATION_MINUTES, DEFAULT_TEST_QUESTION_COUNT, DEFAULT_MARKS_CORRECT, DEFAULT_MARKS_WRONG, DIFFICULTY_LEVELS


def render_admin_dashboard(db):
    # 1. Render layout strictly OUTSIDE of refreshable container
    render_sidebar(admin=True, db=db, on_navigate=lambda: admin_content.refresh(db))
    
    # 2. Render dynamic content
    admin_content(db)

@ui.refreshable
def admin_content(db):
    page = app.storage.user.get("nav_page", "Tests")
    
    with ui.column().classes('w-full max-w-5xl mx-auto p-4'):
        if not has_any_keys_configured():
            ui.notify(
                "No AI provider keys are configured yet. Add GROQ_API_KEYS and/or GEMINI_API_KEYS "
                "to your .env file to generate questions.", type="warning"
            )

        ui.html("<h1>Admin Console</h1>")

        if page == "Tests":
            _render_full_test_builder(db)
        elif page == "Live Quiz":
            _render_live_quiz_tab(db)
        elif page == "Leaderboard":
            _render_leaderboard_tab(db)


def _render_full_test_builder(db):
    ui.label("Tests & DPPs").classes('text-2xl font-bold')
    ui.label(
        "The complete question set is generated up front, before students can attempt it... "
        "only their best score counts."
    ).classes('text-sm text-gray-500 mb-4')

    with ui.tabs() as tabs:
        tab_new = ui.tab("Create New")
        tab_manage = ui.tab("Manage Existing")
    
    with ui.tab_panels(tabs, value=tab_new).classes('w-full bg-transparent'):
        with ui.tab_panel(tab_new):
            _render_new_test_form(db)
        with ui.tab_panel(tab_manage):
            _render_existing_tests(db)


def _render_new_test_form(db):
    with ui.card().classes('w-full p-4'):
        test_type = ui.radio(
            ["test", "dpp"], 
            value="test"
        ).props('inline')
        
        def update_labels():
            is_dpp = test_type.value == "dpp"
            title.placeholder = "e.g. DPP — Thermodynamics, 20 July" if is_dpp else "e.g. NEET Full Syllabus Mock #3"
            btn_generate.text = "Generate DPP" if is_dpp else "Generate Test"
            if is_dpp:
                col_dur.set_visibility(False)
                dpp_caption.set_visibility(True)
                q_count.value = 10
            else:
                col_dur.set_visibility(True)
                dpp_caption.set_visibility(False)
                q_count.value = DEFAULT_TEST_QUESTION_COUNT

        test_type.on_value_change(update_labels)

        title = ui.input("Title", placeholder="e.g. NEET Full Syllabus Mock #3").classes('w-full mb-4')
        scope = ui.radio(["Single Chapter", "Multiple Chapters", "Full Subject", "Full Syllabus (all subjects)"], value="Single Chapter").props('inline')

        scope_single = ui.row().classes('w-full gap-4')
        with scope_single:
            subj_single = ui.select(SUBJECTS, value=SUBJECTS[0], label="Subject")
            chap_single = ui.select(get_chapters(SUBJECTS[0]), value=get_chapters(SUBJECTS[0])[0], label="Chapter")
            subj_single.on_value_change(lambda e: chap_single.set_options(get_chapters(e.value)))

        scope_multi = ui.row().classes('w-full gap-4').style('display: none;')
        with scope_multi:
            subj_multi = ui.select(SUBJECTS, value=SUBJECTS[0], label="Subject")
            chap_multi = ui.select(get_chapters(SUBJECTS[0]), label="Chapters", multiple=True).classes('min-w-[200px]')
            subj_multi.on_value_change(lambda e: chap_multi.set_options(get_chapters(e.value)))

        scope_full_subj = ui.row().classes('w-full gap-4').style('display: none;')
        with scope_full_subj:
            subj_full = ui.select(SUBJECTS, value=SUBJECTS[0], label="Subject")
            ui.label().bind_text_from(subj_full, 'value', backward=lambda v: f"Covers all chapters of {v}.").classes('text-gray-500 self-center')

        scope_full_syl = ui.label("Covers all chapters across all subjects.").classes('text-gray-500 mb-4').style('display: none;')

        def update_scope_visibility():
            v = scope.value
            scope_single.style('display: flex;' if v == 'Single Chapter' else 'display: none;')
            scope_multi.style('display: flex;' if v == 'Multiple Chapters' else 'display: none;')
            scope_full_subj.style('display: flex;' if v == 'Full Subject' else 'display: none;')
            scope_full_syl.style('display: block;' if v == 'Full Syllabus (all subjects)' else 'display: none;')
        
        scope.on_value_change(update_scope_visibility)

        with ui.row().classes('w-full gap-4 my-4'):
            difficulty = ui.select(DIFFICULTY_LEVELS, value=DIFFICULTY_LEVELS[1], label="Difficulty")
            pyq_style = ui.checkbox("PYQ-style phrasing").tooltip("Write questions in the style of actual NEET PYQs.")

        with ui.row().classes('w-full gap-4 my-4'):
            q_count = ui.number("Number of questions", value=DEFAULT_TEST_QUESTION_COUNT, step=1)
            col_dur = ui.row()
            with col_dur:
                duration = ui.number("Duration (minutes)", value=DEFAULT_TEST_DURATION_MINUTES, step=10)
        
        dpp_caption = ui.label("DPPs are untimed — no shared clock, students can work through it at their own pace.").classes('text-sm text-gray-500')
        dpp_caption.set_visibility(False)

        with ui.row().classes('w-full gap-4 my-4'):
            marks_correct = ui.number("Marks per correct answer", value=float(DEFAULT_MARKS_CORRECT), step=0.5)
            marks_wrong = ui.number("Marks per wrong answer (negative marking)", value=float(DEFAULT_MARKS_WRONG), step=0.5)

        ui.separator().classes('my-4')
        
        def handle_generate():
            if not title.value.strip():
                ui.notify("Title is required", type="warning")
                return
            
            chapter_pairs = []
            if scope.value == "Single Chapter":
                chapter_pairs = [(subj_single.value, chap_single.value)]
            elif scope.value == "Multiple Chapters":
                if not chap_multi.value:
                    ui.notify("Select at least one chapter.", type="warning")
                    return
                chapter_pairs = [(subj_multi.value, ch) for ch in chap_multi.value]
            elif scope.value == "Full Subject":
                chapter_pairs = [(subj_full.value, ch) for ch in get_chapters(subj_full.value)]
            else:
                chapter_pairs = [(subj, ch) for subj in SUBJECTS for ch in get_chapters(subj)]

            _generate_full_test(db, title.value.strip(), chapter_pairs, int(q_count.value),
                                 int(duration.value) if test_type.value == 'test' else 0, 
                                 difficulty.value, pyq_style.value,
                                 marks_correct.value, marks_wrong.value, test_type.value)

        btn_generate = ui.button("Generate Test", on_click=handle_generate).props('color=primary')


async def _generate_full_test(db, title, chapter_pairs, question_count, duration_minutes,
                         difficulty, pyq_style, marks_correct, marks_wrong, test_type="test"):
    label = "DPP" if test_type == "dpp" else "test"
    
    prog_container = ui.column().classes('w-full mt-4')
    with prog_container:
        prog_bar = ui.linear_progress(value=0.0).props('size=20px')
        prog_label = ui.label(f"Generating question 1 of {question_count}...")
    
    questions = []
    failures = 0

    for i in range(question_count):
        subject, chapter = chapter_pairs[i % len(chapter_pairs)]
        try:
            q = await asyncio.to_thread(generate_question, subject, chapter, difficulty=difficulty, pyq_style=pyq_style)
            questions.append(q)
        except AllProvidersExhaustedError as e:
            failures += 1
            if failures >= 3:
                prog_container.clear()
                ui.notify(
                    f"Stopped after {failures} consecutive failures. Generated {len(questions)} of {question_count} questions.", 
                    type="negative", timeout=10000
                )
                return
        except RuntimeError as e:
            failures += 1

        prog_bar.value = (i + 1) / question_count
        prog_label.text = f"Generating question {min(i + 2, question_count)} of {question_count}... ({len(questions)} succeeded)"

    prog_container.clear()

    if len(questions) < question_count:
        ui.notify(f"Generated {len(questions)} of {question_count} requested questions ({failures} failed).", type="warning")

    if not questions:
        ui.notify("No questions could be generated. Check your AI provider keys.", type="negative")
        return

    test_id = create_full_test(db, title, questions, duration_minutes, marks_correct, marks_wrong, test_type)
    ui.notify(f"{label.capitalize()} \"{title}\" created with {len(questions)} question(s).", type="positive")
    app.storage.user[f"just_created_{test_id}"] = True
    
    admin_content.refresh(db)


@ui.refreshable
def _render_existing_tests(db):
    tests = db.get("full_tests", {})
    if not tests:
        ui.label("Nothing created yet.").classes('text-gray-500')
        return

    filter_choice = ui.radio(["All", "Tests", "DPPs"], value="All").props('inline')
    list_container = ui.column().classes('w-full mt-4')
    
    def render_list():
        list_container.clear()
        with list_container:
            f_val = filter_choice.value
            filtered_tests = tests
            if f_val == "Tests":
                filtered_tests = {tid: t for tid, t in tests.items() if t.get("test_type", "test") == "test"}
            elif f_val == "DPPs":
                filtered_tests = {tid: t for tid, t in tests.items() if t.get("test_type") == "dpp"}

            if not filtered_tests:
                ui.label("Nothing here yet.").classes('text-gray-500')
                return

            for test_id, test in sorted(filtered_tests.items(), key=lambda kv: kv[1]["created_at"], reverse=True):
                is_dpp = test.get("test_type") == "dpp"
                with ui.card().classes('w-full p-4 mb-2'):
                    status_label = {"draft": "Draft", "open": "Open", "closed": "Closed"}[test["status"]]
                    type_label = "DPP" if is_dpp else "Test"
                    duration_label = "untimed" if is_dpp else f"{test['duration_minutes']} min"
                    
                    ui.markdown(f"**{test['title']}** · *{type_label}* — {len(test['questions'])} questions, {duration_label} — *{status_label}*")

                    with ui.row().classes('w-full justify-between items-center mt-2'):
                        if test["status"] == "draft":
                            ui.button("Open to Students", on_click=lambda tid=test_id: [open_full_test(db, tid), admin_content.refresh(db)]).props('color=primary')
                        
                        elif test["status"] == "open":
                            col = ui.column()
                            with col:
                                if not is_dpp:
                                    remaining = full_test_time_left(db, test_id)
                                    if remaining is not None:
                                        mins = int(remaining // 60)
                                        ui.label(f"{mins} min remaining on shared clock").classes('text-sm text-gray-500')
                                
                                close_label = "End Live Session" if not is_dpp else "Close"
                                ui.button(close_label, on_click=lambda tid=test_id: [close_full_test(db, tid), admin_content.refresh(db)]).props('color=negative')

                        submitted_count = len([s for s in test["submissions"].values() if s.get("best")])
                        attempt_total = sum(s.get("attempt_count", 0) for s in test["submissions"].values())
                        ui.label(f"{submitted_count} student(s) with a score · {attempt_total} attempt(s) total").classes('text-sm text-gray-500')

                    if test["submissions"]:
                        with ui.expansion("Results (best score per student)").classes('w-full mt-2'):
                            render_full_test_leaderboard(test)
    
    filter_choice.on_value_change(render_list)
    render_list()


@ui.refreshable
def _render_live_quiz_tab(db):
    ui.label("Live Practice Quiz").classes('text-2xl font-bold')
    ui.label("Runs in real time with everyone watching the same question at once.").classes('text-sm text-gray-500 mb-4')

    if not db["quiz_state"]["active"]:
        with ui.card().classes('w-full p-4'):
            quiz_mode = ui.radio(["Single Question", "Auto Quiz (multiple, timed)", "My Question Bank"], value="Single Question").props('inline')
            
            mode_single = ui.column().classes('w-full')
            mode_auto = ui.column().classes('w-full').style('display: none;')
            mode_bank = ui.column().classes('w-full').style('display: none;')
            
            def update_mode():
                v = quiz_mode.value
                mode_single.style('display: flex;' if v == 'Single Question' else 'display: none;')
                mode_auto.style('display: flex;' if v == 'Auto Quiz (multiple, timed)' else 'display: none;')
                mode_bank.style('display: flex;' if v == 'My Question Bank' else 'display: none;')

            quiz_mode.on_value_change(update_mode)

            with mode_single:
                with ui.row().classes('w-full gap-4'):
                    subj_s = ui.select(SUBJECTS, value=SUBJECTS[0], label="Subject")
                    chap_s = ui.select(get_chapters(SUBJECTS[0]), value=get_chapters(SUBJECTS[0])[0], label="Chapter")
                    subj_s.on_value_change(lambda e: chap_s.set_options(get_chapters(e.value)))
                
                with ui.row().classes('w-full gap-4 mt-4 items-center'):
                    diff_s = ui.select(DIFFICULTY_LEVELS, value=DIFFICULTY_LEVELS[1], label="Difficulty")
                    use_timer = ui.checkbox("Add a countdown timer")
                    timer_s = ui.slider(min=10, max=120, value=30, step=5).classes('w-48')
                    timer_s.bind_visibility_from(use_timer, 'value')
                
                async def handle_single():
                    try:
                        q_data = await asyncio.to_thread(generate_question, subj_s.value, chap_s.value, difficulty=diff_s.value)
                        start_quiz(db, q_data, timer_seconds=timer_s.value if use_timer.value else 0)
                        admin_content.refresh(db)
                    except AllProvidersExhaustedError as e:
                        ui.notify(f"Generation failed: {e}", type="negative")

                ui.button("Generate & Send", on_click=handle_single).props('color=primary').classes('mt-4')

            with mode_auto:
                with ui.row().classes('w-full gap-4'):
                    subj_a = ui.select(SUBJECTS, value=SUBJECTS[0], label="Subject")
                    chap_a = ui.select(get_chapters(SUBJECTS[0]), value=get_chapters(SUBJECTS[0])[0], label="Chapter")
                    subj_a.on_value_change(lambda e: chap_a.set_options(get_chapters(e.value)))

                with ui.row().classes('w-full gap-4 mt-4'):
                    diff_a = ui.select(DIFFICULTY_LEVELS, value=DIFFICULTY_LEVELS[1], label="Difficulty")
                    pyq_a = ui.checkbox("PYQ-style")
                
                with ui.row().classes('w-full gap-4 mt-4'):
                    ui.label("Number of questions:")
                    num_qs_a = ui.slider(min=2, max=20, value=5).classes('w-48')
                    ui.label("Seconds per question:")
                    timer_a = ui.slider(min=10, max=120, value=30, step=5).classes('w-48')

                async def handle_auto():
                    try:
                        start_auto_quiz(db, subj_a.value, chap_a.value, int(num_qs_a.value), int(timer_a.value), diff_a.value, pyq_a.value)
                        admin_content.refresh(db)
                    except AllProvidersExhaustedError as e:
                        ui.notify(f"Generation failed: {e}", type="negative")

                ui.button("Start Auto Quiz", on_click=handle_auto).props('color=primary').classes('mt-4')

            with mode_bank:
                ui.label("Paste questions below (blank line between each). One-time use.").classes('text-sm text-gray-500 mb-2')
                ui.code("Q: What is the powerhouse of the cell?\nA) Nucleus\nB) Mitochondria\nC) Ribosome\nD) Golgi body\nAnswer: B\nExplanation: Mitochondria generate ATP via oxidative phosphorylation.")
                
                bank_text = ui.textarea("Paste your questions here").classes('w-full h-48 mt-2')
                preview_container = ui.column().classes('w-full mt-4')
                
                def handle_parse():
                    preview_container.clear()
                    parsed, errors = parse_pasted_questions(bank_text.value)
                    app.storage.user['question_bank'] = parsed
                    with preview_container:
                        if parsed:
                            ui.notify(f"{len(parsed)} question(s) parsed.", type="positive")
                        if errors:
                            ui.notify(f"{len(errors)} block(s) skipped", type="warning")
                            for e in errors:
                                ui.label(f"• {e}").classes('text-xs text-red-500')
                        
                        if parsed:
                            ui.label("Seconds per question:")
                            bank_timer = ui.slider(min=10, max=120, value=30, step=5).classes('w-48')
                            ui.label("Number of questions to use:")
                            bank_count = ui.slider(min=1, max=len(parsed), value=len(parsed)).classes('w-48')
                            
                            def start_bank():
                                start_bank_quiz(db, parsed, int(bank_timer.value), int(bank_count.value))
                                admin_content.refresh(db)

                            ui.button("Start Quiz from Bank", on_click=start_bank).props('color=primary').classes('mt-4')

                ui.button("Parse & Preview", on_click=handle_parse).classes('mt-4')
    else:
        _render_active_live_quiz(db)


def _render_active_live_quiz(db):
    qs = db["quiz_state"]
    q_data = qs["question_data"]

    if qs.get("auto_mode"):
        ui.notify(f"Auto Quiz running — question {qs['current_index']}/{qs['total_questions']}", type="info")
    else:
        ui.notify("Live question active.", type="info")

    if q_data.get("_correction_made"):
        ui.label("Note: the verification pass corrected this question's answer before it was sent.").classes('text-sm text-gray-500')

    safe_question = html_lib.escape(str(q_data["question"]))
    
    with ui.row().classes('w-full justify-between items-center mb-4'):
        ui.html(f"<div class='text-xl font-bold'>{safe_question}</div>")
        
        with ui.row().classes('gap-2'):
            if qs.get("auto_mode"):
                ui.badge(f"{qs['current_index']}/{qs['total_questions']} Question")
            if qs.get("timer_seconds") and not qs["revealed"]:
                remaining = time_left(db)
                urgent = remaining is not None and remaining <= 10
                color = "red" if urgent else "blue"
                ui.badge(f"{int(remaining)}s Remaining").props(f'color={color}')

    if not qs["revealed"]:
        if qs.get("timer_seconds") and is_time_up(db):
            lock_and_reveal(db)
            admin_content.refresh(db)

        ui.label(f"{len(qs['answers'])} response(s) received").classes('text-sm text-gray-500')
        ui.button("Lock & Reveal Answer", on_click=lambda: [lock_and_reveal(db), admin_content.refresh(db)]).props('color=primary')
    else:
        ui.notify(f"Correct answer: {q_data['answer']}", type="positive")
        _render_results_table(qs, q_data, db)
        ui.separator().classes('my-4')
        render_leaderboard(db)

        if qs.get("auto_mode"):
            ui.label("Advancing to the next question...").classes('text-sm text-gray-500')
            
            async def auto_advance():
                await asyncio.sleep(2.5)
                advance_auto_quiz(db)
                admin_content.refresh(db)
            
            ui.timer(0.1, auto_advance, once=True)
        else:
            ui.button("Clear & Return", on_click=lambda: [clear_quiz(db), admin_content.refresh(db)])


def _render_results_table(qs, q_data, db):
    ui.label("Results:").classes('font-bold mt-4')
    answers = qs.get("answers", {})
    answer_times = qs.get("answer_times", {})
    all_students = [u for u, info in db["users"].items() if info["role"] == "student"]
    
    rows = []
    for student in all_students:
        chosen = answers.get(student)
        if chosen is None:
            rows.append({"Student": student.capitalize(), "Answer": "— no answer —", "Result": "Timed out", "Time": "—"})
        else:
            correct = chosen == q_data["answer"]
            t = answer_times.get(student)
            rows.append({
                "Student": student.capitalize(), "Answer": chosen,
                "Result": "Correct" if correct else "Wrong",
                "Time": f"{t}s" if t is not None else "—",
            })
            
    if rows:
        columns = [
            {'field': 'Student'},
            {'field': 'Answer'},
            {'field': 'Result'},
            {'field': 'Time'},
        ]
        ui.aggrid({'columnDefs': columns, 'rowData': rows}).classes('h-64 mt-2')
    else:
        ui.label("No responses yet.").classes('text-sm text-gray-500')


@ui.refreshable
def _render_leaderboard_tab(db):
    ui.label("Leaderboard").classes('text-2xl font-bold')
    
    def reset_scores():
        db["current_session_scores"] = {u: 0 for u in db["users"] if db["users"][u]["role"] == "student"}
        try:
            save_db(db)
            ui.notify("Session scores reset.", type="positive")
            admin_content.refresh(db)
        except DatabaseUnavailableError:
            ui.notify("Couldn't save just now — connection hiccup. Please try again.", type="negative")

    ui.button("Reset Today's Session Scores", on_click=reset_scores).classes('mb-4')
    render_leaderboard(db)
