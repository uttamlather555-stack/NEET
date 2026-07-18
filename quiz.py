import random
import re
import time
import uuid

from nicegui import ui, app

from database import save_db, DatabaseUnavailableError
from ai_providers import complete_with_rotation, AllProvidersExhaustedError

def _safe_save(db) -> bool:
    try:
        save_db(db)
        return True
    except DatabaseUnavailableError:
        ui.notify("Couldn't save just now - connection hiccup. Please try that action again in a few seconds.", type="warning")
        return False

# ----------------------------------------------------------------------
# AI GENERATION
# ----------------------------------------------------------------------

def _shuffle_options(q_data: dict) -> dict:
    options = list(q_data["options"])
    correct_text = q_data["answer"]

    if correct_text not in options:
        return q_data 

    shuffled = options[:]
    random.shuffle(shuffled)

    q_data = dict(q_data)
    q_data["options"] = shuffled
    q_data["answer"] = correct_text
    return q_data

_DANGLING_STEM_RE = re.compile(
    r"(given\s+below\s+are|consider\s+the\s+following|read\s+the\s+following|"
    r"read\s+the\s+assertion|assertion\s*\(a\)|two\s+statements|three\s+statements)"
    r"[^.]{0,15}[:\-]?\s*$",
    re.IGNORECASE,
)

def _has_dangling_statement_stem(question_text: str) -> bool:
    return bool(_DANGLING_STEM_RE.search(question_text.strip()))

def _validate_question_shape(q_data: dict) -> bool:
    if not isinstance(q_data, dict):
        return False
    required = ("question", "options", "answer", "explanation")
    if not all(k in q_data for k in required):
        return False
    if not isinstance(q_data["options"], list) or len(q_data["options"]) != 4:
        return False
    if q_data["answer"] not in q_data["options"]:
        return False
    question_text = str(q_data["question"]).strip()
    if not question_text:
        return False
    if _has_dangling_statement_stem(question_text):
        return False
    return True

DIFFICULTY_INSTRUCTIONS = {
    "Easy": "EASY difficulty: direct recall of a single fact or definition, the kind "
            "of question that rewards a student who read the NCERT textbook carefully. "
            "No multi-step reasoning.",
    "Medium": "MEDIUM difficulty: standard NEET difficulty - requires connecting two "
              "related facts or applying a concept to a slightly unfamiliar example.",
    "Hard": "HARD difficulty: a tough, discriminating NEET question - multi-step "
            "reasoning, easily-confused options, or combining concepts from more than "
            "one part of the chapter.",
}

def _generate_raw(subject: str, topic: str, difficulty: str = "Medium", pyq_style: bool = False) -> tuple:
    difficulty_instruction = DIFFICULTY_INSTRUCTIONS.get(difficulty, DIFFICULTY_INSTRUCTIONS["Medium"])
    pyq_block = (
        "\nWrite this in the STYLE of an actual NEET Previous Year Question - the exact "
        "phrasing conventions and answer-choice patterns real NEET papers use. This is "
        "AI-generated, INSPIRED BY that style, not a claim of being a real past paper "
        "question - never state or imply a specific year or session.\n"
        if pyq_style else ""
    )

    prompt = f"""Generate 1 tough NEET multiple choice question for {subject} on the chapter/topic "{topic}".
Be scientifically precise. Double check the correct answer is actually correct before responding.

DIFFICULTY: {difficulty_instruction}
{pyq_block}
You may use any standard NEET question style, including assertion-reason questions and
two/three-statement "which of the following is/are correct" questions. This is exactly why the
"question" field rule below matters.

CRITICAL RULE FOR THE "question" FIELD:
The "question" field must be a SINGLE, FULLY SELF-CONTAINED STRING that includes every piece of
text a student needs in order to answer - there is no separate field for statements, assertions,
or reasons, so nothing outside "question" and "options" is ever shown to the student.
- If this is a statement-based question, the "question" string MUST include the complete text of
  every statement, numbered (Statement I: ..., Statement II: ...).
- If this is an assertion-reason question, the "question" string MUST include the full text of both
  the Assertion (A) and the Reason (R) written out in full, not just the labels.
- NEVER write a stem like "Given below are two statements:" without immediately writing out the
  full statement text right after it, inside that same "question" string.
- The "options" array should then contain only the final answer choices, never the statements.

Output ONLY valid JSON in this exact shape, nothing else:
{{"question": "text (fully self-contained)", "options": ["option 1", "option 2", "option 3", "option 4"], "answer": "exact correct option text, copied verbatim from options", "explanation": "Why it is correct, and briefly why the other options are wrong"}}"""

    result, provider = complete_with_rotation(prompt)
    return result, provider

