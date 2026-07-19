import time
import html as html_lib
from nicegui import ui, app

from quiz import (
    submit_answer, time_left, is_time_up, render_leaderboard,
    start_full_test_attempt, sync_full_test_progress,
    submit_full_test, full_test_time_left,
    render_full_test_leaderboard,
)
from sidebar import render_sidebar

_PAGE_SUBTITLES = {
    "Tests": "Attempt open tests and DPPs, or revisit anything you've already tried.",
    "Practice": "Live questions your instructor sends out in real time.",
    "Leaderboard": "See how you stack up against the rest of the class today.",
}


@ui.refreshable
def render_student_dashboard(db):
    username = app.storage.user.get("username", "")

    # Setup drawer and navigation logic.
    # Passing render_student_dashboard.refresh as the callback so clicks redraw the main view.
    page = render_sidebar(admin=False, db=db, on_navigate=lambda: render_student_dashboard.refresh(db))

    # Main content area
    with ui.column().classes('w-full max-w-5xl mx-auto p-4 md:p-8'):
        ui.html(
            f'<div class="page-header">'
            f'<div class="page-title">Welcome back, {username.capitalize()}</div>'
            f'<div class="page-subtitle">{_PAGE_SUBTITLES.get(page, "")}</div>'
            f'</div>'
        )

        if page == "Tests":
            _render_tests_page(db, username)
        elif page == "Practice":
            _render_live_quiz_view(db, username)
        elif page == "Leaderboard":
            _render_leaderboard_page(db, username)


def _render_tests_page(db, username):
    all_tests = db.get("full_tests", {})

    for test_id, test in all_tests.items():
        if test["status"] != "open":
            continue
        sub = test["submissions"].get(username)
        if sub is not None and sub.get("submitted_at") is None:
            _render_test_taking_ui(db, test_id, test, username)
            return

    type_choice = ui.radio(["Tests", "DPPs"], value=app.storage.user.get("student_test_type_filter", "Tests")).props('inline')
    
    # Store filter choice and refresh when it changes
    def on_filter_change(e):
        app.storage.user["student_test_type_filter"] = e.value
        render_student_dashboard.refresh(db)
        
    type_choice.on_value_change(on_filter_change)

    wanted_type = "test" if type_choice.value == "Tests" else "dpp"
    tests = {tid: t for tid, t in all_tests.items() if t.get("test_type", "test") == wanted_type}

    open_tests = {tid: t for tid, t in tests.items() if t["status"] == "open"}
    closed_tests = {tid: t for tid, t in tests.items() if t["status"] == "closed"}
    noun = "test" if wanted_type == "test" else "DPP"

    ui.label(f"Available {type_choice.value}").classes('section-title mt-6')
    if not open_tests:
        ui.label(f"No {noun}s are open right now. Check back once your instructor opens one.").classes('empty-state')

    for test_id, test in open_tests.items():
        _render_available_card(db, test_id, test, username, wanted_type)

    if closed_tests:
        ui.separator().classes('my-6')
        ui.label(f"Past {type_choice.value}").classes('section-title')
        ui.label("Nothing here ever disappears — revisit and retake any of these whenever you like.").classes('section-caption mb-4')
        for test_id, test in sorted(closed_tests.items(), key=lambda kv: kv[1]["created_at"], reverse=True):
            _render_past_card(db, test_id, test, username, wanted_type)


