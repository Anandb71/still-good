"""Filtering and ranking. No network, no model."""

from app.catalog import INGREDIENTS, RECIPES
from app.scoring import rank_recipes


def recipe(**overrides):
    base = {
        "id": "sample",
        "minutes": 15,
        "skill": "follow",
        "diet": "vegan",
        "allergens": [],
        "hates": [],
        "ingredients": ["rice"],
    }
    base.update(overrides)
    return base


def profile(**overrides):
    base = {
        "diet": "everything",
        "allergies": [],
        "wont_eat": [],
        "minutes": 30,
        "skill": "improvise",
    }
    base.update(overrides)
    return base


def test_nut_allergy_drops_peanut_dish():
    dishes = [
        recipe(id="peanut", allergens=["nuts"], ingredients=["peanuts", "rice"]),
        recipe(id="plain", ingredients=["rice"]),
    ]
    ranked = rank_recipes(dishes, profile(allergies=["nuts"]), ["peanuts", "rice"], [])
    assert [item["id"] for item in ranked] == ["plain"]


def test_diet_ladder():
    dishes = [
        recipe(id="vegan", diet="vegan"),
        recipe(id="veg", diet="vegetarian", allergens=["dairy"]),
        recipe(id="egg", diet="eggetarian", allergens=["egg"]),
        recipe(id="meat", diet="omnivore"),
    ]
    selected = ["rice"]
    assert [item["id"] for item in rank_recipes(dishes, profile(diet="vegan"), selected, [])] == ["vegan"]
    assert [item["id"] for item in rank_recipes(dishes, profile(diet="vegetarian"), selected, [])] == ["veg", "vegan"]
    assert [item["id"] for item in rank_recipes(dishes, profile(diet="eggetarian"), selected, [])] == ["egg", "veg", "vegan"]
    assert [item["id"] for item in rank_recipes(dishes, profile(diet="everything"), selected, [])] == ["egg", "meat", "veg", "vegan"]


def test_time_and_skill_are_ceilings():
    dishes = [
        recipe(id="quick", minutes=15, skill="boil"),
        recipe(id="half", minutes=30, skill="follow"),
        recipe(id="free", minutes=30, skill="improvise"),
    ]
    selected = ["rice"]
    only_quick = rank_recipes(dishes, profile(minutes=15, skill="boil"), selected, [])
    assert [item["id"] for item in only_quick] == ["quick"]
    follow = rank_recipes(dishes, profile(minutes=30, skill="follow"), selected, [])
    assert [item["id"] for item in follow] == ["quick", "half"]


def test_hates_and_missing_ingredients():
    dishes = [
        recipe(id="onion", hates=["onion"], ingredients=["onion", "rice"]),
        recipe(id="hot", hates=["spicy"], ingredients=["rice"]),
        recipe(id="plain", ingredients=["rice"]),
    ]
    ranked = rank_recipes(
        dishes,
        profile(wont_eat=["onion", "spicy"]),
        ["rice", "onion"],
        [],
    )
    assert [item["id"] for item in ranked] == ["plain"]


def test_use_soon_then_fewer_extras_then_id():
    dishes = [
        recipe(id="both", ingredients=["spinach", "yogurt", "rice"]),
        recipe(id="one-extra", ingredients=["yogurt", "rice", "garlic"]),
        recipe(id="one-tight", ingredients=["yogurt"]),
        recipe(id="none", ingredients=["rice"]),
    ]
    ranked = rank_recipes(
        dishes,
        profile(),
        ["spinach", "yogurt", "rice", "garlic"],
        ["spinach", "yogurt"],
    )
    assert [item["id"] for item in ranked] == ["both", "one-tight", "one-extra", "none"]


def test_skip_returns_the_next_match_and_order_is_stable():
    dishes = [
        recipe(id="b", ingredients=["rice"]),
        recipe(id="a", ingredients=["rice"]),
    ]
    first = rank_recipes(dishes, profile(), ["rice"], [])
    again = rank_recipes(dishes, profile(), ["rice"], [])
    assert [item["id"] for item in first] == ["a", "b"]
    assert [item["id"] for item in again] == ["a", "b"]
    nxt = rank_recipes(dishes, profile(), ["rice"], [], skip=["a"])
    assert [item["id"] for item in nxt] == ["b"]


def test_unselected_star_does_not_count():
    dishes = [recipe(id="rice", ingredients=["rice"])]
    ranked = rank_recipes(dishes, profile(), ["rice"], ["paneer"])
    assert ranked[0]["id"] == "rice"


def test_empty_fridge_matches_nothing():
    assert rank_recipes(RECIPES, profile(), [], []) == []


def test_demo_profile_puts_starred_spinach_yogurt_first():
    ranked = rank_recipes(
        RECIPES,
        profile(diet="vegetarian", allergies=["nuts"], minutes=15, skill="follow"),
        ["spinach", "yogurt", "rice", "garlic", "oil", "tomato", "lemon"],
        ["spinach", "yogurt"],
    )
    assert ranked[0]["id"] == "spinach-yogurt-rice"
    assert "spinach" in ranked[0]["ingredients"]
    assert "yogurt" in ranked[0]["ingredients"]
    assert "nuts" not in ranked[0]["allergens"]


def test_catalog_tags_cover_the_board():
    assert 30 <= len(RECIPES) <= 40
    used = {ingredient for recipe in RECIPES for ingredient in recipe["ingredients"]}
    assert used == set(INGREDIENTS)
    diets = {recipe["diet"] for recipe in RECIPES}
    skills = {recipe["skill"] for recipe in RECIPES}
    assert diets == {"vegan", "vegetarian", "eggetarian", "omnivore"}
    assert skills == {"boil", "follow", "improvise"}
    assert any(recipe["spicy"] for recipe in RECIPES)
    assert any("nuts" in recipe["allergens"] for recipe in RECIPES)
    assert any("shellfish" in recipe["allergens"] for recipe in RECIPES)
    assert any("cilantro" in recipe["hates"] for recipe in RECIPES)
    assert any("mushroom" in recipe["hates"] for recipe in RECIPES)
    assert any("onion" in recipe["hates"] for recipe in RECIPES)