def _verify_question(q_data: dict) -> dict:
    options_list = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(q_data["options"]))
    prompt = f"""You are fact-checking a NEET exam question. Solve it yourself from scratch first,
then compare to the proposed answer below.

Question: {q_data['question']}
Options:
{options_list}

Proposed answer: {q_data['answer']}
Proposed explanation: {q_data['explanation']}

Independently determine the correct option. If the proposed answer is correct, confirm it.
If it is wrong, correct it.
Output ONLY valid JSON in this exact shape, nothing else:
{{"answer": "exact correct option text, copied verbatim from the options list above", "explanation": "correct, accurate explanation", "was_correct": true or false}}"""

    verified, _provider = complete_with_rotation(prompt)

    if verified.get("answer") not in q_data["options"]:
        q_data = dict(q_data)
        q_data["_verified"] = False
        return q_data

    q_data = dict(q_data)
    q_data["answer"] = verified["answer"]
    q_data["explanation"] = verified.get("explanation", q_data["explanation"])
    q_data["_verified"] = True
    q_data["_correction_made"] = not verified.get("was_correct", True)
    return q_data

def generate_question(subject: str, topic: str, max_attempts: int = 3,
                       difficulty: str = "Medium", pyq_style: bool = False) -> dict:
    last_error = None

    for attempt in range(max_attempts):
        try:
            q_data, _provider = _generate_raw(subject, topic, difficulty=difficulty, pyq_style=pyq_style)
            q_data = _shuffle_options(q_data)

            if not _validate_question_shape(q_data):
                last_error = "Malformed question shape from generation step"
                continue

            q_data = _verify_question(q_data)

            if not _validate_question_shape(q_data):
                last_error = "Malformed question shape from verification step"
                continue

            return q_data
        except AllProvidersExhaustedError:
            raise
        except (ValueError, KeyError, TypeError) as e:
            last_error = str(e)
            continue

    raise RuntimeError(f"Could not generate a reliable question after {max_attempts} attempts. Last error: {last_error}")


# ----------------------------------------------------------------------
# QUESTION BANK
# ----------------------------------------------------------------------

_OPTION_PREFIX_RE = re.compile(r"^\s*[\(\[]?([A-Da-d])[\)\].:\-]\s*")
_ANSWER_LETTER_RE = re.compile(r"^\s*([A-Da-d])\b")

def _strip_option_prefix(line: str) -> str:
    return _OPTION_PREFIX_RE.sub("", line).strip()

def parse_pasted_questions(raw_text: str) -> tuple:
    blocks = re.split(r"\n\s*\n", raw_text.strip())
    parsed = []
    errors = []

    for block_num, block in enumerate(blocks, start=1):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if not lines:
            continue

        question_text = None
        options = []
        answer_letter = None
        explanation = ""

        for line in lines:
            low = line.lower()
            if low.startswith("q:") or low.startswith("q.") or low.startswith("question:"):
                question_text = line.split(":", 1)[-1].strip()
            elif low.startswith("answer:") or low.startswith("ans:"):
                m = _ANSWER_LETTER_RE.match(line.split(":", 1)[-1].strip())
                if m:
                    answer_letter = m.group(1).upper()
            elif low.startswith("explanation:") or low.startswith("solution:"):
                explanation = line.split(":", 1)[-1].strip()
            elif _OPTION_PREFIX_RE.match(line):
                options.append(_strip_option_prefix(line))

        if question_text is None:
            errors.append(f"Block {block_num}: no line starting with 'Q:' found - skipped.")
            continue
        if len(options) != 4:
            errors.append(f"Block {block_num} (\"{question_text[:40]}...\"): found {len(options)} options, need exactly 4 - skipped.")
            continue
        if answer_letter is None:
            errors.append(f"Block {block_num} (\"{question_text[:40]}...\"): no valid 'Answer: A/B/C/D' line found - skipped.")
            continue

        letter_index = {"A": 0, "B": 1, "C": 2, "D": 3}[answer_letter]
        answer_text = options[letter_index]

        parsed.append({
            "question": question_text,
            "options": options,
            "answer": answer_text,
            "explanation": explanation or "No explanation provided.",
        })

    return parsed, errors


