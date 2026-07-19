from nicegui import ui

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

:root {
    --bg: #0b0f17;
    --bg-raised: #10151f;
    --bg-card: #131a26;
    --bg-card-hover: #17202f;
    --accent: #5b5fef;
    --accent-hover: #7477f2;
    --accent-dim: rgba(91, 95, 239, 0.14);
    --success: #22c55e;
    --success-dim: rgba(34, 197, 94, 0.14);
    --danger: #ef4444;
    --danger-dim: rgba(239, 68, 68, 0.14);
    --warning: #f5a623;
    --warning-dim: rgba(245, 166, 35, 0.14);
    --text: #e7eaf0;
    --text-dim: #9aa4b6;
    --text-faint: #5b6577;
    --border: rgba(231, 234, 240, 0.08);
    --border-strong: rgba(231, 234, 240, 0.16);
    --sans: 'Inter', -apple-system, sans-serif;
    --mono: 'JetBrains Mono', 'Courier New', monospace;
}

body { font-family: var(--sans); color: var(--text); background: var(--bg); }

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg-raised); }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 8px; }

.mono-num { font-family: var(--mono); font-variant-numeric: tabular-nums; font-weight: 600; }

/* ============ LIVE STATUS DOT ============ */
.pulse-dot {
    display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: var(--success); box-shadow: 0 0 0 rgba(34,197,94,0.5);
    animation: pulseDot 1.8s infinite;
}
@keyframes pulseDot {
    0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.55); }
    70% { box-shadow: 0 0 0 6px rgba(34,197,94,0); }
    100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}
.offline-dot { display:inline-block; width:7px; height:7px; border-radius:50%; background: var(--text-faint); }

/* ============ HERO / LANDING ============ */
.hero-wrap { text-align: center; padding: 64px 20px 32px 20px; }
.hero-eyebrow {
    font-family: var(--mono); font-size: 0.74rem; letter-spacing: 0.14em;
    color: var(--accent); text-transform: uppercase; margin-bottom: 16px;
    display: inline-flex; align-items: center; gap: 8px;
}
.hero-title {
    font-family: var(--sans); font-weight: 800; font-size: 3rem; line-height: 1.08;
    color: var(--text); margin: 0 0 14px 0; letter-spacing: -0.02em;
}
.hero-title em { color: var(--accent); font-style: normal; }
.hero-sub {
    font-size: 1.05rem; color: var(--text-dim); max-width: 560px;
    margin: 0 auto 8px auto; line-height: 1.6;
}
@keyframes fadeSlideIn { 0% { opacity: 0; transform: translateY(12px); } 100% { opacity: 1; transform: translateY(0); } }
.anim-in { animation: fadeSlideIn 0.5s cubic-bezier(0.16,1,0.3,1) forwards; }
.anim-in-delay-1 { animation: fadeSlideIn 0.5s cubic-bezier(0.16,1,0.3,1) 0.08s forwards; opacity:0; }
.anim-in-delay-2 { animation: fadeSlideIn 0.5s cubic-bezier(0.16,1,0.3,1) 0.16s forwards; opacity:0; }

.vitals-strip { display: flex; justify-content: center; gap: 0; flex-wrap: wrap; margin: 28px 0 8px 0; }
.vital-stat { padding: 0 28px; text-align: center; border-right: 1px solid var(--border); }
.vital-stat:last-child { border-right: none; }
.vital-stat .num { font-family: var(--mono); font-size: 1.6rem; font-weight: 700; color: var(--accent); }
.vital-stat .label { font-size: 0.7rem; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.07em; margin-top: 2px; }

/* ============ METRIC / SCORE TILES ============ */
.metric-tile {
    background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
    padding: 18px; text-align: center;
}
.metric-tile .val { font-family: var(--mono); font-size: 1.9rem; font-weight: 700; color: var(--accent); line-height: 1.1; }
.metric-tile .lbl { font-size: 0.74rem; color: var(--text-dim); margin-top: 6px; text-transform: uppercase; letter-spacing: 0.05em; }

/* ============ QUESTION CARD (live quiz) ============ */
.quiz-header-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; margin-bottom: 4px; }
.quiz-header-row .quiz-heading { flex: 1; min-width: 0; font-size: 1.05rem; line-height: 1.5; }
.quiz-badges { flex-shrink: 0; display: flex; gap: 8px; }
.progress-badge, .timer-badge {
    flex-shrink: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-width: 62px; padding: 6px 12px; border-radius: 8px; background: var(--bg-raised);
    border: 1px solid var(--border-strong); line-height: 1.1;
}
.progress-badge .t-val { font-family: var(--mono); font-size: 1.15rem; font-weight: 700; color: var(--accent); font-variant-numeric: tabular-nums; }
.timer-badge .t-val { font-family: var(--mono); font-size: 1.15rem; font-weight: 700; color: var(--text); font-variant-numeric: tabular-nums; }
.progress-badge .t-lbl, .timer-badge .t-lbl { font-size: 0.6rem; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 1px; }
.timer-badge.urgent { border-color: var(--warning); background: var(--warning-dim); }
.timer-badge.urgent .t-val { color: var(--warning); }