def _render_available_card(db, test_id, test, username, wanted_type):
    sub = test["submissions"].get(username)
    best = sub.get("best") if sub else None

    with ui.card().classes('list-card w-full p-4 mb-4'):
        with ui.row().classes('w-full items-start justify-between gap-3'):
            with ui.column().classes('gap-1'):
                ui.label(test['title']).classes('list-card-title')
                if wanted_type == "test":
                    ui.label(f"{len(test['questions'])} questions · {test['duration_minutes']} min · +{test['marks_correct']} / {test['marks_wrong']} marking").classes('list-card-meta')
                else:
                    ui.label(f"{len(test['questions'])} questions · untimed · +{test['marks_correct']} / {test['marks_wrong']} marking").classes('list-card-meta')
            if best is not None:
                ui.html(f'<span class="status-pill open">Best: {best["score"]} pts</span>')

        if wanted_type == "test":
            remaining = full_test_time_left(db, test_id)
            if remaining is not None and remaining <= 0:
                ui.label("This test's time window has ended, but it stays available under Past Tests to review and retake.").classes('list-card-meta text-warning mt-2')
                return
            mins = int(remaining // 60) if remaining is not None else test["duration_minutes"]
            ui.label(f"~{mins} min left on the shared clock").classes('list-card-meta mt-2')

        if best is not None:
            ui.label(f"{sub.get('attempt_count', 0)} attempt(s) so far").classes('list-card-meta')

        button_label = "Retake" if best is not None else "Start"
        ui.button(f"{button_label} {'Test' if wanted_type == 'test' else 'DPP'}", icon="play_arrow",
                  on_click=lambda: [start_full_test_attempt(db, test_id, username), render_student_dashboard.refresh(db)]).props('color=primary').classes('mt-3')


def _render_past_card(db, test_id, test, username, wanted_type):
    sub = test["submissions"].get(username)
    best = sub.get("best") if sub else None
    with ui.card().classes('list-card w-full p-4 mb-4'):
        with ui.row().classes('w-full items-start justify-between gap-3'):
            ui.label(test['title']).classes('list-card-title')
            if best is not None:
                ui.html(f'<span class="status-pill open">Best: {best["score"]} pts</span>')

        if best is not None:
            ui.label(
                f"Correct: {best['correct_count']} · Wrong: {best['wrong_count']} · "
                f"Unattempted: {best['unattempted_count']} · {sub.get('attempt_count', 0)} attempt(s)"
            ).classes('list-card-meta mt-1')
            with ui.expansion("Review your best attempt").classes('w-full mt-2 app-expansion'):
                _render_test_review(test, best)
            with ui.expansion("Leaderboard").classes('w-full mt-2 app-expansion'):
                render_full_test_leaderboard(test, highlight_user=username)
        else:
            ui.label("You haven't attempted this one yet.").classes('empty-state mt-1')

        ui.button(f"{'Retake' if best is not None else 'Attempt'} anytime", icon="replay",
                  on_click=lambda: [start_full_test_attempt(db, test_id, username), render_student_dashboard.refresh(db)]).props('outline').classes('mt-4')


def _render_test_review(test, best):
    for i, q in enumerate(test["questions"]):
        chosen = best["answers"].get(str(i))
        correct = q["answer"]
        ui.html(f'<div class="review-q-label">Q{i + 1}. {html_lib.escape(q["question"])}</div>')

        with ui.column().classes('gap-1 mt-2'):
            for opt in q["options"]:
                safe_opt = html_lib.escape(opt)
                if opt == correct and opt == chosen:
                    ui.html(f'<div class="review-option correct"><span class="material-icons">check_circle</span>{safe_opt} <span class="review-option-tag">Your answer</span></div>')
                elif opt == correct:
                    ui.html(f'<div class="review-option correct"><span class="material-icons">check_circle</span>{safe_opt}</div>')
                elif opt == chosen:
                    ui.html(f'<div class="review-option wrong"><span class="material-icons">cancel</span>{safe_opt} <span class="review-option-tag">Your answer</span></div>')
                else:
                    ui.html(f'<div class="review-option">{safe_opt}</div>')

        ui.label(q.get("explanation", "")).classes('list-card-meta mt-3')
        ui.separator().classes('my-4')


def _get_working_copy(sub, test_id):
    key = f"working_{test_id}"
    if key not in app.storage.user:
        app.storage.user[key] = {
            "answers": dict(sub.get("answers", {})),
            "marked_for_review": list(sub.get("marked_for_review", [])),
        }
    return app.storage.user[key]


def _flush_working_copy(db, test_id, username):
    working = app.storage.user.get(f"working_{test_id}")
    if working is not None:
        sync_full_test_progress(db, test_id, username, working["answers"], working["marked_for_review"])


def _render_exam_bar(db, test_id, test, username, working, total):
    """Renders the sticky exam bar (title, clock, answered/marked/remaining stats).

    The clock ticks via its own @ui.refreshable + a single ui.timer that is created
    only the first time this test attempt is rendered on this client (guarded by a
    flag in app.storage.user). Navigating between questions re-renders the parent
    dashboard, but this function's timer is skipped on subsequent calls, so timers
    never stack and the stats/clock never go stale or freeze.
    """
    timer_guard_key = f"exam_timer_started_{test_id}"

    @ui.refreshable
    def exam_bar():
        # Recompute everything fresh on every tick/refresh - never capture stale values.
        curr_working = _get_working_copy(test["submissions"][username], test_id)
        answered_count = len(curr_working["answers"])
        marked_count = len(curr_working["marked_for_review"])
        unattempted_count = total - answered_count

        curr_remaining = full_test_time_left(db, test_id)
        if curr_remaining is not None:
            mins, secs = int(curr_remaining // 60), int(curr_remaining % 60)
            urgent = curr_remaining <= 300
            clock_class = "exam-bar-clock urgent" if urgent else "exam-bar-clock"
            clock_html = f'<div class="{clock_class}">{mins:02d}:{secs:02d}</div>'

            if curr_remaining <= 0:
                _flush_working_copy(db, test_id, username)
                submit_full_test(db, test_id, username)
                app.storage.user.pop(f"working_{test_id}", None)
                app.storage.user.pop(f"qidx_{test_id}", None)
                app.storage.user.pop(timer_guard_key, None)
                render_student_dashboard.refresh(db)
                return
        else:
            clock_html = '<div class="exam-bar-clock">Untimed</div>'

        ui.html(
            f"""
            <div class="exam-bar" style="width: 100%;">
                <div class="exam-bar-title">{html_lib.escape(test['title'])}</div>
                {clock_html}
                <div class="exam-bar-stats">
                    <div class="exam-stat answered"><div class="n">{answered_count}</div><div class="l">Answered</div></div>
                    <div class="exam-stat marked"><div class="n">{marked_count}</div><div class="l">Marked</div></div>
                    <div class="exam-stat unattempted"><div class="n">{unattempted_count}</div><div class="l">Remaining</div></div>
                </div>
            </div>
            """
        ).classes('w-full')

    exam_bar()

    # Only ever create the ticking/autosave timers once per attempt per client.
    if not app.storage.user.get(timer_guard_key):
        app.storage.user[timer_guard_key] = True
        remaining = full_test_time_left(db, test_id)
        if remaining is not None:
            ui.timer(1.0, exam_bar.refresh)
        ui.timer(20.0, lambda: _flush_working_copy(db, test_id, username))


def _render_test_taking_ui(db, test_id, test, username):
    sub = test["submissions"][username]
    questions = test["questions"]
    total = len(questions)
    is_untimed = test.get("test_type") == "dpp" or test["status"] != "open"

    remaining = full_test_time_left(db, test_id)
    if remaining is not None and remaining <= 0:
        _flush_working_copy(db, test_id, username)
        submit_full_test(db, test_id, username)
        app.storage.user.pop(f"working_{test_id}", None)
        app.storage.user.pop(f"qidx_{test_id}", None)
        app.storage.user.pop(f"exam_timer_started_{test_id}", None)
        ui.notify("Time's up - your attempt has been auto-submitted.", type="warning")
        
        # Short delay before refreshing to show dashboard
        ui.timer(1.5, lambda: render_student_dashboard.refresh(db), once=True)
        return

    working = _get_working_copy(sub, test_id)

    qidx_key = f"qidx_{test_id}"
    if qidx_key not in app.storage.user:
        app.storage.user[qidx_key] = 0
    current_idx = app.storage.user[qidx_key]

    # Background autosave + exam bar / clock: registered exactly once per test attempt
    # (guarded below), not once per navigation click, so timers never stack up.
    _render_exam_bar(db, test_id, test, username, working, total)

    if is_untimed and test.get("test_type") != "dpp":
        ui.label("This test's live window has ended, but you're free to practice it now — self-paced, no clock, doesn't affect anyone else's result.").classes('text-sm text-gray-500 mb-4')

    with ui.row().classes('w-full gap-6 flex-nowrap items-start mt-4'):

        # MAIN QUESTION COLUMN
        with ui.column().classes('question-card flex-grow w-3/4 p-6'):
            q = questions[current_idx]
            with ui.row().classes('w-full items-center justify-between mb-1'):
                ui.label(f"Question {current_idx + 1} of {total}").classes('question-index-label')
                if current_idx in working["marked_for_review"]:
                    ui.html('<span class="status-pill closed">Marked for review</span>')

            ui.html(f'<div class="question-text">{html_lib.escape(q["question"])}</div>')

            existing_answer = working["answers"].get(str(current_idx))

            # Update the local dictionary memory instantly on click
            def on_choice_change(e):
                if e.value is not None:
                    working["answers"][str(current_idx)] = e.value

            choice = ui.radio(q["options"], value=existing_answer, on_change=on_choice_change).classes('option-radio mt-5')

            with ui.row().classes('w-full gap-3 mt-8'):
                ui.button("Previous", icon="chevron_left", on_click=lambda: navigate_test(db, test_id, username, max(0, current_idx - 1))).props('outline').classes('flex-1').set_visibility(current_idx > 0)

                is_marked = current_idx in working["marked_for_review"]
                def toggle_mark():
                    if is_marked:
                        working["marked_for_review"].remove(current_idx)
                    else:
                        working["marked_for_review"].append(current_idx)
                    navigate_test(db, test_id, username, current_idx) # just flush and refresh

                ui.button("Unmark" if is_marked else "Mark for Review", icon="flag", on_click=toggle_mark).props('outline color=warning').classes('flex-1')

                def clear_answer():
                    working["answers"].pop(str(current_idx), None)
                    choice.value = None # Clear radio UI
                    navigate_test(db, test_id, username, current_idx)

                ui.button("Clear Answer", icon="close", on_click=clear_answer).props('outline color=negative').classes('flex-1').set_visibility(existing_answer is not None)

                ui.button("Next", icon="chevron_right", on_click=lambda: navigate_test(db, test_id, username, min(total - 1, current_idx + 1))).props('color=primary').classes('flex-1').set_visibility(current_idx < total - 1)

            ui.separator().classes('my-8')

            # Submit Section
            answered_count = len(working["answers"])
            submit_container = ui.column().classes('w-full')
            with submit_container:
                if not app.storage.user.get(f"confirm_submit_{test_id}"):
                    ui.button("Submit Exam", icon="task_alt", on_click=lambda: [app.storage.user.update({f"confirm_submit_{test_id}": True}), render_student_dashboard.refresh(db)]).props('color=primary').classes('w-full')
                else:
                    with ui.column().classes('submit-confirm-box w-full'):
                        ui.label(f"You've answered {answered_count} of {total} questions. Submit anyway?").classes('font-medium mb-2')
                        with ui.row().classes('w-full gap-4'):
                            def final_submit():
                                _flush_working_copy(db, test_id, username)
                                submit_full_test(db, test_id, username)
                                app.storage.user.pop(f"confirm_submit_{test_id}", None)
                                app.storage.user.pop(f"working_{test_id}", None)
                                app.storage.user.pop(qidx_key, None)
                                app.storage.user.pop(f"exam_timer_started_{test_id}", None)
                                render_student_dashboard.refresh(db)

                            ui.button("Yes, Submit Now", on_click=final_submit).props('color=primary').classes('flex-1')
                            ui.button("Keep Working", on_click=lambda: [app.storage.user.pop(f"confirm_submit_{test_id}", None), render_student_dashboard.refresh(db)]).props('outline').classes('flex-1')

        # PALETTE COLUMN
        with ui.column().classes('palette-card w-1/4 min-w-[220px] p-4'):
            ui.label("Question Palette").classes('form-section-title mb-3')

            with ui.row().classes('w-full gap-2 qpalette-btn-wrap'):
                for idx in range(total):
                    is_answered = str(idx) in working["answers"]
                    is_marked = idx in working["marked_for_review"]
                    is_current = idx == current_idx

                    if is_current:
                        pill_class = "qpalette-btn current"
                    elif is_marked:
                        pill_class = "qpalette-btn marked"
                    elif is_answered:
                        pill_class = "qpalette-btn answered"
                    else:
                        pill_class = "qpalette-btn unanswered"

                    ui.button(str(idx + 1), on_click=lambda i=idx: navigate_test(db, test_id, username, i)).props('flat').classes(pill_class)

            ui.separator().classes('my-4')
            with ui.column().classes('gap-2'):
                _palette_legend_item("qpalette-btn answered", "Answered")
                _palette_legend_item("qpalette-btn marked", "Marked for review")
                _palette_legend_item("qpalette-btn unanswered", "Not answered")
                _palette_legend_item("qpalette-btn current", "Current question")


def _palette_legend_item(swatch_class: str, label: str):
    with ui.row().classes('items-center gap-2'):
        ui.html(f'<div class="{swatch_class} legend-swatch"></div>')
        ui.label(label).classes('list-card-meta')

def navigate_test(db, test_id, username, new_idx):
    _flush_working_copy(db, test_id, username)
    app.storage.user[f"qidx_{test_id}"] = new_idx
    render_student_dashboard.refresh(db)

# ========================================================================
# LIVE QUIZ 
# ========================================================================

def _render_live_quiz_view(db, username):
    ui.label("Live Practice").classes('section-title mt-4')

    if not db["quiz_state"]["active"]:
        ui.label("No live quiz running right now.").classes('empty-state')
        return

    qs = db["quiz_state"]
    q_data = qs["question_data"]

    safe_question = html_lib.escape(str(q_data["question"]))

    badges_html = ""
    if qs.get("auto_mode"):
        badges_html += f"<div class='progress-badge'><div class='t-val'>{qs['current_index']}/{qs['total_questions']}</div><div class='t-lbl'>Question</div></div>"
    if qs.get("timer_seconds") and not qs["revealed"]:
        remaining = time_left(db)
        urgent = remaining is not None and remaining <= 10
        badge_class = "timer-badge urgent" if urgent else "timer-badge"
        badges_html += f"<div class='{badge_class}'><div class='t-val'>{int(remaining)}s</div><div class='t-lbl'>Remaining</div></div>"

    with ui.column().classes('question-card w-full p-6 mt-4'):
        ui.html(
            f"<div class='quiz-header-row'><div class='quiz-heading font-bold text-lg'>{safe_question}</div>"
            f"<div class='quiz-badges'>{badges_html}</div></div>"
        )

        if not qs["revealed"]:
            already_answered = username in qs["answers"]
            time_up = qs.get("timer_seconds") and is_time_up(db)

            # question_start_time is set fresh (time.time()) for every question, whether
            # single or auto-mode, so it's a reliable unique key - unlike current_index,
            # which stays 0 forever for single-question quizzes.
            question_key = qs.get("question_start_time", 0)
            notify_flag_key = f"live_quiz_notified_{question_key}"

            if already_answered:
                if not app.storage.user.get(notify_flag_key):
                    app.storage.user[notify_flag_key] = True
                    ui.notify(f"Answer submitted: {qs['answers'][username]}", type="positive")
                ui.label(f"You answered: {qs['answers'][username]}").classes('mt-4 text-green-500 font-bold')
            elif time_up:
                ui.label("Time's up. Waiting for instructor...").classes('mt-4 text-orange-500 font-bold')
            else:
                choice = ui.radio(q_data["options"]).classes('option-radio mt-4')
                ui.button("Submit Answer", icon="send", on_click=lambda: [submit_answer(db, username, choice.value), render_student_dashboard.refresh(db)] if choice.value else ui.notify("Select an answer first", type="warning")).props('color=primary').classes('mt-4')

                # Background checker to auto-refresh student view when admin reveals the
                # answer - created once per question (guarded), not once per page render,
                # and self-cancels once it fires so it can't stack or re-trigger forever.
                timer_guard_key = f"live_quiz_watch_timer_{question_key}"
                if not app.storage.user.get(timer_guard_key):
                    app.storage.user[timer_guard_key] = True

                    def _watch_for_reveal():
                        current_qs = db["quiz_state"]
                        if current_qs.get("revealed") or (current_qs.get("timer_seconds") and is_time_up(db)):
                            render_student_dashboard.refresh(db)

                    ui.timer(1.0, _watch_for_reveal)
        else:
            correct = qs["answers"].get(username) == q_data["answer"]
            box_class = "reveal-box" if correct else "reveal-box wrong"
            result_text = "Correct!" if correct else ("Incorrect" if username in qs["answers"] else "No answer submitted")

            ui.html(
                f"<div class='{box_class}'><strong>{result_text}</strong><br/>"
                f"Correct answer: {html_lib.escape(q_data['answer'])}<br/>"
                f"<span style='color:var(--text-dim);font-size:0.9rem'>{html_lib.escape(q_data.get('explanation', ''))}</span></div>"
            )

    if qs["revealed"]:
        ui.separator().classes('my-6')
        render_leaderboard(db, highlight_user=username)


def _render_leaderboard_page(db, username):
    ui.label("Leaderboard").classes('section-title mt-4')
    render_leaderboard(db, highlight_user=username)