# ----------------------------------------------------------------------
# LIVE QUIZ - single question
# ----------------------------------------------------------------------

def _empty_quiz_state() -> dict:
    return {
        "active": False,
        "question_data": None,
        "answers": {},
        "answer_times": {},
        "revealed": False,
        "timer_seconds": 0,
        "question_start_time": 0,
        "auto_mode": False,
        "subject": None,
        "topic": None,
        "total_questions": 0,
        "current_index": 0,
        "question_source": "ai",
        "bank_order": [],
    }

def start_quiz(db, q_data: dict, timer_seconds: int = 0):
    db["quiz_state"] = _empty_quiz_state()
    db["quiz_state"].update({
        "active": True,
        "question_data": q_data,
        "timer_seconds": timer_seconds,
        "question_start_time": time.time() if timer_seconds else 0,
    })
    _safe_save(db)

def clear_quiz(db):
    db["quiz_state"] = _empty_quiz_state()
    _safe_save(db)


# ----------------------------------------------------------------------
# LIVE QUIZ - auto series 
# ----------------------------------------------------------------------

def start_auto_quiz(db, subject: str, topic: str, total_questions: int, timer_seconds: int,
                     difficulty: str = "Medium", pyq_style: bool = False):
    q_data = generate_question(subject, topic, difficulty=difficulty, pyq_style=pyq_style)
    db["quiz_state"] = _empty_quiz_state()
    db["quiz_state"].update({
        "active": True,
        "question_data": q_data,
        "timer_seconds": timer_seconds,
        "question_start_time": time.time(),
        "auto_mode": True,
        "subject": subject,
        "topic": topic,
        "difficulty": difficulty,
        "pyq_style": pyq_style,
        "total_questions": total_questions,
        "current_index": 1,
        "question_source": "ai",
    })
    _safe_save(db)

def start_bank_quiz(db, bank_questions: list, timer_seconds: int, num_questions: int = None):
    count = len(bank_questions) if num_questions is None else min(num_questions, len(bank_questions))
    order = list(range(len(bank_questions)))
    random.shuffle(order)
    order = order[:count]

    first_q = bank_questions[order[0]]
    db["quiz_state"] = _empty_quiz_state()
    db["quiz_state"].update({
        "active": True,
        "question_data": first_q,
        "timer_seconds": timer_seconds,
        "question_start_time": time.time(),
        "auto_mode": True,
        "total_questions": count,
        "current_index": 1,
        "question_source": "bank",
        "bank_order": order,
    })
    _safe_save(db)

def advance_auto_quiz(db):
    qs = db["quiz_state"]
    if qs["current_index"] >= qs["total_questions"]:
        clear_quiz(db)
        return

    if qs.get("question_source") == "bank":
        # NiceGUI stores session state in app.storage.user
        bank = app.storage.user.get("question_bank", [])
        order = qs.get("bank_order", [])
        next_pos = qs["current_index"]
        if next_pos >= len(order) or not bank:
            clear_quiz(db)
            return
        q_data = bank[order[next_pos]]
    else:
        q_data = generate_question(
            qs["subject"], qs["topic"],
            difficulty=qs.get("difficulty", "Medium"),
            pyq_style=qs.get("pyq_style", False),
        )

    qs["question_data"] = q_data
    qs["answers"] = {}
    qs["answer_times"] = {}
    qs["revealed"] = False
    qs["question_start_time"] = time.time()
    qs["current_index"] += 1
    _safe_save(db)

def time_left(db) -> float:
    qs = db["quiz_state"]
    if not qs.get("timer_seconds"):
        return None
    elapsed = time.time() - qs.get("question_start_time", time.time())
    remaining = qs["timer_seconds"] - elapsed
    return max(0, remaining)

def is_time_up(db) -> bool:
    tl = time_left(db)
    return tl is not None and tl <= 0

def submit_answer(db, username: str, choice: str):
    qs = db["quiz_state"]
    qs["answers"][username] = choice
    if qs.get("timer_seconds"):
        elapsed = time.time() - qs.get("question_start_time", time.time())
        qs["answer_times"][username] = round(max(0, elapsed), 1)
    _safe_save(db)

