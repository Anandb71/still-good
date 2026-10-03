"""Parser and allow-list. No Ollama."""

from app.catalog import INGREDIENTS, RECIPES
from app.notes import (
    MUMBLED,
    allow_terms,
    blocked_terms,
    build_prompt,
    choose_note,
    find_foods,
    note_is_ready,
    parse_note_text,
    required_starred,
    resolve_gemma_note,
    text_is_allowed,
    vocabulary_from,
)

VOCAB = vocabulary_from(INGREDIENTS)
RECIPE = {
    "id": "sample",
    "title": "Spinach rice",
    "why": "Spinach on rice.",
    "steps": ["Rinse the spinach.", "Warm the rice.", "Add salt.", "Eat the rice."],
    "ingredients": ["spinach", "rice"],
}
ALLOW = allow_terms(RECIPE, INGREDIENTS)


def note(body):
    return (
        "TITLE: Spinach rice\n"
        "WHY: Spinach on warm rice.\n"
        + body
    )


def test_parse_six_lines_and_ignore_extra_prose():
    parsed = parse_note_text(
        "Here you go.\n"
        "TITLE: Lemon rice\n"
        "WHY: Bright and fast.\n"
        "STEP: Warm the rice.\n"
        "step 2: Add the lemon.\n"
        "3. STEP: Taste the salt.\n"
        "- STEP: Eat the rice.\n"
        "Enjoy."
    )
    assert parsed["title"] == "Lemon rice"
    assert parsed["why"] == "Bright and fast."
    assert parsed["steps"] == [
        "Warm the rice.",
        "Add the lemon.",
        "Taste the salt.",
        "Eat the rice.",
    ]


def test_markdown_bold_still_parses():
    parsed = parse_note_text("**TITLE:** Bowl\n**WHY:** Fast.\n**STEP:** Eat.")
    assert parsed["title"] == "Bowl"
    assert parsed["steps"] == ["Eat."]


def test_minute_is_not_a_nut_and_peanut_is_not_just_nut():
    vocab = ("nut", "peanut", "peanuts")
    assert find_foods("Cook for a minute.", vocab) == []
    assert find_foods("Stir the peanuts.", vocab) == ["peanuts"]
    assert "nut" not in find_foods("Stir the peanuts.", vocab)


def test_longest_phrase_wins():
    vocab = ("soy sauce", "soy", "green chili", "chili")
    assert find_foods("Stir in the soy sauce.", vocab) == ["soy sauce"]
    assert find_foods("Add the green chili.", vocab) == ["green chili"]


def test_outside_food_drops_that_step_only():
    raw = note(
        "STEP: Rinse the spinach.\n"
        "STEP: Add the chicken.\n"
        "STEP: Warm the rice.\n"
        "STEP: Add a pinch of salt.\n"
        "STEP: Eat the rice.\n"
    )
    chosen = choose_note(raw, RECIPE, ALLOW, set(), VOCAB)
    assert chosen["source"] == "gemma"
    assert chosen["steps"] == [
        "Rinse the spinach.",
        "Warm the rice.",
        "Add a pinch of salt.",
        "Eat the rice.",
    ]


def test_fewer_than_four_clean_steps_uses_fallback():
    raw = note(
        "STEP: Rinse the spinach.\n"
        "STEP: Add cumin.\n"
        "STEP: Add the chicken.\n"
        "STEP: Warm the rice.\n"
    )
    chosen = choose_note(raw, RECIPE, ALLOW, set(), VOCAB)
    assert chosen["source"] == "fallback"
    assert chosen["message"] == MUMBLED
    assert chosen["steps"] == RECIPE["steps"]
    assert chosen["title"] == RECIPE["title"]


def test_blocked_allergen_drops_step_even_if_named_in_allow_list():
    allow = set(ALLOW)
    allow.update(("peanut", "peanuts"))
    raw = note(
        "STEP: Rinse the spinach.\n"
        "STEP: Stir in the peanuts.\n"
        "STEP: Warm the rice.\n"
        "STEP: Add a pinch of salt.\n"
        "STEP: Eat the rice.\n"
    )
    chosen = choose_note(raw, RECIPE, allow, blocked_terms(["nuts"]), VOCAB)
    assert "peanuts" not in " ".join(chosen["steps"]).lower()
    assert chosen["source"] == "gemma"


