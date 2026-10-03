"""Load ingredient chips and recipe skeletons, and check the tags are honest."""

import json
from pathlib import Path

from app.scoring import DIET_RANK

DATA_DIR = Path(__file__).resolve().parent / "data"

KIND_DIET = {
    "vegan": "vegan",
    "dairy": "vegetarian",
    "egg": "eggetarian",
    "meat": "omnivore",
    "shellfish": "omnivore",
}


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def expected_diet(ingredient_ids, ingredients):
    best = "vegan"
    for ingredient_id in ingredient_ids:
        diet = KIND_DIET[ingredients[ingredient_id]["kind"]]
        if DIET_RANK[diet] > DIET_RANK[best]:
            best = diet
    return best


def expected_allergens(ingredient_ids, ingredients):
    found = set()
    for ingredient_id in ingredient_ids:
        found.update(ingredients[ingredient_id]["allergens"])
    return sorted(found)


def expected_hates(recipe, ingredients):
    hates = set()
    for ingredient_id in recipe["ingredients"]:
        hates.update(ingredients[ingredient_id]["hates"])
    if recipe.get("spicy"):
        hates.add("spicy")
    return sorted(hates)


def _prepare():
    raw_ingredients = _load("ingredients.json")
    ingredients = {item["id"]: item for item in raw_ingredients}
    if len(ingredients) != len(raw_ingredients):
        raise ValueError("duplicate ingredient id")

    recipes = []
    seen = set()
    for recipe in _load("recipes.json"):
        recipe_id = recipe["id"]
        if recipe_id in seen:
            raise ValueError(f"duplicate recipe id: {recipe_id}")
        seen.add(recipe_id)
        if recipe["minutes"] not in (15, 30):
            raise ValueError(f"{recipe_id} has a bad time")
        if recipe["skill"] not in ("boil", "follow", "improvise"):
            raise ValueError(f"{recipe_id} has a bad skill")
        if len(recipe["steps"]) != 4 or any(not step.strip() for step in recipe["steps"]):
            raise ValueError(f"{recipe_id} needs four steps")
        if not recipe["title"].strip() or not recipe["why"].strip():
            raise ValueError(f"{recipe_id} needs a title and why")
        unknown = [item for item in recipe["ingredients"] if item not in ingredients]
        if unknown or len(set(recipe["ingredients"])) != len(recipe["ingredients"]):
            raise ValueError(f"{recipe_id} has bad ingredients: {unknown}")
        diet = expected_diet(recipe["ingredients"], ingredients)
        if recipe["diet"] != diet:
            raise ValueError(f"{recipe_id} diet is {recipe['diet']}, expected {diet}")
        prepared = dict(recipe)
        prepared["allergens"] = expected_allergens(recipe["ingredients"], ingredients)
        prepared["hates"] = expected_hates(recipe, ingredients)
        prepared["spicy"] = bool(recipe.get("spicy"))
        recipes.append(prepared)

    if not 28 <= len(recipes) <= 40:
        raise ValueError(f"expected about 30 recipes, found {len(recipes)}")
    return raw_ingredients, ingredients, recipes


INGREDIENTS_LIST, INGREDIENTS, RECIPES = _prepare()
