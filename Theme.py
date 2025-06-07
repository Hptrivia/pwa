import os
import json
import random
import datetime
import math
import gradio as gr

PERSISTENT_DIR = "/mnt/persistent"
FEEDBACK_FILE   = os.path.join(PERSISTENT_DIR, "feedback.txt")
LEADERBOARD_FILE     = os.path.join(PERSISTENT_DIR, "leaderboard.json")
VOUCHER_FILE     = os.path.join(PERSISTENT_DIR, "vouchers.json")

# ----------------- Load Questions -----------------
theme_files = {
    "Friends":  "FRIENDS.txt",
    "Naruto":   "Naruto.txt",
    "Avengers": "avengers.txt",
    "The Office": "Office.txt",
    "The Big Bang Theory": "TBBT.txt"
}

theme_questions = {
    theme: json.load(open(path, "r", encoding="utf-8"))
    for theme, path in theme_files.items()
}

friend_templates_by_theme = {
    "Friends": {
        "Chandler":   "Could it *be* any more obvious? The answer is {answer}.",
        "Joey":       "How you doin'? The answer is {answer}.",
        "Monica":     "I've cleaned the data: the answer is {answer}.",
        "Ross":       "Pivot! The answer is {answer}.",
        "Phoebe":     "Smelly cat, smelly cat, the answer’s {answer}.",
    },
    "The Big Bang Theory": {
        "Sheldon Cooper":     "Bazinga! Of course the answer is {answer}.",
        "Leonard Hofstadter": "According to my calculations, the answer is {answer}.",
        "Howard Wolowitz":    "In zero-G or on Earth, only one constant stands: {answer}.",
        "Raj Koothrappali":   "I still can’t talk to women… but I can tell you the answer: {answer}.",
        "Penny":              "Aww, sweetie, the answer is {answer}.",
    },
    "The Office": {
        "Michael Scott":    "That’s what she said: {answer}.",
        "Jim Halpert":      "Bears. Beets. Battlestar Galactica. Actually, the answer is {answer}.",
        "Dwight Schrute":   "Now look who needs my help. The answer is: {answer}.",
        "Pam Beesly":       "I sketched this whole scenario—every line leads back to {answer}.",
        "Creed Bratton":    "I’m not sure what we’re doing here, but the answer is {answer}.",
    },
    "Naruto": {
        "Naruto Uzumaki":  "Never give up! The answer is {answer}.",
        "Sasuke Uchiha":   "My vengeance is complete. Now the truth remains: the answer is {answer}.",
        "Sakura Haruno":   "I will heal all your doubts: the answer is {answer}.",
        "Kakashi Hatake":  "My Copy-Ninja Technique shows that the answer is {answer}.",
        "Shikamaru Nara":  "Troublesome… but the answer is {answer}.",
    },
    "Avengers": {
        "Iron Man":       "I am Iron Man—and I’m never wrong. The answer is {answer}.",
        "Captain America":"I can do this all day. The answer is {answer}.",
        "Thor":           "By Odin’s beard… it’s {answer}.",
        "Hulk":           "Hulk SMASH wrong answers. Only {answer} stands.",
        "Black Panther":  "Wakanda forever, the answer is {answer}.",
        "Black Widow":    "Tactical analysis shows the right answer is {answer}.",
    }
}

# ----------------- Load & Save vouchers -----------------

def load_vouchers():
     os.makedirs(PERSISTENT_DIR, exist_ok=True)
     if not os.path.isfile(VOUCHER_FILE):
        with open(VOUCHER_FILE, "w") as f:
            json.dump({}, f, indent=2)
        return {}
     with open(VOUCHER_FILE, "r") as f:
        return json.load(f)

def save_vouchers(v):
    os.makedirs(PERSISTENT_DIR, exist_ok=True)
    with open(VOUCHER_FILE, "w") as f:
        json.dump(v, f, indent=2)


def consume_voucher(code):
    if not code: return
    vouchers = load_vouchers()
    if code in vouchers and not vouchers[code]["consumed"]:
        vouchers[code]["consumed"] = True
        save_vouchers(vouchers)
# ----------------- Mix & Shuffle Logic -----------------
def get_randomized_run(n=None, difficulties=None, theme=None):
    # 1) Build the initial pool
    if theme:
        pool = theme_questions.get(theme, []).copy()
    else:
        # No theme → flatten all themes
        pool = [q for qs in theme_questions.values() for q in qs]

    # 2) Pure-difficulty mode shortcut
    if difficulties:
        filtered = [
            q for q in pool
            if q.get("difficulty", "easy").strip().lower() in difficulties
        ]
        random.shuffle(filtered)
        return filtered[: n or len(filtered)]

    # 3) Bucket-and-block logic with fallback
    if n is None:
        n = len(pool)

    buckets = {"easy": [], "medium": [], "hard": [], "expert": []}
    for q in pool:
        d = q.get("difficulty", "easy").strip().lower()
        buckets.setdefault(d if d in buckets else "easy", []).append(q)

    def pop_with_fallback(diff):
        order = ["easy", "medium", "hard", "expert"]
        idx = order.index(diff)
        # try requested diff, then step down to easier ones
        for i in range(idx, -1, -1):
            b = order[i]
            if buckets[b]:
                return buckets[b].pop(random.randrange(len(buckets[b])))
        return None

    run, full_blocks = [], n // 10
    for _ in range(full_blocks):
        if not any(buckets.values()):
            break
        block = []
        # one per difficulty (or fallback)
        for diff in ["easy", "medium", "hard", "expert"]:
            q = pop_with_fallback(diff)
            if q:
                block.append(q)
        # fill out to 10 from whatever remains
        remaining = [q for bl in buckets.values() for q in bl]
        for _ in range(10 - len(block)):
            if not remaining:
                break
            q = remaining.pop(random.randrange(len(remaining)))
            bkt = q.get("difficulty", "easy").lower()
            buckets[bkt].remove(q)
            block.append(q)
        random.shuffle(block)
        run.extend(block)

    # 4) Any leftover to hit n?
    rem = n - len(run)
    if rem > 0:
        leftover = [q for bl in buckets.values() for q in bl]
        random.shuffle(leftover)
        run.extend(leftover[:rem])

    return run



