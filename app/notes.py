"""Parse a Gemma note and keep only lines that stay inside the allow-list."""

import re
import time

MUMBLED = "Gemma mumbled; here's the sure version."
SILENT = "Gemma didn't answer; here's the sure version."

# Foods the model might invent. Ingredient aliases are added on top of this.
EXTRA_FOODS = (
    "salt",
    "water",
    "sugar",
    "honey",
    "flour",
    "wheat",
    "atta",
    "maida",
    "ghee",
    "cream",
    "almond",
    "almonds",
    "cashew",
    "cashews",
    "walnut",
    "walnuts",
    "pistachio",
    "pistachios",
    "hazelnut",
    "hazelnuts",
    "nut",
    "nuts",
    "peanut butter",
    "mutton",
    "beef",
    "pork",
    "crab",
    "lobster",
    "shellfish",
    "coconut",
    "corn",
    "apple",
    "mango",
    "sesame",
    "vinegar",
    "mustard",
    "basil",
    "mint",
    "cumin",
    "turmeric",
    "paprika",
)

ALLERGEN_TERMS = {
    "nuts": (
        "peanut",
        "peanuts",
        "almond",
        "almonds",
        "cashew",
        "cashews",
        "walnut",
        "walnuts",
        "pistachio",
        "pistachios",
        "hazelnut",
        "hazelnuts",
        "nut",
        "nuts",
        "peanut butter",
    ),
    "dairy": (
        "milk",
        "cheese",
        "paneer",
        "yogurt",
        "yoghurt",
        "butter",
        "ghee",
        "cream",
        "curd",
        "dahi",
    ),
    "gluten": (
        "gluten",
        "wheat",
        "bread",
        "pasta",
        "noodle",
        "noodles",
        "toast",
        "maida",
        "atta",
        "flour",
    ),
    "egg": ("egg", "eggs"),
    "soy": ("soy", "soya", "tofu", "soy sauce"),
    "shellfish": ("shrimp", "prawn", "prawns", "shellfish", "crab", "lobster"),
}

LINE_RE = re.compile(
    r"(?im)^\s*(?:[-*]|\d+[.)])?\s*(TITLE|WHY|STEP)(?:\s*\d+)?\s*:\s*(.+?)\s*$"
)
FENCE_RE = re.compile(r"```(?:\w+)?")
THINK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def allow_terms(recipe, ingredients):
    allow = {"salt", "water"}
    for ingredient_id in recipe["ingredients"]:
        for alias in ingredients[ingredient_id]["aliases"]:
            allow.add(alias.lower())
    return allow


def blocked_terms(allergies):
    blocked = set()
    for allergy in allergies or []:
        blocked.update(ALLERGEN_TERMS.get(allergy, ()))
    return blocked


def vocabulary_from(ingredients):
    terms = set(EXTRA_FOODS)
    terms.update(("salt", "water"))
    for item in ingredients.values():
        for alias in item["aliases"]:
            terms.add(alias.lower())
        for allergy in item.get("allergens", []):
            terms.update(ALLERGEN_TERMS.get(allergy, ()))
    for words in ALLERGEN_TERMS.values():
        terms.update(words)
    return tuple(sorted(terms, key=lambda term: (-len(term), term)))


def find_foods(text, vocabulary):
    """Food phrases in text, longest match first, no overlapping hits."""
    lower = (text or "").lower()
    occupied = [False] * len(lower)
    found = []
    for term in vocabulary:
        start = 0
        length = len(term)
        while True:
            index = lower.find(term, start)
            if index < 0:
                break
            end = index + length
            before_ok = index == 0 or not lower[index - 1].isalnum()
            after_ok = end == len(lower) or not lower[end].isalnum()
            if before_ok and after_ok and not any(occupied[index:end]):
                for pos in range(index, end):
                    occupied[pos] = True
                found.append(term)
            start = index + 1
    return found


def text_is_allowed(text, allow, blocked, vocabulary):
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    for food in find_foods(cleaned, vocabulary):
        if food in blocked or food not in allow:
            return False
    return True


def parse_note_text(raw):
    """Pull the first TITLE, the first WHY, and every STEP. Extra prose is ignored."""
    text = THINK_RE.sub("", raw or "")
    text = FENCE_RE.sub("", text).replace("*", "")
    title = None
    why = None
    steps = []
    for kind, value in LINE_RE.findall(text):
        value = value.strip()
        if not value:
            continue
        label = kind.upper()
        if label == "TITLE" and title is None:
            title = value
        elif label == "WHY" and why is None:
            why = value
        elif label == "STEP":
            steps.append(value)
    return {"title": title, "why": why, "steps": steps}


def fallback_note(recipe, message):
    return {
        "source": "fallback",
        "message": message,
        "title": recipe["title"],
        "why": recipe["why"],
        "steps": list(recipe["steps"]),
    }


def step_is_finished(step):
    """Ignore a stub such as 'Add'. A full line of a sentence is enough."""
    return len((step or "").strip()) >= 12


def required_starred(recipe, use_soon):
    """Starred ids that are actually in this skeleton, in fridge order."""
    in_recipe = set(recipe["ingredients"])
    required = []
    seen = set()
    for item_id in use_soon or []:
        if item_id in in_recipe and item_id not in seen:
            seen.add(item_id)
            required.append(item_id)
    return required


def _terms_for(ingredient):
    terms = {ingredient["id"].lower()}
    for alias in ingredient.get("aliases") or []:
        terms.add(alias.lower())
    return tuple(sorted(terms, key=lambda term: (-len(term), term)))


