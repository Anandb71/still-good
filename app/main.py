"""Still Good API. Code chooses the recipe. Gemma only writes the note."""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.catalog import INGREDIENTS, INGREDIENTS_LIST, RECIPES
from app.notes import (
    allow_terms,
    blocked_terms,
    resolve_gemma_note,
    vocabulary_from,
)
from app.ollama_client import TIMEOUT_SECONDS, generate, model_label, settings
from app.scoring import rank_recipes

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
VOCABULARY = vocabulary_from(INGREDIENTS)

app = FastAPI(title="Still Good")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ProfileIn(BaseModel):
    diet: str
    allergies: list[str] = Field(default_factory=list)
    wont_eat: list[str] = Field(default_factory=list)
    minutes: int
    skill: str
    name: str = ""


class GenerateIn(BaseModel):
    profile: ProfileIn
    selected: list[str]
    use_soon: list[str] = Field(default_factory=list)
    skip: list[str] = Field(default_factory=list)


DIETS = {"vegan", "vegetarian", "eggetarian", "omnivore", "everything"}
SKILLS = {"boil", "follow", "improvise"}
ALLERGIES = {"nuts", "dairy", "gluten", "egg", "soy", "shellfish"}
HATES = {"cilantro", "mushroom", "onion", "spicy"}


def _unique(items):
    seen = set()
    ordered = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _check_profile(profile: ProfileIn):
    if profile.diet not in DIETS:
        raise HTTPException(status_code=400, detail="Unknown diet.")
    if profile.skill not in SKILLS:
        raise HTTPException(status_code=400, detail="Unknown skill.")
    if profile.minutes not in (15, 30):
        raise HTTPException(status_code=400, detail="Tonight is 15 or 30 minutes.")
    unknown_allergies = [item for item in profile.allergies if item not in ALLERGIES]
    if unknown_allergies:
        raise HTTPException(status_code=400, detail="Unknown allergy.")
    unknown_hates = [item for item in profile.wont_eat if item not in HATES]
    if unknown_hates:
        raise HTTPException(status_code=400, detail="Unknown won't-eat tag.")


def _check_ids(ids):
    unknown = [item for item in ids if item not in INGREDIENTS]
    if unknown:
        raise HTTPException(status_code=400, detail="Unknown ingredient.")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    _, model = settings()
    return {"ok": True, "model": model}


@app.get("/api/catalog")
def catalog():
    chips = []
    for item in INGREDIENTS_LIST:
        chips.append(
            {
                "id": item["id"],
                "label": item["label"],
                "group": item["group"],
            }
        )
    return {"ingredients": chips}


@app.post("/api/generate")
def generate_note(body: GenerateIn):
    _check_profile(body.profile)
    selected = _unique(body.selected)
    _check_ids(selected)
    _check_ids(body.use_soon)
    profile = {
        "diet": body.profile.diet,
        "allergies": _unique(body.profile.allergies),
        "wont_eat": _unique(body.profile.wont_eat),
        "minutes": body.profile.minutes,
        "skill": body.profile.skill,
    }
    ranked = rank_recipes(RECIPES, profile, selected, body.use_soon, body.skip)
    if not ranked:
        return {
            "ok": False,
            "message": "Nothing in the fridge fits those rules tonight. Add a staple you have, or give yourself 30 minutes.",
        }

    recipe = ranked[0]
    allow = allow_terms(recipe, INGREDIENTS)
    blocked = blocked_terms(profile["allergies"])
    note, elapsed_ms = resolve_gemma_note(
        generate,
        recipe,
        INGREDIENTS,
        allow,
        blocked,
        VOCABULARY,
        body.use_soon,
        TIMEOUT_SECONDS,
    )
    _, model = settings()

    return {
        "ok": True,
        "source": note["source"],
        "message": note["message"],
        "model": model,
        "model_label": model_label(model),
        "generation_ms": elapsed_ms,
        "title": note["title"],
        "why": note["why"],
        "steps": note["steps"],
        "recipe_id": recipe["id"],
        "minutes": recipe["minutes"],
        "ingredients": [
            {"id": ingredient_id, "label": INGREDIENTS[ingredient_id]["label"]}
            for ingredient_id in recipe["ingredients"]
        ],
        "remaining": len(ranked) - 1,
    }


def main():
    import uvicorn

    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
