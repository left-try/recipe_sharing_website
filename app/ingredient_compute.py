"""Scale and convert recipe ingredient amounts (servings, metric, US customary)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

import pint

_ureg = pint.UnitRegistry()
_Q = _ureg.Quantity

# Grams per 1 US cup (236.588 ml) — approximate baking references.
_DENSITY_KEYWORDS: list[tuple[str, float]] = [
    ("bread flour", 127),
    ("cake flour", 114),
    ("all purpose flour", 120),
    ("all-purpose flour", 120),
    ("whole wheat flour", 120),
    ("flour", 120),
    ("powdered sugar", 120),
    ("confectioners sugar", 120),
    ("icing sugar", 120),
    ("brown sugar", 220),
    ("granulated sugar", 200),
    ("white sugar", 200),
    ("caster sugar", 200),
    ("sugar", 200),
    ("butter", 227),
    ("margarine", 230),
    ("shortening", 205),
    ("vegetable oil", 218),
    ("olive oil", 216),
    ("coconut oil", 205),
    ("honey", 340),
    ("maple syrup", 322),
    ("molasses", 328),
    ("cocoa powder", 100),
    ("cocoa", 100),
    ("rolled oats", 90),
    ("oats", 90),
    ("cornstarch", 128),
    ("rice", 185),
    ("shredded cheese", 113),
    ("parmesan", 100),
    ("milk", 245),
    ("buttermilk", 245),
    ("cream", 238),
    ("heavy cream", 238),
    ("yogurt", 245),
    ("sour cream", 242),
    ("water", 237),
    ("broth", 240),
    ("stock", 240),
    ("salt", 273),
    ("kosher salt", 240),
    ("baking powder", 220),
    ("baking soda", 220),
    ("yeast", 150),
    ("vanilla extract", 224),
    ("peanut butter", 270),
    ("almond flour", 96),
    ("coconut flour", 128),
]

_UNIT_TO_PINT: dict[str, str] = {
    "g": "gram",
    "kg": "kilogram",
    "ml": "milliliter",
    "l": "liter",
    "tsp": "teaspoon",
    "tbsp": "tablespoon",
    "cup": "cup",
    "cups": "cup",
}

_COUNT_UNITS = frozenset({"piece", "pieces", "slice", "slices", "pinch"})
_SKIP_SCALE_UNITS = frozenset({"to taste", ""})


# Data class to hold computed ingredient information after scaling and unit conversion
@dataclass
class ComputedIngredient:
    name: str
    amount: str
    unit: str
    display_amount: str
    display_unit: str
    note: str | None = None

# Return grams per ml for the ingredient based on keyword matching
def _grams_per_ml_for_ingredient(name: str) -> float | None:
    lower = name.lower()
    for key, g_per_cup in _DENSITY_KEYWORDS:
        if key in lower:
            cup_ml = float(_Q(1, _ureg.cup).to(_ureg.milliliter).magnitude)
            return g_per_cup / cup_ml
    return None


# Parse a string amount into a float, supporting formats like "1", "1.5", "1,5", "1 1/2", "1/2"
def parse_amount(amount_str: str) -> float | None:
    s = (amount_str or "").replace(",", ".").strip()
    if not s:
        return None
    mixed = re.match(r"^(\d+(?:\.\d+)?)\s+(\d+)\s*/\s*(\d+)$", s)
    if mixed:
        a, n, d = mixed.groups()
        den = float(d)
        if den == 0:
            return None
        return float(a) + float(n) / den
    frac = re.match(r"^(\d+)\s*/\s*(\d+)$", s)
    if frac:
        n, d = frac.groups()
        den = float(d)
        if den == 0:
            return None
        return float(n) / den
    try:
        return float(s)
    except ValueError:
        return None


def _format_num(x: float, *, max_decimals: int = 2) -> str:
    if math.isnan(x) or math.isinf(x):
        return ""
    rounded = round(x, max_decimals)
    if abs(rounded - int(rounded)) < 1e-9:
        return str(int(rounded))
    s = f"{rounded:.{max_decimals}f}".rstrip("0").rstrip(".")
    return s or "0"


def _scale_amount_unit(amount: str, unit: str, factor: float) -> tuple[str, str]:
    u = (unit or "").strip()
    if u in _SKIP_SCALE_UNITS or not amount.strip():
        return amount, u
    parsed = parse_amount(amount)
    if parsed is None:
        return amount, u
    scaled = parsed * factor
    return _format_num(scaled), u


def _to_metric_volume(ml_qty: _Q) -> tuple[str, str]:
    mag = float(ml_qty.magnitude)
    if mag >= 1000:
        return _format_num(mag / 1000), "l"
    return _format_num(mag), "ml"


def _to_us_volume(ml_qty: _Q) -> tuple[str, str]:
    cups = ml_qty.to(_ureg.cup)
    c = float(cups.magnitude)
    if c >= 0.25:
        s = _format_num(c)
        return s, "cup" if s == "1" else "cups"
    tbsp = ml_qty.to(_ureg.tablespoon)
    t = float(tbsp.magnitude)
    if t >= 0.5:
        return _format_num(t), "tbsp"
    tsp = ml_qty.to(_ureg.teaspoon)
    return _format_num(float(tsp.magnitude)), "tsp"


def _to_metric_mass(g_qty: _Q) -> tuple[str, str]:
    mag = float(g_qty.to(_ureg.gram).magnitude)
    if mag >= 1000:
        return _format_num(mag / 1000), "kg"
    return _format_num(mag), "g"


def _to_us_mass(g_qty: _Q) -> tuple[str, str]:
    oz = g_qty.to(_ureg.ounce)
    o = float(oz.magnitude)
    if o >= 16:
        lb = g_qty.to(_ureg.pound)
        return _format_num(float(lb.magnitude)), "lb"
    return _format_num(o), "oz"


def _convert_line(
    name: str,
    amount: str,
    unit: str,
    *,
    mode: str,
) -> tuple[str, str, str | None]:
    """Return (display_amount, display_unit, optional note)."""
    u = (unit or "").strip()
    scaled_amt, scaled_u = amount, u

    if mode == "original":
        return scaled_amt, scaled_u, None

    parsed = parse_amount(scaled_amt)
    if parsed is None:
        return scaled_amt, scaled_u, None

    note: str | None = None

    if u in _COUNT_UNITS:
        return scaled_amt, scaled_u, None

    if u in _SKIP_SCALE_UNITS:
        return scaled_amt, scaled_u, None

    pint_unit = _UNIT_TO_PINT.get(u)
    if not pint_unit:
        return scaled_amt, scaled_u, None

    try:
        q = parsed * _ureg(pint_unit)
    except (pint.errors.DimensionalityError, ValueError, TypeError):
        return scaled_amt, scaled_u, None

    is_mass = q.check("[mass]")
    is_volume = q.check("[volume]")

    if mode == "metric":
        if is_mass:
            return (*_to_metric_mass(q), None)
        if is_volume:
            ml_q = q.to(_ureg.milliliter)
            g_per_ml = _grams_per_ml_for_ingredient(name)
            if g_per_ml is not None:
                g = float(ml_q.magnitude) * g_per_ml
                return _format_num(g), "g", "approx. (density)"
            return (*_to_metric_volume(ml_q), None)
        return scaled_amt, scaled_u, None

    if mode == "us":
        if is_mass:
            return (*_to_us_mass(q), None)
        if is_volume:
            ml_q = q.to(_ureg.milliliter)
            g_per_ml = _grams_per_ml_for_ingredient(name)
            if g_per_ml is not None:
                g = float(ml_q.magnitude) * g_per_ml
                oz = _Q(g, _ureg.gram).to(_ureg.ounce)
                o = float(oz.magnitude)
                if o >= 16:
                    lb = _Q(g, _ureg.gram).to(_ureg.pound)
                    return _format_num(float(lb.magnitude)), "lb", "approx. (density)"
                return _format_num(o), "oz", "approx. (density)"
            return (*_to_us_volume(ml_q), None)
        return scaled_amt, scaled_u, None

    return scaled_amt, scaled_u, None


def compute_ingredient(name: str, amount: str, unit: str, *, scale_factor: float, mode: str) -> ComputedIngredient:
    scaled_amount, scaled_unit = _scale_amount_unit(amount, unit, scale_factor)
    d_amt, d_unit, note = _convert_line(name, scaled_amount, scaled_unit, mode=mode)
    return ComputedIngredient(
        name=name,
        amount=scaled_amount,
        unit=scaled_unit,
        display_amount=d_amt,
        display_unit=d_unit,
        note=note,
    )


# Build JSON-serializable payload for the recipe detail API
def compute_recipe_ingredients(
    recipe: Any,
    *,
    target_servings: float | None,
    mode: str,
) -> dict[str, Any]:
    """Build JSON-serializable payload for the recipe detail API."""
    base = max(int(getattr(recipe, "servings", None) or 1), 1)
    target = float(target_servings) if target_servings is not None else float(base)
    if target <= 0 or target > 500:
        target = float(base)
    scale_factor = target / float(base)
    mode = mode if mode in ("original", "metric", "us") else "original"

    steps_out: list[dict[str, Any]] = []
    for step in recipe.structured_steps():
        if step.get("type") != "content":
            steps_out.append({"type": step.get("type"), "ingredients": None})
            continue
        items = []
        for ing in step.get("ingredients") or []:
            n = str(ing.get("name") or "").strip()
            if not n:
                continue
            amt = str(ing.get("amount") or "").strip()
            u = str(ing.get("unit") or "").strip()
            c = compute_ingredient(n, amt, u, scale_factor=scale_factor, mode=mode)
            items.append(
                {
                    "name": c.name,
                    "amount": c.amount,
                    "unit": c.unit,
                    "displayAmount": c.display_amount,
                    "displayUnit": c.display_unit,
                    "note": c.note,
                }
            )
        steps_out.append({"type": "content", "ingredients": items})

    legacy_lines = _scale_legacy_ingredient_lines(recipe.ingredients_list(), scale_factor)

    return {
        "baseServings": base,
        "targetServings": int(target) if target == int(target) else target,
        "mode": mode,
        "scaleFactor": scale_factor,
        "steps": steps_out,
        "legacyIngredientLines": legacy_lines,
    }


def _scale_legacy_ingredient_lines(lines: list[str], scale_factor: float) -> list[str]:
    if scale_factor == 1.0:
        return list(lines)
    out: list[str] = []
    pattern = re.compile(r"^(\d+(?:[.,]\d+)?|\d+\s+\d+/\d+|\d+/\d+)\s+")
    for line in lines:
        stripped = line.strip()
        m = pattern.match(stripped)
        if not m:
            out.append(line)
            continue
        token = m.group(1).replace(",", ".")
        parsed = parse_amount(token)
        if parsed is None:
            out.append(line)
            continue
        scaled = _format_num(parsed * scale_factor)
        rebuilt = stripped[: m.start(1)] + scaled + stripped[m.end(1) :]
        out.append(rebuilt)
    return out


# Build a human-readable ingredient line like "1 1/2 cups flour" from display amount/unit and name
def ingredient_line_text(display_amount: str, display_unit: str, name: str) -> str:
    parts = []
    if (display_amount or "").strip():
        parts.append(display_amount.strip())
    if (display_unit or "").strip():
        parts.append(display_unit.strip())
    qty = " ".join(parts).strip()
    if qty:
        return f"{qty} {name}".strip()
    return name
