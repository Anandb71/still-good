"""Deterministic recipe filtering and ranking. The model never picks the meal."""

DIET_RANK = {"vegan": 0, "vegetarian": 1, "eggetarian": 2, "omnivore": 3}
SKILL_RANK = {"boil": 0, "follow": 1, "improvise": 2}


def canonical_diet(diet):
    if diet == "everything":
        return "omnivore"
    return diet


def rank_recipes(recipes, profile, selected, use_soon, skip=()):
    """Return matching recipes, best first.

    Hard stops: diet, allergens, hates, time, skill, and ingredient subset.
    Score: more starred ingredients, then fewer extras, then shorter time, then id.
    """
    selected_ids = list(dict.fromkeys(selected or []))
    selected_set = set(selected_ids)
    soon = set(use_soon or []) & selected_set
    skipped = set(skip or [])
    user_diet = canonical_diet(profile["diet"])
    allergies = set(profile.get("allergies") or [])
    hates = set(profile.get("wont_eat") or [])
    minutes = int(profile["minutes"])
    skill = profile["skill"]

    ranked = []
    for recipe in recipes:
        if recipe["id"] in skipped:
            continue
        if recipe["minutes"] > minutes:
            continue
        if SKILL_RANK[recipe["skill"]] > SKILL_RANK[skill]:
            continue
        if DIET_RANK[recipe["diet"]] > DIET_RANK[user_diet]:
            continue
        if allergies & set(recipe["allergens"]):
            continue
        if hates & set(recipe["hates"]):
            continue
        ingredients = set(recipe["ingredients"])
        if not ingredients <= selected_set:
            continue
        hits = len(ingredients & soon)
        extras = len(ingredients - soon)
        ranked.append((-hits, extras, recipe["minutes"], recipe["id"], recipe))

    ranked.sort(key=lambda row: row[:4])
    return [row[4] for row in ranked]