def item_mentioned(text, ingredient):
    """True when the id or any alias appears as its own word."""
    return bool(find_foods(text, _terms_for(ingredient)))


def missing_starred(steps, required, ingredients):
    if not required:
        return []
    blob = "\n".join(steps)
    missing = []
    for item_id in required:
        if not item_mentioned(blob, ingredients[item_id]):
            missing.append(item_id)
    return missing


def _name_list(names):
    names = list(names)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def skipped_message(missing, ingredients):
    names = [ingredients[item_id]["label"].lower() for item_id in missing]
    return f"Gemma skipped the {_name_list(names)}; here's the sure version."


def clean_steps(steps, allow, blocked, vocabulary):
    kept = []
    for step in steps:
        if text_is_allowed(step, allow, blocked, vocabulary) and step_is_finished(step):
            kept.append(step)
        if len(kept) == 4:
            break
    return kept


def _structured_note(raw, allow, blocked, vocabulary, drop_partial):
    text = raw or ""
    if drop_partial and text and not text.endswith("\n"):
        text = text.rsplit("\n", 1)[0]
    parsed = parse_note_text(text)
    title_ok = text_is_allowed(parsed["title"], allow, blocked, vocabulary)
    why_ok = text_is_allowed(parsed["why"], allow, blocked, vocabulary)
    steps = clean_steps(parsed["steps"], allow, blocked, vocabulary) if title_ok and why_ok else []
    return parsed, title_ok and why_ok and len(steps) == 4, steps


def note_is_ready(raw, allow, blocked, vocabulary, required=(), ingredients=None):
    """True only when four clean steps are in hand and they name every required star.

    A finished fourth step that never mentions a starred skeleton food does not
    end the stream. Title and WHY do not count toward that mention.
    """
    ready, steps = _structured_note(raw, allow, blocked, vocabulary, drop_partial=True)[1:]
    if not ready:
        return False
    return not missing_starred(steps, required, ingredients)


def classify_reply(raw, error, recipe, allow, blocked, vocabulary, required=(), ingredients=None):
    """Return (note, kind). kind is gemma, skipped, mumbled, or silent."""
    parsed, ready, steps = _structured_note(
        raw, allow, blocked, vocabulary, drop_partial=False
    )
    if ready:
        missing = missing_starred(steps, required, ingredients)
        if missing:
            return fallback_note(recipe, skipped_message(missing, ingredients)), "skipped"
        return {
            "source": "gemma",
            "message": None,
            "title": parsed["title"],
            "why": parsed["why"],
            "steps": steps,
        }, "gemma"
    if error:
        return fallback_note(recipe, SILENT), "silent"
    return fallback_note(recipe, MUMBLED), "mumbled"


def choose_note(raw, recipe, allow, blocked, vocabulary, required=(), ingredients=None):
    """Use the model note only when title, why, four steps, and the stars all pass."""
    note, _kind = classify_reply(
        raw, None, recipe, allow, blocked, vocabulary, required, ingredients
    )
    return note


def build_prompt(recipe, allow, must_use=()):
    foods = ", ".join(sorted(allow))
    skeleton = [f"TITLE: {recipe['title']}", f"WHY: {recipe['why']}"]
    skeleton.extend(f"STEP: {step}" for step in recipe["steps"])
    must = ""
    if must_use:
        named = _name_list(must_use)
        must = (
            f"The STEP lines must mention {named}. The title is not enough.\n"
        )
    return (
        "Write a cooking note for one person.\n"
        f"Use ONLY these foods: {foods}.\n"
        "Do not name any other food, spice, or sauce.\n"
        + must
        + "Reply with exactly six lines and no other words:\n"
        "TITLE: short dish name\n"
        "WHY: one short sentence\n"
        "STEP: one short action\n"
        "STEP: one short action\n"
        "STEP: one short action\n"
        "STEP: one short action\n"
        "\n"
        "Rewrite this idea in your own words, using the same foods:\n"
        + "\n".join(skeleton)
        + "\n"
        + must
    )


def resolve_gemma_note(
    generate_fn,
    recipe,
    ingredients,
    allow,
    blocked,
    vocabulary,
    use_soon,
    budget_seconds,
):
    """Ask Gemma, and if the steps skip a starred skeleton food, ask once more.

    Both calls share budget_seconds. The second call is skipped when the first
    already used the budget.
    """
    required = required_starred(recipe, use_soon)
    names = [ingredients[item_id]["id"] for item_id in required]
    prompt = build_prompt(recipe, allow, names)
    started = time.perf_counter()
    spent_ms = 0

    def one_call(prompt_text):
        nonlocal spent_ms
        wall_left = budget_seconds - (time.perf_counter() - started)
        reported_left = budget_seconds - (spent_ms / 1000)
        remaining = min(wall_left, reported_left)
        if remaining <= 0:
            return "", "timed out"
        raw, elapsed_ms, error = generate_fn(
            prompt_text,
            stop_when=lambda text: note_is_ready(
                text, allow, blocked, vocabulary, required, ingredients
            ),
            timeout_seconds=remaining,
        )
        spent_ms += max(0, int(elapsed_ms))
        return raw, error

    raw, error = one_call(prompt)
    note, kind = classify_reply(
        raw, error, recipe, allow, blocked, vocabulary, required, ingredients
    )
    if kind != "skipped":
        return note, spent_ms
    first = note
    raw, error = one_call(prompt)
    note, kind = classify_reply(
        raw, error, recipe, allow, blocked, vocabulary, required, ingredients
    )
    if kind == "gemma" or kind == "skipped":
        return note, spent_ms
    return first, spent_ms