def test_title_with_a_forbidden_food_rejects_the_whole_note():
    raw = (
        "TITLE: Chicken rice\n"
        "WHY: Spinach on rice.\n"
        "STEP: Rinse the spinach.\n"
        "STEP: Warm the rice.\n"
        "STEP: Add salt.\n"
        "STEP: Eat the rice.\n"
    )
    chosen = choose_note(raw, RECIPE, ALLOW, set(), VOCAB)
    assert chosen["source"] == "fallback"


def test_short_fragment_is_not_a_finished_step():
    raw = note(
        "STEP: Rinse the spinach.\n"
        "STEP: Warm the rice with a pinch of salt.\n"
        "STEP: Stir the spinach into the rice.\n"
        "STEP: Add\n"
    )
    assert not note_is_ready(raw, ALLOW, set(), VOCAB)
    partial = note(
        "STEP: Rinse the spinach.\n"
        "STEP: Warm the rice with a pinch of salt.\n"
        "STEP: Stir the spinach into the rice.\n"
        "STEP: Eat the rice while it is still"
    )
    assert not note_is_ready(partial, ALLOW, set(), VOCAB)
    assert note_is_ready(partial + " warm.\n", ALLOW, set(), VOCAB)
    finished = note(
        "STEP: Rinse the spinach.\n"
        "STEP: Warm the rice with a pinch of salt.\n"
        "STEP: Stir the spinach into the rice.\n"
        "STEP: Eat the rice.\n"
    )
    assert note_is_ready(finished, ALLOW, set(), VOCAB)


def test_empty_and_garbage_fall_back():
    assert choose_note("", RECIPE, ALLOW, set(), VOCAB)["source"] == "fallback"
    assert choose_note("I like soup.", RECIPE, ALLOW, set(), VOCAB)["source"] == "fallback"


STAR_RECIPE = {
    "id": "sample-star",
    "title": "Spinach yogurt rice",
    "why": "Spinach on rice with yogurt.",
    "steps": [
        "Rinse the spinach.",
        "Warm the rice.",
        "Stir in the yogurt.",
        "Eat the rice.",
    ],
    "ingredients": ["spinach", "yogurt", "rice"],
}
STAR_ALLOW = allow_terms(STAR_RECIPE, INGREDIENTS)
SKIPPED_YOGURT = "Gemma skipped the yogurt; here's the sure version."


def star_note(steps, title="Yogurt rice", why="Spinach on warm rice."):
    lines = [f"TITLE: {title}", f"WHY: {why}"]
    lines.extend(f"STEP: {step}" for step in steps)
    return "\n".join(lines) + "\n"


CLEAN_STEPS = [
    "Rinse the spinach.",
    "Warm the rice with a pinch of salt.",
    "Stir the spinach into the rice.",
    "Eat the rice.",
]


def test_starred_food_in_the_steps_is_accepted():
    raw = star_note(
        [
            "Rinse the spinach.",
            "Warm the rice with a pinch of salt.",
            "Stir in the yogurt.",
            "Eat the rice.",
        ]
    )
    chosen = choose_note(
        raw, STAR_RECIPE, STAR_ALLOW, set(), VOCAB, ["yogurt", "spinach"], INGREDIENTS
    )
    assert chosen["source"] == "gemma"
    assert note_is_ready(
        raw, STAR_ALLOW, set(), VOCAB, ["yogurt", "spinach"], INGREDIENTS
    )


def test_starred_food_only_in_the_title_is_rejected():
    raw = star_note(CLEAN_STEPS, title="Quick spinach and yogurt rice")
    chosen = choose_note(
        raw, STAR_RECIPE, STAR_ALLOW, set(), VOCAB, ["yogurt"], INGREDIENTS
    )
    assert chosen["source"] == "fallback"
    assert chosen["message"] == SKIPPED_YOGURT
    assert chosen["title"] == STAR_RECIPE["title"]
    assert chosen["steps"] == STAR_RECIPE["steps"]
    assert not note_is_ready(raw, STAR_ALLOW, set(), VOCAB, ["yogurt"], INGREDIENTS)


def test_aliases_count_as_the_starred_food():
    for step in (
        "Stir in the curd.",
        "Stir in the dahi.",
        "Stir in the Yogurt.",
    ):
        raw = star_note(
            [
                "Rinse the palak.",
                "Warm the rice with a pinch of salt.",
                step,
                "Eat the rice.",
            ]
        )
        chosen = choose_note(
            raw,
            STAR_RECIPE,
            STAR_ALLOW,
            set(),
            VOCAB,
            ["yogurt", "spinach"],
            INGREDIENTS,
        )
        assert chosen["source"] == "gemma", step
    missed = star_note(
        [
            "Rinse the spinach.",
            "Warm the rice with a pinch of salt.",
            "Do not curdle the sauce of rice.",
            "Eat the rice.",
        ]
    )
    assert (
        choose_note(
            missed, STAR_RECIPE, STAR_ALLOW, set(), VOCAB, ["yogurt"], INGREDIENTS
        )["source"]
        == "fallback"
    )