@keyframes popIn { 0% { opacity:0; transform: scale(0.96); } 100% { opacity:1; transform: scale(1); } }
.reveal-box { animation: popIn 0.35s cubic-bezier(0.16,1,0.3,1) forwards; background: var(--success-dim); border: 1px solid rgba(34,197,94,0.3); padding: 18px; border-radius: 10px; margin-top: 12px; }
.reveal-box.wrong { background: var(--danger-dim); border: 1px solid rgba(239,68,68,0.3); }

/* ============ EXAM MODE - SIGNATURE ELEMENT ============ */
.exam-bar {
    position: sticky; top: 0; z-index: 999;
    display: flex; align-items: center; justify-content: space-between;
    gap: 16px; background: var(--bg-raised); border: 1px solid var(--border-strong);
    border-radius: 12px; padding: 14px 20px; margin-bottom: 18px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35);
}
.exam-bar-title { font-weight: 700; font-size: 0.95rem; color: var(--text); }
.exam-bar-clock {
    font-family: var(--mono); font-size: 1.4rem; font-weight: 700; color: var(--text);
    font-variant-numeric: tabular-nums; letter-spacing: 0.02em;
}
.exam-bar-clock.urgent { color: var(--warning); animation: clockPulse 1s infinite; }
@keyframes clockPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.55; } }
.exam-bar-stats { display: flex; gap: 18px; }
.exam-stat { text-align: center; }
.exam-stat .n { font-family: var(--mono); font-size: 1.05rem; font-weight: 700; }
.exam-stat .l { font-size: 0.62rem; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.05em; }
.exam-stat.answered .n { color: var(--success); }
.exam-stat.marked .n { color: var(--warning); }
.exam-stat.unattempted .n { color: var(--text-faint); }

/* ============ SIDEBAR / ROSTER ============ */
.roster-row { display: flex; align-items: center; gap: 8px; padding: 6px 4px; font-size: 0.86rem; }
.roster-name { color: var(--text); font-weight: 500; }
.roster-name.offline { color: var(--text-faint); }
.roster-role-tag { font-family: var(--mono); font-size: 0.62rem; padding: 1px 6px; border-radius: 6px; background: var(--bg-card); color: var(--text-faint); margin-left: auto; }

/* ============ LEADERBOARD ============ */
.lb-row {
    display: flex; align-items: center; gap: 14px; padding: 12px 16px;
    border-radius: 10px; margin-bottom: 6px; background: var(--bg-card);
    border: 1px solid var(--border);
}
.lb-row.me { border-color: var(--accent); background: var(--accent-dim); }
.lb-row.top3 { border-color: var(--warning); }
.lb-rank { font-family: var(--mono); font-weight: 800; font-size: 1.1rem; color: var(--text-dim); min-width: 34px; }
.lb-rank.top3 { color: var(--warning); }
.lb-name { flex: 1; font-weight: 600; }
.lb-score { font-family: var(--mono); font-weight: 700; color: var(--accent); font-size: 1.05rem; }
.lb-meta { font-size: 0.74rem; color: var(--text-faint); font-family: var(--mono); }

@media (max-width: 640px) {
    .hero-title { font-size: 2rem; }
    .vitals-strip { gap: 6px; }
    .vital-stat { padding: 0 14px; border-right: none; }
    .exam-bar { flex-direction: column; align-items: stretch; gap: 10px; }
}

/* ============ SIDEBAR / DRAWER ============ */
.app-drawer { background: var(--bg-raised) !important; border-right: 1px solid var(--border); }

.drawer-brand { display: flex; align-items: center; gap: 10px; padding: 4px 4px 20px 4px; }
.drawer-brand-mark {
    width: 34px; height: 34px; border-radius: 9px; background: var(--accent);
    color: white; font-weight: 800; font-family: var(--mono);
    display: flex; align-items: center; justify-content: center; font-size: 1rem;
    flex-shrink: 0;
}
.drawer-brand-title { font-weight: 700; font-size: 0.95rem; color: var(--text); line-height: 1.2; }
.drawer-brand-sub { font-size: 0.72rem; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.05em; }

.nav-item {
    display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 10px;
    cursor: pointer; color: var(--text-dim); transition: background 0.15s ease, color 0.15s ease;
    width: 100%;
}
.nav-item:hover { background: var(--bg-card-hover); color: var(--text); }
.nav-item.active { background: var(--accent-dim); color: var(--accent-hover); }
.nav-item-icon { font-size: 1.2rem !important; }
.nav-item-label { font-weight: 600; font-size: 0.9rem; }

.roster-heading {
    font-size: 0.68rem; font-weight: 700; color: var(--text-faint);
    letter-spacing: 0.08em; margin-bottom: 10px; display: block;
}