def lock_and_reveal(db):
    q_data = db["quiz_state"]["question_data"]
    for student, answer in db["quiz_state"]["answers"].items():
        if student not in db["users"]:
            continue
        if answer == q_data["answer"]:
            db["current_session_scores"][student] = db["current_session_scores"].get(student, 0) + 4
            db["users"][student]["lifetime_score"] += 4
        else:
            db["current_session_scores"][student] = db["current_session_scores"].get(student, 0) - 1
            db["users"][student]["lifetime_score"] -= 1
    db["quiz_state"]["revealed"] = True
    _safe_save(db)


# ----------------------------------------------------------------------
# FULL-LENGTH TIMED TESTS + DPPs
# ----------------------------------------------------------------------

def create_full_test(db, title: str, questions: list, duration_minutes: int,
                      marks_correct: float = 4, marks_wrong: float = -1,
                      test_type: str = "test") -> str:
    test_id = uuid.uuid4().hex[:10]
    db.setdefault("full_tests", {})
    db["full_tests"][test_id] = {
        "id": test_id,
        "title": title,
        "test_type": test_type,
        "questions": questions,
        "duration_minutes": duration_minutes,
        "marks_correct": marks_correct,
        "marks_wrong": marks_wrong,
        "status": "draft",
        "opened_at": None,
        "created_at": time.time(),
        "submissions": {},
    }
    _safe_save(db)
    return test_id

def open_full_test(db, test_id: str):
    test = db["full_tests"][test_id]
    test["status"] = "open"
    test["opened_at"] = time.time()
    _safe_save(db)

def close_full_test(db, test_id: str):
    test = db["full_tests"][test_id]
    for username, sub in test["submissions"].items():
        if sub.get("submitted_at") is None:
            try:
                _grade_and_finalize_submission(test, sub)
            except Exception:
                continue
    test["status"] = "closed"
    _safe_save(db)

def full_test_time_left(db, test_id: str) -> float:
    test = db["full_tests"][test_id]
    if test.get("test_type") == "dpp":
        return None
    if test["status"] != "open" or not test.get("opened_at"):
        return None
    elapsed = time.time() - test["opened_at"]
    remaining = test["duration_minutes"] * 60 - elapsed
    return max(0, remaining)

def _fresh_attempt_fields() -> dict:
    return {
        "answers": {},
        "marked_for_review": [],
        "started_at": time.time(),
        "submitted_at": None,
    }

def start_full_test_attempt(db, test_id: str, username: str):
    test = db["full_tests"][test_id]
    sub = test["submissions"].get(username)

    if sub is not None and sub.get("submitted_at") is None:
        return 

    fresh = _fresh_attempt_fields()
    if sub is not None:
        fresh["best"] = sub.get("best")
        fresh["attempt_count"] = sub.get("attempt_count", 0)
    else:
        fresh["best"] = None
        fresh["attempt_count"] = 0
    test["submissions"][username] = fresh
    _safe_save(db)

def save_full_test_answer(db, test_id: str, username: str, question_index: int, choice: str):
    test = db["full_tests"][test_id]
    sub = test["submissions"].get(username)
    if not sub or sub.get("submitted_at") is not None:
        return
    sub["answers"][str(question_index)] = choice
    _safe_save(db)

def sync_full_test_progress(db, test_id: str, username: str, answers: dict, marked_for_review: list):
    test = db["full_tests"][test_id]
    sub = test["submissions"].get(username)
    if not sub or sub.get("submitted_at") is not None:
        return
    sub["answers"] = dict(answers)
    sub["marked_for_review"] = list(marked_for_review)
    _safe_save(db)

def toggle_mark_for_review(db, test_id: str, username: str, question_index: int):
    test = db["full_tests"][test_id]
    sub = test["submissions"].get(username)
    if not sub or sub.get("submitted_at") is not None:
        return
    marked = sub.setdefault("marked_for_review", [])
    if question_index in marked:
        marked.remove(question_index)
    else:
        marked.append(question_index)
    _safe_save(db)

