"""Tests for health_score.py (run: python test_score.py or pytest)."""

from health_score import calculate_health_score, raw_to_score, score_category
from nutrient_parser import parse_nutrients

SPEC = """Per 100 g
Energy 450 kcal
Protein 8 g
Sugars 18 g
Saturated Fat 6 g
Fibre 4 g
Sodium 400 mg"""


def P(kcal, sugar, sat, sodium, fibre, protein, normalized=True):
    return dict(calories_kcal=kcal, sugar_g=sugar, saturated_fat_g=sat, sodium_mg=sodium,
                fibre_g=fibre, protein_g=protein, normalized=normalized)


def test_spec_sample_is_below_average():
    r = calculate_health_score(parse_nutrients(SPEC))
    # negative = 5 (energy) + 5 (sugar) + 5 (sat fat) + 4 (sodium) = 19 -> protein ignored
    assert r["negative_points"] == 19 and r["positive_points"] == 1
    assert r["category"] == "Below Average" and 21 <= r["score"] <= 40


def test_protein_ignored_when_negative_points_high():
    r = calculate_health_score(P(450, 18, 6, 400, 4, 20))
    assert r["positive_points"] == 1  # only fibre counted
    assert any("Protein points were not counted" in n for n in r["notes"])


# ---- Benchmark: real-world products must land on the right side ----
UNHEALTHY = {
    "Potato chips": P(536, 0.5, 3.5, 600, 4, 6),
    "Instant noodles": P(430, 2, 8, 1500, 3, 9),
    "Digestive biscuits": P(480, 20, 8, 400, 3, 7),
    "Chocolate bar": P(540, 55, 18, 80, 3, 6),
    "Cream biscuits": P(490, 30, 9, 300, 1, 5),
    "Namkeen": P(560, 3, 13, 900, 5, 15),
    "Corn flakes (sweetened)": P(370, 8, 0.5, 600, 3, 7),
}
HEALTHY = {
    "Plain oats": P(370, 1, 1.4, 5, 10, 13),
    "Muesli (no sugar)": P(360, 12, 1.5, 30, 8, 10),
    "Plain yogurt": P(60, 4.5, 2, 45, 0, 4),
}


def test_unhealthy_foods_never_above_below_average():
    for name, p in UNHEALTHY.items():
        r = calculate_health_score(p)
        assert r["score"] <= 40, f"{name} scored {r['score']} ({r['category']})"


def test_healthy_foods_score_good_or_better():
    for name, p in HEALTHY.items():
        r = calculate_health_score(p)
        assert r["score"] >= 61, f"{name} scored {r['score']} ({r['category']})"


def test_drinks_use_stricter_thresholds():
    cola = calculate_health_score(P(42, 10.6, 0, 5, 0, 0), is_drink=True)
    juice = calculate_health_score(P(46, 10, 0, 2, 0.2, 0.7), is_drink=True)
    water = calculate_health_score(P(0, 0, 0, 5, 0, 0), is_drink=True)
    assert cola["score"] <= 20 and juice["score"] <= 40 and water["score"] >= 81
    # the same cola scored as a FOOD would wrongly look Moderate - that is why drink mode exists
    assert calculate_health_score(P(42, 10.6, 0, 5, 0, 0))["score"] >= 41


def test_sweeteners_penalise_diet_drinks():
    plain = calculate_health_score(P(1, 0, 0, 10, 0, 0), is_drink=True)
    sweet = calculate_health_score(P(1, 0, 0, 10, 0, 0), is_drink=True, has_sweeteners=True)
    assert sweet["score"] < plain["score"]


def test_missing_key_nutrient_is_capped_at_moderate():
    # sodium missing: cannot prove the food is healthy
    r = calculate_health_score(dict(calories_kcal=370, sugar_g=1, saturated_fat_g=1.4,
                                    fibre_g=10, protein_g=13, normalized=True))
    assert r["capped"] and r["score"] <= 60 and "Sodium" in r["missing_negative"]


def test_unnormalized_values_are_capped():
    r = calculate_health_score(P(370, 1, 1.4, 5, 10, 13, normalized=False))
    assert r["capped"] and r["score"] <= 60


def test_too_few_nutrients_gives_no_score():
    r = calculate_health_score({"sugar_g": 10.0})
    assert r["score"] is None and r["notes"]


def test_raw_mapping_is_monotonic():
    scores = [raw_to_score(x) for x in range(-10, 41)]
    assert all(a >= b for a, b in zip(scores, scores[1:]))
    assert raw_to_score(-10) == 100 and raw_to_score(40) == 0


def test_bands():
    assert [score_category(s) for s in (0, 20, 21, 40, 41, 60, 61, 80, 81, 100)] == [
        "Poor", "Poor", "Below Average", "Below Average", "Moderate", "Moderate",
        "Good", "Good", "Excellent", "Excellent"]


def test_deterministic():
    p = parse_nutrients(SPEC)
    assert calculate_health_score(p) == calculate_health_score(p)


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("PASS", n)