def test_star_outside_the_skeleton_is_ignored():
    assert required_starred(STAR_RECIPE, ["lemon", "yogurt", "lemon"]) == ["yogurt"]
    raw = star_note(
        [
            "Rinse the spinach.",
            "Warm the rice with a pinch of salt.",
            "Stir in the yogurt.",
            "Eat the rice.",
        ]
    )
    required = required_starred(STAR_RECIPE, ["lemon", "yogurt"])
    chosen = choose_note(
        raw, STAR_RECIPE, STAR_ALLOW, set(), VOCAB, required, INGREDIENTS
    )
    assert chosen["source"] == "gemma"
    assert "lemon" not in " ".join(chosen["steps"]).lower()


def test_prompt_names_the_starred_foods_for_the_steps():
    prompt = build_prompt(STAR_RECIPE, STAR_ALLOW, ["yogurt", "spinach"])
    lowered = prompt.lower()
    assert "must mention yogurt and spinach" in lowered
    assert "step" in lowered


def test_retry_then_fallback_when_steps_keep_skipping_the_star():
    missing = star_note(CLEAN_STEPS, title="Yogurt rice with spinach")
    prompts = []
    timeouts = []

    def fake(prompt, stop_when=None, timeout_seconds=None):
        prompts.append(prompt)
        timeouts.append(timeout_seconds)
        assert stop_when(missing) is False
        return missing, 20, None

    note, elapsed = resolve_gemma_note(
        fake,
        STAR_RECIPE,
        INGREDIENTS,
        STAR_ALLOW,
        set(),
        VOCAB,
        ["spinach", "yogurt", "lemon"],
        300,
    )
    assert len(prompts) == 2
    assert all("yogurt" in prompt.lower() for prompt in prompts)
    assert timeouts[0] <= 300
    assert timeouts[1] <= timeouts[0]
    assert elapsed == 40
    assert note["source"] == "fallback"
    assert note["message"] == SKIPPED_YOGURT
    assert note["steps"] == STAR_RECIPE["steps"]


def test_retry_keeps_the_second_reply_when_it_uses_the_star():
    missing = star_note(CLEAN_STEPS, title="Yogurt rice")
    fixed = star_note(
        [
            "Rinse the spinach.",
            "Warm the rice with a pinch of salt.",
            "Stir in the yogurt.",
            "Eat the rice.",
        ]
    )
    replies = [missing, fixed]

    def fake(prompt, stop_when=None, timeout_seconds=None):
        text = replies.pop(0)
        return text, 15, None

    note, elapsed = resolve_gemma_note(
        fake,
        STAR_RECIPE,
        INGREDIENTS,
        STAR_ALLOW,
        set(),
        VOCAB,
        ["yogurt"],
        300,
    )
    assert note["source"] == "gemma"
    assert any("yogurt" in step.lower() for step in note["steps"])
    assert elapsed == 30
    assert replies == []


def test_no_second_call_when_the_budget_is_already_spent():
    missing = star_note(CLEAN_STEPS, title="Yogurt rice")
    calls = []

    def fake(prompt, stop_when=None, timeout_seconds=None):
        calls.append(timeout_seconds)
        return missing, 300_000, None

    note, elapsed = resolve_gemma_note(
        fake,
        STAR_RECIPE,
        INGREDIENTS,
        STAR_ALLOW,
        set(),
        VOCAB,
        ["yogurt"],
        300,
    )
    assert calls == [300] or (len(calls) == 1 and calls[0] <= 300)
    assert elapsed == 300_000
    assert note["source"] == "fallback"
    assert note["message"] == SKIPPED_YOGURT


def test_shipped_fallback_notes_stay_inside_their_allow_lists():
    for recipe in RECIPES:
        allow = allow_terms(recipe, INGREDIENTS)
        assert text_is_allowed(recipe["title"], allow, set(), VOCAB), recipe["id"]
        assert text_is_allowed(recipe["why"], allow, set(), VOCAB), recipe["why"]
        for step in recipe["steps"]:
            assert text_is_allowed(step, allow, set(), VOCAB), (recipe["id"], step)