def _grade_and_finalize_submission(test: dict, sub: dict):
    questions = test["questions"]
    correct = wrong = unattempted = 0
    for i, q in enumerate(questions):
        chosen = sub["answers"].get(str(i))
        if chosen is None:
            unattempted += 1
        elif chosen == q["answer"]:
            correct += 1
        else:
            wrong += 1
    score = correct * test["marks_correct"] + wrong * test["marks_wrong"]
    submitted_at = time.time()

    this_attempt = {
        "answers": dict(sub["answers"]),
        "score": score,
        "correct_count": correct,
        "wrong_count": wrong,
        "unattempted_count": unattempted,
        "started_at": sub["started_at"],
        "submitted_at": submitted_at,
    }

    previous_best = sub.get("best")
    if previous_best is None or score > previous_best["score"]:
        sub["best"] = this_attempt

    sub["attempt_count"] = sub.get("attempt_count", 0) + 1
    sub["submitted_at"] = submitted_at

def submit_full_test(db, test_id: str, username: str):
    test = db["full_tests"][test_id]
    sub = test["submissions"].get(username)
    if not sub or sub.get("submitted_at") is not None:
        return
    _grade_and_finalize_submission(test, sub)
    _safe_save(db)

def get_full_test_leaderboard(test: dict) -> list:
    rows = []
    for username, sub in test["submissions"].items():
        best = sub.get("best")
        if best is None:
            continue
        time_taken = best["submitted_at"] - best["started_at"]
        rows.append((username, best["score"], best["correct_count"], best["wrong_count"], best["unattempted_count"], time_taken))
    rows.sort(key=lambda r: (-r[1], r[5])) 
    return rows

def render_full_test_leaderboard(test: dict, highlight_user: str = None):
    import html as html_lib

    rows = get_full_test_leaderboard(test)
    if not rows:
        ui.label("No submissions yet.").classes('text-sm text-gray-500')
        return

    rows_html = []
    for i, (username, score, correct, wrong, unattempted, time_taken) in enumerate(rows):
        rank = i + 1
        is_top3 = rank <= 3
        is_me = highlight_user is not None and username == highlight_user
        row_classes = "lb-row" + (" top3" if is_top3 else "") + (" me" if is_me else "")
        rank_classes = "lb-rank" + (" top3" if is_top3 else "")
        mins = int(time_taken // 60)
        display_name = html_lib.escape(username.capitalize()) + (" (You)" if is_me else "")

        rows_html.append(
            f"<div class='{row_classes}'>"
            f"<div class='{rank_classes}'>#{rank}</div>"
            f"<div class='lb-name'>{display_name}</div>"
            f"<div class='lb-meta'>{correct} correct - {wrong} wrong - {unattempted} skipped - {mins} min</div>"
            f"<div class='lb-score'>{score} pts</div>"
            f"</div>"
        )

    ui.html("".join(rows_html))

# ----------------------------------------------------------------------
# LEADERBOARD 
# ----------------------------------------------------------------------

def render_leaderboard(db, highlight_user: str = None):
    import html as html_lib

    session_scores = db.get("current_session_scores", {})
    all_students = [u for u, info in db["users"].items() if info["role"] == "student"]

    if not all_students:
        ui.label("No students yet.").classes('text-sm text-gray-500')
        return

    ranked = sorted(all_students, key=lambda u: session_scores.get(u, 0), reverse=True)

    ui.label("Today's Session").classes('font-bold mt-4 mb-2')
    rows_html = []
    for i, student in enumerate(ranked):
        rank = i + 1
        is_top3 = rank <= 3
        is_me = highlight_user is not None and student == highlight_user
        row_classes = "lb-row" + (" top3" if is_top3 else "") + (" me" if is_me else "")
        rank_classes = "lb-rank" + (" top3" if is_top3 else "")

        session_pts = session_scores.get(student, 0)
        lifetime_pts = db["users"][student].get("lifetime_score", 0)
        display_name = html_lib.escape(student.capitalize()) + (" (You)" if is_me else "")

        rows_html.append(
            f"<div class='{row_classes}'>"
            f"<div class='{rank_classes}'>#{rank}</div>"
            f"<div class='lb-name'>{display_name}</div>"
            f"<div class='lb-meta'>{lifetime_pts} lifetime</div>"
            f"<div class='lb-score'>{session_pts} pts</div>"
            f"</div>"
        )

    ui.html("".join(rows_html))