# ----------------- Feedback & Leaderboard -----------------
def save_feedback(msg):
    msg=msg.strip()
    if not msg:
        return gr.update(value="⚠️ Enter feedback before submitting.",visible=True), gr.update(value="")
    os.makedirs(PERSISTENT_DIR, exist_ok=True)    
    ts=datetime.datetime.now().isoformat()
    with open(FEEDBACK_FILE,"a",encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n\n")
    return gr.update(value="✅ Thanks for your feedback!",visible=True), gr.update(value="")

def save_leaderboard(theme, nick, pin, score):
    os.makedirs(PERSISTENT_DIR, exist_ok=True)
    key = f"{theme}|{nick}|{pin}"
    if os.path.exists(LEADERBOARD_FILE):
        data = json.load(open(LEADERBOARD_FILE, "r", encoding="utf-8"))
    else:
        data = {}
    if score > data.get(key, 0):
        data[key] = score
        json.dump(data, open(LEADERBOARD_FILE,"w",encoding="utf-8"), indent=2)
        
def save_leaderboard_if_no_voucher(theme, nickname, pin, score, voucher_code):
    # if they ever redeemed a voucher this run, don’t record them
    if voucher_code:
        return
    save_leaderboard(theme, nickname, pin, score)
    
def get_leaderboard(theme, top_n=20):
    if not os.path.exists(LEADERBOARD_FILE):
        return "## 🏆 Leaderboard\n\n_No scores yet._"
    # 1) Read with explicit UTF-8 encoding
    with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2) Drop entries whose nickname (before the “|”) is empty
    entries = []
    prefix = theme + "|"
    for full_key, pts in data.items():
        if full_key.startswith(prefix):
            _theme, nick, _pin = full_key.split("|", 2)
            if nick.strip():
                entries.append((nick, pts))

    # 3) Sort descending by score, take top_n
    entries = sorted(entries, key=lambda kv: kv[1], reverse=True)[:top_n]

    # 4) Render Markdown
    md = "## 🏆 Leaderboard\n\n"
    for i, (nick, pts) in enumerate(entries, start=1):
        md += f"**{i}. {nick}** — {pts} pts\n\n"

    return md


# ----------------- Core Quiz Logic -----------------
def get_question(q_list, q_index, score,
                 streak_score, streak_active, fifty_used, call_used):
    q = q_list[q_index]
    # 1) Difficulty label
    diff = q.get("difficulty", "easy").capitalize()
    # 2) Debug info
    debug = f"🔥 Streak: {streak_score} | {'Active ✅' if streak_active else 'Inactive'}"
    # 3) Shuffle options safely
    opts = q["options"].copy()
    random.shuffle(opts)
    # 4) Markdown question
    question_md = f"### Q{q_index+1}: {q['question']}"

    return (
        question_md,
        gr.update(choices=opts, value=None, interactive=True),
        gr.update(visible=False),  # hide any previous “next” / “restart”
        gr.update(visible=False),
        gr.update(value=f"Score: {score}"),
        diff,
        gr.update(value="", visible=False),       # clear wizard hint
        gr.update(value="⏱️ Time: 30"),            # 40 s timer
        30,                                        # initial time_left
        False,                                     # timer_running
        gr.update(interactive=True),               # enable “Submit”
        True,                                      # answered=False → timer starts
        gr.update(value=debug)
    )


def initialize_with_list(
    run_list,
    early_reveal_flag,
    unlimited_flag,
    disable_timer_flag
):
    # 1) Reset scores & flags
    score = streak_score = 0
    streak_active = fifty_used = call_used = False

    # 2) Prime first question
    core = get_question(
        run_list, 0,
        score, streak_score,
        streak_active, fifty_used, call_used
    )

    # 3) Unpack core + reset values + pointers + buttons + page toggles + flags
    return (
        *core,
        # reset scores & lifelines
        score, streak_score, streak_active, fifty_used, call_used,
        # quiz data pointers
        run_list, 0,
        # lifeline buttons
        gr.update(interactive=True),  # fifty_btn
        gr.update(interactive=True),  # call_btn
        # clear any old hint
        gr.update(value="", visible=False),  # wizard_hint / friend_hint
        # hide pre-quiz menus
        gr.update(visible=False),  # theme_menu or mode_page
        gr.update(visible=True),   # quiz_block
        # hide any other nav (if you have rules_box, show_rules_btn, etc.)
        gr.update(visible=False),  # rules_box
        gr.update(visible=False),  # show_rules_btn
        gr.update(visible=False),  # start_game_btn
        gr.update(visible=False),  # feedback_btn
        gr.update(visible=False),  # leaderboard_btn
        gr.update(visible=False),  # support_btn
        # finally, carry forward your shop flags
        early_reveal_flag,
        unlimited_flag,
        disable_timer_flag
    )