/* ============ PAGE HEADER ============ */
.page-header { padding: 4px 0 20px 0; }
.page-title { font-family: var(--sans); font-weight: 800; font-size: 1.7rem; color: var(--text); letter-spacing: -0.01em; }
.page-subtitle { font-size: 0.92rem; color: var(--text-dim); margin-top: 4px; }

.section-title { font-family: var(--sans); font-weight: 700; font-size: 1.3rem; color: var(--text); display: block; }
.section-caption { font-size: 0.88rem; color: var(--text-dim); display: block; margin-top: 2px; }
.empty-state { font-size: 0.9rem; color: var(--text-faint); padding: 12px 0; display: block; }
.text-dim { color: var(--text-dim); }

/* ============ FORM SECTIONS (admin builder) ============ */
.builder-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; }
.form-section-header { margin-bottom: 10px; }
.form-section-title { font-size: 0.78rem; font-weight: 700; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.07em; }
.form-section-caption { font-size: 0.82rem; color: var(--text-dim); margin-top: 1px; }

.key-warning-banner {
    background: var(--warning-dim); border: 1px solid rgba(245,166,35,0.3);
    border-radius: 10px; padding: 12px 16px; color: var(--warning);
}

.app-tabs { border-bottom: 1px solid var(--border); }

/* ============ STATUS PILLS ============ */
.status-pill {
    display: inline-block; font-family: var(--mono); font-size: 0.7rem; font-weight: 700;
    padding: 3px 10px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.04em;
    white-space: nowrap;
}
.status-pill.draft { background: rgba(154,164,182,0.14); color: var(--text-dim); }
.status-pill.open { background: var(--success-dim); color: var(--success); }
.status-pill.closed { background: var(--danger-dim); color: var(--danger); }

/* ============ LIST CARDS (tests, DPPs, admin manage list) ============ */
.list-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; transition: border-color 0.15s ease; }
.list-card:hover { border-color: var(--border-strong); }
.list-card-title { font-weight: 700; font-size: 1.02rem; color: var(--text); }
.list-card-meta { font-size: 0.82rem; color: var(--text-dim); display: block; }

.app-expansion { background: var(--bg-raised); border-radius: 10px; border: 1px solid var(--border); }
.app-grid { border-radius: 10px; overflow: hidden; }

/* ============ GENERATE BUTTON ============ */
.generate-btn { font-weight: 600; }

/* ============ QUESTION-TAKING UI ============ */
.question-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; }
.question-index-label { font-size: 0.78rem; font-weight: 700; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.06em; }
.question-text { font-size: 1.15rem; font-weight: 600; color: var(--text); line-height: 1.5; margin-top: 8px; }
.quiz-live-question { font-size: 1.2rem; font-weight: 700; color: var(--text); line-height: 1.5; }

.option-radio .q-radio { padding: 10px 6px; }
.option-radio { background: var(--bg-raised); border-radius: 10px; padding: 6px 10px; }

.submit-confirm-box {
    background: var(--warning-dim); border: 1px solid rgba(245,166,35,0.3);
    border-radius: 10px; padding: 14px 16px;
}

/* ============ QUESTION PALETTE ============ */
.palette-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; align-self: flex-start; }
.qpalette-btn-wrap { display: flex; flex-wrap: wrap; }
.qpalette-btn {
    width: 38px !important; height: 38px !important; min-height: 38px !important;
    border-radius: 9px !important; font-family: var(--mono); font-weight: 700; font-size: 0.85rem;
    display: flex; align-items: center; justify-content: center; padding: 0 !important;
}
.qpalette-btn.unanswered { background: var(--bg-raised); color: var(--text-faint); border: 1px solid var(--border-strong); }
.qpalette-btn.answered { background: var(--success-dim); color: var(--success); border: 1px solid rgba(34,197,94,0.3); }
.qpalette-btn.marked { background: var(--warning-dim); color: var(--warning); border: 1px solid rgba(245,166,35,0.3); }
.qpalette-btn.current { background: var(--accent); color: white; border: 1px solid var(--accent); }

.legend-swatch { width: 16px; height: 16px; border-radius: 5px; flex-shrink: 0; }

/* ============ REVIEW (past attempts) ============ */
.review-q-label { font-weight: 700; color: var(--text); font-size: 0.98rem; line-height: 1.5; }
.review-option {
    display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 8px;
    background: var(--bg-raised); font-size: 0.9rem; color: var(--text-dim);
}
.review-option .material-icons { font-size: 1.1rem; }
.review-option.correct { background: var(--success-dim); color: var(--success); font-weight: 600; }
.review-option.wrong { background: var(--danger-dim); color: var(--danger); font-weight: 600; }
.review-option-tag {
    margin-left: auto; font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.04em; opacity: 0.8;
}

@media (max-width: 900px) {
    .palette-card { display: none; }
}
</style>
"""

def inject_css():
    ui.add_head_html(CSS)
    # Enforce NiceGUI's dark mode to match your PW/Unacademy style theme
    ui.dark_mode(True)

def pulse_dot_html(online: bool) -> str:
    return "<span class='pulse-dot'></span>" if online else "<span class='offline-dot'></span>"
