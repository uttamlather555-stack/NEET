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


def render_student_dashboard(db):
    # 1. Render layout safely outside refreshable container
    render_sidebar(admin=False, db=db, on_navigate=lambda: student_content.refresh(db))

    # 2. Render dynamic content
    student_content(db)

@ui.refreshable
def student_content(db):
    username = app.storage.user.get("username", "")
    page = app.storage.user.get("nav_page", "Tests")
    
    with ui.column().classes('w-full max-w-5xl mx-auto p-4'):
        ui.html("<h1>Dashboard</h1>")

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
    
    def on_filter_change(e):
        app.storage.user["student_test_type_filter"] = e.value
        student_content.refresh(db)
        
    type_choice.on_value_change(on_filter_change)

    wanted_type = "test" if type_choice.value == "Tests" else "dpp"
    tests = {tid: t for tid, t in all_tests.items() if t.get("test_type", "test") == wanted_type}

    open_tests = {tid: t for tid, t in tests.items() if t["status"] == "open"}
    closed_tests = {tid: t for tid, t in tests.items() if t["status"] == "closed"}
    noun = "test" if wanted_type == "test" else "DPP"

    ui.label(f"Available {type_choice.value}").classes('text-xl font-bold mt-6')
    if not open_tests:
        ui.label(f"No {noun}s are open right now. Check back once your instructor opens one.").classes('text-sm text-gray-500')
    
    for test_id, test in open_tests.items():
        _render_available_card(db, test_id, test, username, wanted_type)

    if closed_tests:
        ui.separator().classes('my-6')
        ui.label(f"Past {type_choice.value}").classes('text-xl font-bold')
        ui.label("Nothing here ever disappears — revisit and retake any of these whenever you like.").classes('text-sm text-gray-500 mb-4')
        for test_id, test in sorted(closed_tests.items(), key=lambda kv: kv[1]["created_at"], reverse=True):
            _render_past_card(db, test_id, test, username, wanted_type)