def next_question(
    q_list, q_index, score,
    streak_score, streak_active,
    fifty_used, call_used, unlimited_lifelines_enabled, voucher_code
):
    # 1) advance index
    new_i = q_index + 1

    # 2) Game-over branch (keep this!)
    if new_i >= len(q_list):
        return (
            # Replace the quiz with a final‐score Markdown
            f"## 🏁 Game Over!\n\nYour final score: {score}",
            # disable answer choices and submit
            gr.update(choices=[], visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(value=f"Score: {score}"),
            "",
            gr.update(value="", visible=False),
            gr.update(value="⏱️ 0"),
            0,
            False,
            gr.update(interactive=False),
            False,
            gr.update(value=""),
            new_i,
            gr.update(interactive=False),
            gr.update(interactive=False),
            False,
            gr.update(value="")
        )

    # 2) get the fresh question UI
    core = get_question(q_list, new_i, score, streak_score, streak_active, fifty_used, call_used)

    # 3) decide call-wizard button
    call_update = gr.update(interactive=not call_used)

    # 4) decide 50/50 button
    #    either you’ve bought unlimited *or* you still have a valid “fifty” voucher
    vouchers = load_vouchers()
    has_fifty_voucher = (
        voucher_code
        and voucher_code in vouchers
        and vouchers[voucher_code]["type"] == "fifty"
        and not vouchers[voucher_code]["consumed"]
    )
    fifty_update = gr.update(interactive=(unlimited_lifelines_enabled or not fifty_used or has_fifty_voucher))
    has_call_voucher = (
    voucher_code
    and voucher_code in vouchers
    and vouchers[voucher_code]["type"] == "call"
    and not vouchers[voucher_code]["consumed"]
    )
    call_update = gr.update(interactive=(unlimited_lifelines_enabled or not call_used or has_call_voucher))


    # 5) clear any old wizard hint
    wiz_clear = gr.update(value="", visible=False)

    return (
        *core,
        new_i,
        fifty_update,
        call_update,
        call_used,
        wiz_clear
    )


def check_answer(
    selected,
    q_index,
    q_list,
    score,
    answered,
    streak_score,
    streak_active,
    fifty_used,
    call_used,
    unlimited_lifelines_enabled  # new: from shop/voucher
):
    q       = q_list[q_index]
    correct = q["answer"]
    pts     = {"easy": 1, "medium": 2, "hard": 3, "expert": 4}
    earned  = pts.get(q.get("difficulty", "easy"), 1)

    # Gate both lifelines on the “unlimited” shop flag
    lifeline_btn_update = gr.update(interactive=unlimited_lifelines_enabled)

    # These come back on if you restore them via a streak
    enable50 = gr.update(interactive=True)
    enablec  = gr.update(interactive=True)

    # 1) No answer selected or already answered?
    if answered or selected is None:
        return (
            gr.update(interactive=True),           # answer_radio re-enabled
            gr.update(value="⚠️ Please pick an option.", visible=True),
            gr.update(visible=False),              # next_btn
            gr.update(visible=False),              # restart_btn
            score, False, True,                    # score, answered, timer_running
            streak_score, streak_active,
            fifty_used, call_used,
            gr.update(interactive=True),           # submit_btn
            lifeline_btn_update,                   # fifty_btn
            lifeline_btn_update,                   # call_btn
            gr.update(value=f"⚠️ | Streak: {streak_score}")
        )

    # 2) Correct answer branch
    if selected == correct:
        score += earned
        if streak_active:
            streak_score += earned
        elif fifty_used and call_used:
            # both lifelines used → start a streak
            streak_active, streak_score = True, 0

        msgs = ["✅ Correct!"]
        if fifty_used and streak_score >= 25:
            fifty_used = False
            msgs.append("🎲 50:50 restored!")
        if call_used and streak_score >= 50:
            call_used = False
            msgs.append("📞 Call-a-Friend restored!")

        feedback = gr.update(value="  ".join(msgs), visible=True)

        # if you’ve now restored both, end the streak
        if not fifty_used and not call_used:
            streak_active, streak_score = False, 0

        nv, rv = True, False  # show Next, hide Play Again

    else:
        # 3) Wrong answer branch
        feedback      = gr.update(value="❌ Wrong!", visible=True)
        streak_score  = 0
        streak_active = False
        nv, rv        = False, True

    dbg = f"🔥 Streak: {streak_score} | {'Active ✅' if streak_active else 'Inactive'}"

    # 4) Return exactly the 15 outputs your Gradio callback expects
    return (
        gr.update(interactive=False),  # disable submit_btn
        feedback,
        gr.update(visible=nv),         # next_btn
        gr.update(visible=rv),         # restart_btn
        score,
        True,                          # answered
        False,                         # timer_running
        streak_score, streak_active,
        fifty_used, call_used,
        gr.update(interactive=False),  # submit_btn (redundant, but HP does it)
        lifeline_btn_update,           # fifty_btn
        lifeline_btn_update,           # call_btn
        gr.update(value=dbg)           # debug_info
    )


def use_fifty(
    q_list,
    q_index,
    streak_active,
    call_used,
    unlimited_lifelines_enabled,  # shop flag
    voucher_code                  # redeemed code
):
    q = q_list[q_index]
    opts = q["options"]
    correct = q["answer"]

    # 1) Not enough options?
    if len(opts) <= 2:
        return (
            gr.update(),                # answer_radio untouched
            gr.update(interactive=False), 
            streak_active, True, call_used,
            gr.update(value="⚠️ Not enough options", visible=True),
            gr.update(value="")
        )

    # 2) Build the reduced choice set
    wrong = [o for o in opts if o != correct]
    reduced = random.sample(wrong, 1) + [correct]
    random.shuffle(reduced)

    # 3) Voucher vs unlimited logic
    vouchers = load_vouchers()
    is_voucher_valid = (
        voucher_code
        and voucher_code in vouchers
        and vouchers[voucher_code]["type"] == "fifty"
        and not vouchers[voucher_code]["consumed"]
    )
    keep_btn = unlimited_lifelines_enabled or is_voucher_valid

    # 4) Consume the voucher if it was valid
    if is_voucher_valid:
        consume_voucher(voucher_code)

    # 5) Build the debug message
    if streak_active:
        debug_msg = "✅ 50:50 used — ⚠️ Streak broken"
        streak_active = False
    else:
        debug_msg = "✅ 50:50 used"

    # 6) Return exactly the 7 outputs your Gradio callback expects
    return (
        gr.update(choices=reduced, value=None, interactive=True),  # answer_radio
        gr.update(interactive=keep_btn),                           # fifty_btn
        streak_active,                                             # streak_active
        True,                                                      # fifty_used
        call_used,                                                 # call_used
        gr.update(value=debug_msg, visible=True),                 # feedback
        gr.update(value="")                                        # debug_info
    )


def call_friend(
    q_list, q_index,
    fifty_used, call_used,
    unlimited_lifelines_enabled,
    voucher_code, selected_theme
):
    q= q_list[q_index]
    correct = q["answer"]

    # pick a theme‐specific template dict (fall back to a default if needed)
    templates = friend_templates_by_theme.get(
        selected_theme,
        {"Friend": "I think it's {answer}."}
    )

    # choose a random character from this theme
    friend = random.choice(list(templates.keys()))
    hint_text = templates[friend].format(answer=correct)
    hint = f"📞 {friend}: {hint_text}"

    # Voucher validation & single-use consumption
    vouchers = load_vouchers()
    is_valid = (
        voucher_code
        and voucher_code in vouchers
        and vouchers[voucher_code]["type"] == "call"
        and not vouchers[voucher_code]["consumed"]
    )
    keep_btn = unlimited_lifelines_enabled or is_valid
    if is_valid:
        consume_voucher(voucher_code)

    # Return (hint_update, call_btn_update, call_used_flag)
    return (
        gr.update(value=hint, visible=True),
        gr.update(interactive=keep_btn),
        True
    )

def handle_timeout(
    time_left,
    timer_running,
    answered,
    last_update,
    disable_timer_enabled,
    early_reveal_enabled,
    q_list,
    q_index
):
    import datetime, math

    # 1) If the player bought “Disable Timer,” just hide the timer and do nothing
    if disable_timer_enabled:
        return (
            time_left,
            gr.update(visible=False),  # timer_display
            gr.update(),               # feedback
            gr.update(),               # submit_btn
            gr.update(),               # next_btn
            gr.update(),               # restart_btn
            timer_running,
            last_update
        )

    # 2) Normal countdown start/stop
    now = datetime.datetime.now()
    if not timer_running or answered:
        return (
            time_left,
            gr.update(value="⏱️ --"),
            gr.update(), gr.update(), gr.update(), gr.update(),
            timer_running,
            now
        )

    # 3) Tick the clock
    elapsed = (now - last_update).total_seconds()
    new_time = max(0, time_left - elapsed)

    # 4) Early-reveal: show the correct answer when ≤10s remain
    if early_reveal_enabled and new_time <= 10 and not answered:
        correct = q_list[q_index]["answer"]
        feedback_update = gr.update(value=f"🔍 Answer: {correct}", visible=True)
    else:
        feedback_update = gr.update()

    # 5) Time’s up → Game Over branch for timeout
    if new_time <= 0:
        return (
            0,
            gr.update(value="⏱️ 0"),
            gr.update(value="⏱️ Time's up!", visible=True),
            gr.update(interactive=False),
            gr.update(visible=False),
            gr.update(visible=True),
            False,
            now
        )

    # 6) Return normal tick values
    return (
        new_time,
        gr.update(value=f"⏱️ {math.ceil(new_time)}"),
        feedback_update,
        gr.update(), gr.update(), gr.update(),
        timer_running,
        now
    )



# ----------------- Build UI -----------------
with gr.Blocks() as demo:
    
    # --- QUIZ STATE VARIABLES ---
    selected_theme  = gr.State("")
    q_index         = gr.State(0)
    score           = gr.State(0)
    q_list          = gr.State([])
    time_left       = gr.State(30)
    answered        = gr.State(False)
    timer_running   = gr.State(False)
    streak_score    = gr.State(0)
    streak_active   = gr.State(False)
    fifty_used      = gr.State(False)
    call_used       = gr.State(False)
    difficulty_state= gr.State("")
    last_update     = gr.State(datetime.datetime.now())
    early_reveal_enabled   = gr.State(False)
    unlimited_lifelines_enabled    = gr.State(False)
    disable_timer_enabled     = gr.State(False)
    voucher_code_state = gr.State("")

        # --- NICKNAME & PIN STATE ---
    nickname_state  = gr.State("")
    pin_state       = gr.State("")

    # ─── Theme Selection ───────────────────────────────────────────
    with gr.Column(visible=True) as theme_page:
        gr.Markdown("## 🎯 TV Trivia")
        gr.Markdown("## Select the show you want to play")
        friends_btn   = gr.Button("Friends")
        naruto_btn    = gr.Button("Naruto")
        avengers_btn  = gr.Button("Avengers")
        theme4_btn    = gr.Button("The Office")
        theme5_btn    = gr.Button("The Big Bang Theory")

    # ─── Theme Menu (rules + nav buttons) ─────────────────────────
    with gr.Column(visible=False) as theme_menu:
        theme_heading = gr.Markdown("", visible=True)
        rules_md      = gr.Markdown(
            "**🥊 Welcome to the TV Series Trivia Challenge!**  "
            "Answer up to 200 questions of varying difficulty on a 40s timer.  "
            "You have two lifelines—50/50 and Call-a-Friend —which you can restore by answering correct questions.  "
            "One wrong answer ends the game\n\n"
            "**Update Section:**\n\nHere I will be posting updates on new features, challenges, tournaments and prizes for players. Follow on Instagram/Tiktok @triviaking2025 for quicker updates.\n\n"
            "1.**Click on the share icon on the top right of your browser, scroll to the bottom and click add to home screen. This will enable you have the game as an app icon on your phone**\n\n",
            visible=True
        )
        start_quiz_btn  = gr.Button("🎮 Play Quiz")
        shop_btn        = gr.Button("🛍️ Shop", visible=False)
        feedback_btn    = gr.Button("✉️ Send Feedback")
        leaderboard_btn = gr.Button("🏆 Leaderboards")
        support_btn     = gr.Button("💖 Support Me")
        back_to_themes = gr.Button("🔙 Back to Themes", visible=False)
        
    with gr.Column(visible=False) as shop_page:
        gr.Markdown(r"""
        ## 🛍️ Shop
            
        Here you can boost your game with one-time power-ups. **Each power-up lasts for one game (except speciied otherwise)**. You will receive a voucher code
        which you can redeem below to access your purchase:
            
        • 🕑 **Early-Reveal(1 use)** — show the correct answer 10s before the timer runs out  
        <a href="https://ko-fi.com/s/9e1a94ffea" target="_blank">Buy for €2.00 ↗</a>
            
        • ♾️ **Unlimited Lifelines(1 use)** — Reuse Lifelines  
        <a href="https://ko-fi.com/s/82438a6b3c" target="_blank">Buy for €2.00 ↗</a>
            
        • ⏱️ **Disable Timer(1 use)** — no countdown per run  
        <a href="https://ko-fi.com/s/130279c714" target="_blank">Buy for €1.00 ↗</a>
                    
        • 💌 For Custom Trivia Requests, Questions, Themes, Genres etc  
        <a href="mailto:triviaking2025@gmail.com?subject=Custom%20Trivia%20Request">Email me ↗</a>)
        """
        )

        # add a nice separation
      # gr.HTML("<hr style='margin:24px 0;'/>")

         # ⚠️ Warning: only redeem when you’re ready
        warning_msg = gr.Markdown(
        "⚠️ **Please only redeem your voucher once you’re about to use it.**\n"
        "Codes are one-time use and **will not survive** a browser refresh or reuse.",
        visible=True
        )
        
        # Voucher code entry
        code_input    = gr.Textbox(label="Enter Voucher Code", placeholder="E.g. EARLY5")
        redeem_status = gr.Markdown(visible=False)
        redeem_btn = gr.Button("📥 Redeem Code")
        shop_back = gr.Button("🔙 Back")
     

        # ─── Nickname & PIN Entry ─────────────────────────────────────
    with gr.Column(visible=False) as user_entry:
        back_to_menu = gr.Button("🔙 Back", visible=True)
        gr.Markdown(
            "## 📝 Enter a Nickname & PIN (Optional)\n\n"
            "Enter a nickname and a 4-digit PIN to appear on the Leaderboard.\n\n"
            "**You must click on Play Again at game end to save your scores.**\n\n"
            "When you use a voucher code, you are not eligible for the leaderboard in that run.\n\n"
            "Otherwise, just hit **Skip** to jump right in anonymously!"               
            )
        nick_in   = gr.Textbox(label="Nickname")
        pin_in    = gr.Textbox(label="PIN (4 digits)", type="password")
        entry_err = gr.Markdown("", visible=False)
        entry_btn = gr.Button("Start Quiz")
        skip_btn  = gr.Button("Skip")

        
        # ─── GAME-TYPE SELECTION PAGE ──────────────────────────────────────────
    with gr.Column(visible=False) as game_type_page:
        gr.Markdown("## 🎲 Choose Your Adventure")
        gr.Markdown("**If you find any mistakes in the quiz, or a question you feel is incorrect etc. Please contact me via the feedback page**")
        story_btn    = gr.Button("📖 Story Mode")
        gauntlet_btn = gr.Button("⚔️ Trivia Gauntlet")
        versus_btn   = gr.Button("🤝 VS Mode")

    # ─── PLACEHOLDER PAGE FOR COMING SOON MODES ───────────────────────────
    with gr.Column(visible=False) as placeholder_page:
        placeholder_md = gr.Markdown("", visible=False)
        back_from_ph   = gr.Button("🔙 Back to Adventure")
    
        # ─── Difficulty Selection ─────────────────────────────────────
    with gr.Column(visible=False) as mode_page:
        gr.Markdown("## 🛡️ Choose Your Mode")
        easy_btn  = gr.Button("🥉 Easy")
        hard_btn  = gr.Button("🥇 Hard")
        mixed_btn = gr.Button("🔀 Mixed")
    
        # ─── Feedback Page ─────────────────────────────────────────────
    with gr.Column(visible=False) as feedback_page:
        gr.Markdown("## ✉️ Feedback")
        fb_input  = gr.Textbox(label="Your message", lines=5)
        fb_submit = gr.Button("Submit")
        fb_status = gr.Markdown("", visible=False)
        fb_back   = gr.Button("🔙 Back")
            
        gr.Markdown(
            "[Or send me an email ↗](mailto:triviaking2025@gmail.com"
            "?subject=Triwizard%20Feedback)"
    )
    
        # ─── Leaderboard Page ─────────────────────────────────────────
    with gr.Column(visible=False) as leaderboard_page:
        lb_md   = gr.Markdown("", visible=False)
        lb_back = gr.Button("🔙 Back")
    
        # ─── Support Page ─────────────────────────────────────────────
    with gr.Column(visible=False) as support_page:
        gr.Markdown(
            "## 🙏 Support This App\n\n"
            "If you enjoy TriWizard Trivia, please consider supporting me!  "
            "Your support helps me write more questions, add new features and keep the server running.\n\n"
            "☕ Buy me a Beer on [Ko-fi](https://ko-fi.com/triviaking)"
        )
        support_back = gr.Button("🔙 Back")

    
        # ─── Quiz Block ────────────────────────────────────────────────
    with gr.Column(visible=False) as quiz_block:
        question_text = gr.Markdown()
        answer_radio  = gr.Radio(choices=[], label="Choose your answer")
        feedback      = gr.Markdown(visible=False)
        with gr.Row():
            score_display = gr.Markdown("Score: 0")
            timer_display = gr.Markdown("⏱️ Time: 40")
                
        debug_info   = gr.Textbox(label="Debug Info", interactive=False)
        friend_hint  = gr.Textbox(label="Friend's Hint", visible=False, interactive=False)
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Lifelines")
                fifty_btn    = gr.Button("🎲 50:50")
                call_btn     = gr.Button("📞 Call a Friend")
            with gr.Column(scale=1):
                gr.Markdown("### Actions")
                submit_btn   = gr.Button("Submit")
                next_btn     = gr.Button("Next Question", visible=False)
                restart_btn  = gr.Button("Play Again",    visible=False)
    
        gr.Timer(value=1.0).tick(
            fn=handle_timeout,
            inputs=[time_left, timer_running, answered, last_update, disable_timer_enabled, 
            early_reveal_enabled, q_list, q_index],
            outputs=[time_left, timer_display, feedback,
                    submit_btn, next_btn, restart_btn,
                    timer_running, last_update]
            )

    # ─── CALLBACKS ──────────────────────────────────────────────────

    # Theme buttons → Theme Menu
    friends_btn.click(
        fn=lambda: ("Friends", gr.update(visible=False), gr.update(visible=True), gr.update(value="## Friends Trivia"), gr.update(visible=True), gr.update(visible=True)),  
        outputs=[selected_theme, theme_page, theme_menu, theme_heading, back_to_themes, shop_btn]
    )
    naruto_btn.click(
        fn=lambda: ("Naruto", gr.update(visible=False), gr.update(visible=True), gr.update(value="## Naruto Trivia"), gr.update(visible=True), gr.update(visible=True)),
        outputs=[selected_theme, theme_page, theme_menu, theme_heading, back_to_themes, shop_btn]
    )
    avengers_btn.click(
        fn=lambda: ("Avengers", gr.update(visible=False), gr.update(visible=True), gr.update(value="## Avengers Trivia"), gr.update(visible=True), gr.update(visible=True)),
        outputs=[selected_theme, theme_page, theme_menu, theme_heading, back_to_themes, shop_btn]
    )
    theme4_btn.click(
        fn=lambda: ("The Office", gr.update(visible=False), gr.update(visible=True), gr.update(value="## The Office"), gr.update(visible=True), gr.update(visible=True)),
        outputs=[selected_theme, theme_page, theme_menu, theme_heading, back_to_themes, shop_btn]
    )
    theme5_btn.click(
        fn=lambda: ("The Big Bang Theory", gr.update(visible=False), gr.update(visible=True), gr.update(value="## The Big Bang Theory"), gr.update(visible=True), gr.update(visible=True)),
        outputs=[selected_theme, theme_page, theme_menu, theme_heading, back_to_themes, shop_btn]
    )

    # Back from Theme Menu → Theme Selection
    back_to_themes.click(
        fn=lambda: (
            gr.update(visible=False),  # hide theme_menu (and its nav buttons)
            gr.update(visible=True)    # show theme_page again
        ),
        outputs=[theme_menu, theme_page]
    )
    # Back from Nickname/PIN → Theme Menu
    back_to_menu.click(
        fn=lambda: (
            gr.update(visible=False),  # hide user_entry
            gr.update(visible=True)    # show theme_menu
        ),
        outputs=[user_entry, theme_menu]
    )

   # Trivia Gauntlet → rich placeholder
    gauntlet_btn.click(
        fn=lambda: (
            gr.update(visible=False),
            gr.update(
                value="""### ⚔️ Trivia Gauntlet (Coming Soon!)
    
    This mode will contain even more questions, extra lifelines, and more fun challenges!
    
    Help keep TriWizard Trivia running:
    
    ☕ **Buy me a Drink on [Ko-fi](https://ko-fi.com/triviaking)**\n\n
    """,
                visible=True
            ),
            gr.update(visible=True)
        ),
        outputs=[game_type_page, placeholder_md, placeholder_page]
    )
    
    # Versus Mode → rich placeholder
    versus_btn.click(
        fn=lambda: (
            gr.update(visible=False),
            gr.update(
                value="""### 🤝 Versus Mode (Coming Soon!)
    
    In Versus Mode, you’ll battle head-to-head with other players locally for ultimate bragging rights
    
    Help keep TriWizard Trivia running!

    ☕ **Buy me a Drink on [Ko-fi](https://ko-fi.com/triviaking)**\n\n
    """,
                visible=True
            ),
            gr.update(visible=True)
        ),
        outputs=[game_type_page, placeholder_md, placeholder_page]
    )
    
    # Back from Placeholder → Game-Type Selection
    back_from_ph.click(
        fn=lambda: (
            gr.update(visible=False),  # placeholder_page
            gr.update(visible=False),  # placeholder_md
            gr.update(visible=True)    # game_type_page
        ),
        outputs=[placeholder_page, placeholder_md, game_type_page]
    )

    def validate_and_proceed(nick, pin):
        if not nick or not pin:
            return (
                "", "",
                gr.update(value="❌ Nickname & PIN required", visible=True),
                gr.update(visible=True),   # show user_entry
                gr.update(visible=False)   # hide mode_page
            )
        return (
            nick, pin,
            gr.update(value="", visible=False),  # clear error
            gr.update(visible=False),            # hide user_entry
            gr.update(visible=True)              # show mode_page
        )
        
    # 1) Play Quiz → show Game-Type options
    start_quiz_btn.click(
        fn=lambda: (
            gr.update(visible=False),  # hide the theme_menu
            gr.update(visible=True)    # show game_type_page
        ),
        outputs=[theme_menu, game_type_page]
    )
    
    # 2) Story Mode → show Nickname & PIN entry
    story_btn.click(
        fn=lambda: (
            gr.update(visible=False),  # hide the game_type_page
            gr.update(visible=True)    # show user_entry
        ),
        outputs=[game_type_page, user_entry]
    )


    # Validate Nickname/PIN → Difficulty
    entry_btn.click(
        fn=validate_and_proceed,
        inputs=[nick_in, pin_in],
        outputs=[nickname_state, pin_state, entry_err, user_entry, mode_page]
    )

    names = {
    "early":     "Early-Reveal",
    "unlimited": "Unlimited Lifelines",
    "disable":   "Disable Timer"
    }
    
    def redeem_code(code):
        code = code.strip().upper()
        vouchers = load_vouchers()
    
        # 1) Does it exist?
        if code not in vouchers:
            return (
                gr.update(value="❌ Invalid code.", visible=True),
                False, False, False, ""
            )
    
        v = vouchers[code]
        # 2) Has it already been used?
        if v.get("consumed", False):
            return (
                gr.update(value="❌ Code already used.", visible=True),
                False, False, False, ""
            )
    
        # 3) Mark it consumed immediately so it can never be redeemed again
        v["consumed"] = True
        save_vouchers(vouchers)
    
        # 4) Flip the right lifeline-flags for this run
        early = (v["type"] == "early")
        unlim = (v["type"] == "unlimited")
        disab = (v["type"] == "disable")
    
        # look up your friendly label
        nice = names.get(v["type"], v["type"].capitalize())
    
        return (
            gr.update(value=f"✅ {nice} unlocked!", visible=True),
            early, unlim, disab, code
        )
            
    # Skip → Difficulty Modes
    skip_btn.click(
        fn=lambda: (
            gr.update(value="", visible=False),  # clear entry_err
            gr.update(visible=False),            # hide user_entry
            gr.update(visible=True)              # show mode_page
        ),
        outputs=[entry_err, user_entry, mode_page]
    )

    redeem_btn.click(
    fn=redeem_code,
    inputs=[code_input],
    outputs=[
        redeem_status,
        early_reveal_enabled,
        unlimited_lifelines_enabled,
        disable_timer_enabled,
        voucher_code_state
        ]
    )

    # Difficulty → Quiz Start
    easy_btn.click(
        fn=lambda theme: get_randomized_run(
            difficulties=["easy","medium"],
            theme=theme
        ),
        inputs=[selected_theme],
        outputs=[q_list]
    ).then(
        fn=initialize_with_list,
        inputs=[
            q_list,
            early_reveal_enabled,
            unlimited_lifelines_enabled,
            disable_timer_enabled
        ],
        outputs=[
            # core quiz UI
            question_text, answer_radio, next_btn, restart_btn,
            score_display, difficulty_state, feedback,
            timer_display, time_left, answered,
            submit_btn, timer_running, debug_info,
            # game state
            score, streak_score, streak_active, fifty_used, call_used,
            q_list, q_index,
            fifty_btn, call_btn, friend_hint,
            # page toggles
            mode_page, quiz_block,
            # carry the shop flags through so they stay “on”
            early_reveal_enabled, unlimited_lifelines_enabled, disable_timer_enabled
        ]
    )
    
    
    # ─── Hard Mode → initialize quiz run ─────────────────────────────────
    hard_btn.click(
        fn=lambda theme: get_randomized_run(
            difficulties=["hard","expert"],
            theme=theme
        ),
        inputs=[selected_theme],
        outputs=[q_list]
    ).then(
        fn=initialize_with_list,
        inputs=[
            q_list,
            early_reveal_enabled,
            unlimited_lifelines_enabled,
            disable_timer_enabled
        ],
        outputs=[
            question_text, answer_radio, next_btn, restart_btn,
            score_display, difficulty_state, feedback,
            timer_display, time_left, answered,
            submit_btn, timer_running, debug_info,
            score, streak_score, streak_active, fifty_used, call_used,
            q_list, q_index,
            fifty_btn, call_btn, friend_hint,
            mode_page, quiz_block,
            early_reveal_enabled, unlimited_lifelines_enabled, disable_timer_enabled
        ]
    )
    
    
    # ─── Mixed Mode → initialize quiz run ────────────────────────────────
    mixed_btn.click(
        fn=lambda theme: get_randomized_run(
            theme=theme,
        ),
        inputs=[selected_theme],
        outputs=[q_list]
    ).then(
        fn=initialize_with_list,
        inputs=[
            q_list,
            early_reveal_enabled,
            unlimited_lifelines_enabled,
            disable_timer_enabled
        ],
        outputs=[
            question_text, answer_radio, next_btn, restart_btn,
            score_display, difficulty_state, feedback,
            timer_display, time_left, answered,
            submit_btn, timer_running, debug_info,
            score, streak_score, streak_active, fifty_used, call_used,
            q_list, q_index,
            fifty_btn, call_btn, friend_hint,
            mode_page, quiz_block,
            early_reveal_enabled, unlimited_lifelines_enabled, disable_timer_enabled
        ]
    )

    # Quiz interactions
    submit_btn.click(
        fn=check_answer,
        inputs=[answer_radio, q_index, q_list, score,
                answered, streak_score, streak_active,
                fifty_used, call_used, unlimited_lifelines_enabled],
        outputs=[
            answer_radio, feedback, next_btn, restart_btn,
            score, answered, timer_running,
            streak_score, streak_active, fifty_used, call_used,
            submit_btn, fifty_btn, call_btn, debug_info
        ]
    )

    # 50:50 Lifeline
    fifty_btn.click(
        fn=use_fifty,
        inputs=[q_list, q_index, streak_active, call_used, unlimited_lifelines_enabled, voucher_code_state],
        outputs=[
            answer_radio, fifty_btn,
            streak_active, fifty_used, call_used,
            feedback, debug_info
        ]
    )

    # Call-a-Wizard
    call_btn.click(
        fn=lambda: gr.update(value="📞 Calling friend...", visible=True),
        outputs=[friend_hint]
    ).then(
        fn=call_friend,
        inputs=[q_list, q_index, fifty_used, call_used, unlimited_lifelines_enabled, voucher_code_state, selected_theme],
        outputs=[friend_hint, call_btn, call_used]
    )

    # Next Question
    next_btn.click(
        fn=next_question,
        inputs=[q_list, q_index, score,
                streak_score, streak_active,
                fifty_used, call_used, unlimited_lifelines_enabled, voucher_code_state],
        outputs=[
            question_text, answer_radio, next_btn, restart_btn,
            score_display, difficulty_state, feedback,
            timer_display, time_left, answered,
            submit_btn, timer_running, debug_info,
            q_index, fifty_btn, call_btn, call_used, friend_hint
        ]
    )

    # Play Again (save leaderboard)
    restart_btn.click(
        fn=save_leaderboard_if_no_voucher,
        inputs=[selected_theme, nickname_state, pin_state, score, voucher_code_state],
        outputs=[]
    ).then(
        fn=lambda: (gr.update(visible=False), gr.update(visible=True), False, False, False, "", gr.update(visible=True)),
        outputs=[quiz_block, mode_page, early_reveal_enabled, unlimited_lifelines_enabled,
        disable_timer_enabled, voucher_code_state, timer_display]
    )
    
    shop_btn.click(
        fn=lambda: (
            gr.update(visible=False),  # hide theme_menu
            gr.update(visible=True),   # show shop_page
            gr.update(visible=True)    # show back_to_themes
        ),
        outputs=[theme_menu, shop_page, back_to_themes])
    shop_back.click(fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
                       outputs=[shop_page, theme_menu])

    # Feedback nav
    feedback_btn.click(fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
                       outputs=[theme_menu, feedback_page])
    fb_submit.click(fn=save_feedback, inputs=[fb_input], outputs=[fb_status, fb_input])
    fb_back.click(fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
                  outputs=[feedback_page, theme_menu])

    # Leaderboard nav
    leaderboard_btn.click(
        fn=lambda theme: get_leaderboard(theme),
        inputs=[selected_theme],
        outputs=[lb_md]    # this writes the MD into lb_md
    ).then(
        fn=lambda: (
            gr.update(visible=False),  # hide theme_menu
            gr.update(visible=False),  # hide feedback_page
            gr.update(visible=False),  # hide support_page
            gr.update(visible=False),  # hide shop_page
            gr.update(visible=True),   # show leaderboard_page container
            gr.update(visible=True)    # show lb_md itself
        ),
        outputs=[
            theme_menu,     # we want to hide the theme menu
            feedback_page,  # hide feedback if it was visible
            support_page,   # hide support if it was visible
            shop_page,      # hide shop if it was visible
            leaderboard_page,  # make the leaderboard page container visible
            lb_md           # make the Markdown box visible
        ]
    )

    lb_back.click(fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
                  outputs=[leaderboard_page, theme_menu])

    # Support nav
    support_btn.click(fn=lambda : (gr.update(visible=False), gr.update(visible=True)),
                      outputs=[theme_menu, support_page])
    support_back.click(fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
                       outputs=[support_page, theme_menu])

    

    demo.launch(server_name="0.0.0.0", server_port=8080, pwa=True)