def _render_available_card(db, test_id, test, username, wanted_type):
    sub = test["submissions"].get(username)
    best = sub.get("best") if sub else None
    
    with ui.card().classes('w-full p-4 mb-4'):
        if wanted_type == "test":
            remaining = full_test_time_left(db, test_id)
            mins = int(remaining // 60) if remaining is not None else test["duration_minutes"]
            ui.markdown(f"**{test['title']}**")
            ui.label(f"{len(test['questions'])} questions - {test['duration_minutes']} minutes - +{test['marks_correct']} / {test['marks_wrong']} marking").classes('text-sm text-gray-500')
            
            if remaining is not None and remaining <= 0:
                ui.label("This test's time window has ended, but it stays available under Past Tests to review and retake.").classes('text-sm text-warning')
                return
            ui.label(f"~{mins} min left on the shared clock.").classes('text-sm text-gray-500')
        else:
            ui.markdown(f"**{test['title']}**")
            ui.label(f"{len(test['questions'])} questions - untimed - +{test['marks_correct']} / {test['marks_wrong']} marking").classes('text-sm text-gray-500')

        if best is not None:
            ui.markdown(f"Your best score so far: **{best['score']}** ({sub.get('attempt_count', 0)} attempt(s))").classes('text-sm text-gray-500')

        button_label = "Retake" if best is not None else "Start"
        ui.button(f"{button_label} {'Test' if wanted_type == 'test' else 'DPP'}", 
                  on_click=lambda: [start_full_test_attempt(db, test_id, username), student_content.refresh(db)]).props('color=primary').classes('mt-2')


def _render_past_card(db, test_id, test, username, wanted_type):
    sub = test["submissions"].get(username)
    best = sub.get("best") if sub else None
    with ui.card().classes('w-full p-4 mb-4'):
        ui.markdown(f"**{test['title']}**")
        if best is not None:
            ui.markdown(
                f"Your best score: **{best['score']}** - Correct: {best['correct_count']} - "
                f"Wrong: {best['wrong_count']} - Unattempted: {best['unattempted_count']} "
                f"- ({sub.get('attempt_count', 0)} attempt(s))"
            )
            with ui.expansion("Review your best attempt").classes('w-full mt-2 bg-transparent'):
                _render_test_review(test, best)
            with ui.expansion("Leaderboard").classes('w-full mt-2 bg-transparent'):
                render_full_test_leaderboard(test, highlight_user=username)
        else:
            ui.label("You haven't attempted this one yet.").classes('text-sm text-gray-500')

        ui.button(f"{'Retake' if best is not None else 'Attempt'} anytime", 
                  on_click=lambda: [start_full_test_attempt(db, test_id, username), student_content.refresh(db)]).classes('mt-4')


def _render_test_review(test, best):
    for i, q in enumerate(test["questions"]):
        chosen = best["answers"].get(str(i))
        correct = q["answer"]
        ui.markdown(f"**Q{i + 1}.** {q['question']}")
        
        for opt in q["options"]:
            if opt == correct and opt == chosen:
                ui.markdown(f"**[correct - your answer]** {opt}").classes('text-green-500')
            elif opt == correct:
                ui.markdown(f"**[correct answer]** {opt}").classes('text-green-500')
            elif opt == chosen:
                ui.markdown(f"**[your answer - wrong]** {opt}").classes('text-red-500')
            else:
                ui.markdown(f"{opt}")
                
        ui.label(q.get("explanation", "")).classes('text-sm text-gray-500 mt-2')
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
        ui.notify("Time's up - your attempt has been auto-submitted.", type="warning")
        
        ui.timer(1.5, lambda: student_content.refresh(db), once=True)
        return

    working = _get_working_copy(sub, test_id)

    qidx_key = f"qidx_{test_id}"
    if qidx_key not in app.storage.user:
        app.storage.user[qidx_key] = 0
    current_idx = app.storage.user[qidx_key]

    ui.timer(20.0, lambda: _flush_working_copy(db, test_id, username))

    answered_count = len(working["answers"])
    marked_count = len(working["marked_for_review"])
    unattempted_count = total - answered_count

    exam_bar_container = ui.row().classes('w-full')
    
    def render_exam_bar():
        exam_bar_container.clear()
        with exam_bar_container:
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
                    student_content.refresh(db)
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
            
    render_exam_bar()
    
    if remaining is not None:
        ui.timer(1.0, render_exam_bar)

    if is_untimed and test.get("test_type") != "dpp":
        ui.label("This test's live window has ended, but you're free to practice it now — self-paced, no clock, doesn't affect anyone else's result.").classes('text-sm text-gray-500 mb-4')

    with ui.row().classes('w-full gap-8 flex-nowrap'):
        with ui.column().classes('flex-grow w-3/4'):
            q = questions[current_idx]
            ui.label(f"Question {current_idx + 1} of {total}").classes('text-sm text-gray-500')
            ui.markdown(f"### {html_lib.escape(q['question'])}")

            existing_answer = working["answers"].get(str(current_idx))
            
            def on_choice_change(e):
                if e.value is not None:
                    working["answers"][str(current_idx)] = e.value
                    
            choice = ui.radio(q["options"], value=existing_answer, on_change=on_choice_change).classes('mt-4 text-lg')

            with ui.row().classes('w-full gap-4 mt-8'):
                ui.button("Previous", on_click=lambda: navigate_test(db, test_id, username, max(0, current_idx - 1))).props('outline').classes('flex-1').set_visibility(current_idx > 0)
                
                is_marked = current_idx in working["marked_for_review"]
                def toggle_mark():
                    if is_marked:
                        working["marked_for_review"].remove(current_idx)
                    else:
                        working["marked_for_review"].append(current_idx)
                    navigate_test(db, test_id, username, current_idx)

                ui.button("Unmark" if is_marked else "Mark for Review", on_click=toggle_mark).props('outline color=warning').classes('flex-1')
                
                def clear_answer():
                    working["answers"].pop(str(current_idx), None)
                    choice.value = None
                    navigate_test(db, test_id, username, current_idx)
                    
                ui.button("Clear Answer", on_click=clear_answer).props('outline color=negative').classes('flex-1').set_visibility(existing_answer is not None)
                
                ui.button("Next", on_click=lambda: navigate_test(db, test_id, username, min(total - 1, current_idx + 1))).props('color=primary').classes('flex-1').set_visibility(current_idx < total - 1)

            ui.separator().classes('my-8')
            
            submit_container = ui.column().classes('w-full')
            with submit_container:
                if not app.storage.user.get(f"confirm_submit_{test_id}"):
                    ui.button("Submit Exam", on_click=lambda: [app.storage.user.update({f"confirm_submit_{test_id}": True}), student_content.refresh(db)]).props('color=primary').classes('w-full')
                else:
                    ui.notify(f"You've answered {answered_count} of {total} questions. Submit anyway?", type="warning")
                    with ui.row().classes('w-full gap-4 mt-2'):
                        def final_submit():
                            _flush_working_copy(db, test_id, username)
                            submit_full_test(db, test_id, username)
                            app.storage.user.pop(f"confirm_submit_{test_id}", None)
                            app.storage.user.pop(f"working_{test_id}", None)
                            app.storage.user.pop(qidx_key, None)
                            student_content.refresh(db)
                            
                        ui.button("Yes, Submit Now", on_click=final_submit).props('color=primary').classes('flex-1')
                        ui.button("Keep Working", on_click=lambda: [app.storage.user.pop(f"confirm_submit_{test_id}", None), student_content.refresh(db)]).classes('flex-1')

        with ui.column().classes('w-1/4 min-w-[200px]'):
            ui.label("Question Palette").classes('text-sm text-gray-500 mb-2')
            
            with ui.row().classes('w-full gap-1 qpalette-btn-wrap'):
                for idx in range(total):
                    is_answered = str(idx) in working["answers"]
                    is_marked = idx in working["marked_for_review"]
                    is_current = idx == current_idx
                    
                    if is_current:
                        label = f"[{idx + 1}]"
                        color = "primary"
                    elif is_marked:
                        label = f"*{idx + 1}"
                        color = "warning"
                    elif is_answered:
                        label = f"+{idx + 1}"
                        color = "positive"
                    else:
                        label = str(idx + 1)
                        color = "grey-7"
                        
                    ui.button(label, on_click=lambda i=idx: navigate_test(db, test_id, username, i)).props(f'color={color} outline size=sm').classes('w-10 h-10 p-0')


def navigate_test(db, test_id, username, new_idx):
    _flush_working_copy(db, test_id, username)
    app.storage.user[f"qidx_{test_id}"] = new_idx
    student_content.refresh(db)


def _render_live_quiz_view(db, username):
    ui.label("Live Practice").classes('text-xl font-bold mt-4')

    if not db["quiz_state"]["active"]:
        ui.label("No live quiz running right now.").classes('text-sm text-gray-500')
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

    ui.html(
        f"<div class='quiz-header-row'><div class='quiz-heading font-bold text-lg'>{safe_question}</div>"
        f"<div class='quiz-badges'>{badges_html}</div></div>"
    )

    if not qs["revealed"]:
        already_answered = username in qs["answers"]
        time_up = qs.get("timer_seconds") and is_time_up(db)

        if already_answered:
            ui.notify(f"Answer submitted: {qs['answers'][username]}", type="positive")
            ui.label(f"You answered: {qs['answers'][username]}").classes('mt-4 text-green-500 font-bold')
        elif time_up:
            ui.notify("Time's up - waiting for the instructor to reveal the answer.", type="warning")
            ui.label("Time's up. Waiting for instructor...").classes('mt-4 text-orange-500 font-bold')
        else:
            choice = ui.radio(q_data["options"]).classes('mt-4 text-lg')
            ui.button("Submit Answer", on_click=lambda: [submit_answer(db, username, choice.value), student_content.refresh(db)] if choice.value else ui.notify("Select an answer first", type="warning")).props('color=primary').classes('mt-4')
            
            ui.timer(1.0, lambda: student_content.refresh(db) if qs.get("timer_seconds") and is_time_up(db) else None)
    else:
        correct = qs["answers"].get(username) == q_data["answer"]
        box_class = "reveal-box" if correct else "reveal-box wrong"
        result_text = "Correct!" if correct else ("Incorrect" if username in qs["answers"] else "No answer submitted")
        
        ui.html(
            f"<div class='{box_class}'><strong>{result_text}</strong><br/>"
            f"Correct answer: {html_lib.escape(q_data['answer'])}<br/>"
            f"<span style='color:var(--text-dim);font-size:0.9rem'>{html_lib.escape(q_data.get('explanation', ''))}</span></div>"
        )
        ui.separator().classes('my-6')
        render_leaderboard(db, highlight_user=username)


def _render_leaderboard_page(db, username):
    ui.label("Leaderboard").classes('text-xl font-bold mt-4')
    render_leaderboard(db, highlight_user=username)
