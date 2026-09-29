from __future__ import annotations

from copy import deepcopy
from typing import Any


def _unique(values: list[Any]) -> list[Any]:
    """Déduplique en préservant l'ordre d'apparition."""
    result: list[Any] = []
    seen: set[str] = set()

    for value in values:
        marker = repr(value)

        if marker not in seen:
            seen.add(marker)
            result.append(value)

    return result


def _merge_comment(left: Any, right: Any) -> str | None:
    """Concatène les commentaires distincts dans l'ordre des fichiers."""
    left_value = left if left not in (None, "") else None
    right_value = right if right not in (None, "") else None

    if left_value is None:
        return right_value

    if right_value is None:
        return left_value

    return " | ".join(_unique(left_value.split(" | ") + right_value.split(" | ")))


def _normalise_meal(meal: dict[str, Any]) -> None:
    """Regroupe les éléments par type et supprime les contenus identiques."""
    elements_by_type: dict[str, dict[str, Any]] = {}
    normalised_elements: list[dict[str, Any]] = []

    for element in meal.get("elements", []):
        if not isinstance(element, dict):
            continue

        element_type = element.get("type")
        contenu = element.get("contenu", [])

        if not isinstance(contenu, list):
            contenu = [contenu] if contenu not in (None, "") else []

        if not element_type:
            copied = deepcopy(element)
            copied["contenu"] = deepcopy(_unique(contenu))
            normalised_elements.append(copied)
            continue

        if element_type not in elements_by_type:
            copied = deepcopy(element)
            copied["contenu"] = deepcopy(_unique(contenu))
            elements_by_type[element_type] = copied
            normalised_elements.append(copied)
            continue

        current = elements_by_type[element_type]
        current["contenu"] = _unique(current["contenu"] + deepcopy(contenu))

    meal["elements"] = normalised_elements


def _merge_meal(
    target_meal: dict[str, Any],
    source_meal: dict[str, Any],
) -> None:
    """Fusionne un déjeuner ou un goûter par type d'élément."""
    _normalise_meal(target_meal)

    source_copy = deepcopy(source_meal)
    _normalise_meal(source_copy)

    target_elements = target_meal.setdefault("elements", [])
    elements_by_type = {
        element.get("type"): element
        for element in target_elements
        if isinstance(element, dict) and element.get("type")
    }

    for source_element in source_copy.get("elements", []):
        element_type = source_element.get("type")

        if not element_type:
            target_elements.append(deepcopy(source_element))
            continue

        if element_type not in elements_by_type:
            copied_element = deepcopy(source_element)
            target_elements.append(copied_element)
            elements_by_type[element_type] = copied_element
            continue

        target_element = elements_by_type[element_type]
        target_element["contenu"] = _unique(
            target_element["contenu"] + source_element.get("contenu", [])
        )

    target_meal["commentaires"] = _merge_comment(
        target_meal.get("commentaires"),
        source_copy.get("commentaires"),
    )


def _normalise_age_group(age_group: dict[str, Any]) -> None:
    """Normalise un groupe d'âge avant ou après fusion."""
    allergenes = age_group.get("allergenes", [])

    if not isinstance(allergenes, list):
        allergenes = [allergenes] if allergenes not in (None, "") else []

    age_group["allergenes"] = _unique(allergenes)

    regimes = age_group.setdefault("regimes_specifiques", {})

    if not isinstance(regimes, dict):
        regimes = {}
        age_group["regimes_specifiques"] = regimes

    for key, value in list(regimes.items()):
        regimes[key] = bool(value)

    repas = age_group.setdefault("repas", {})

    if not isinstance(repas, dict):
        repas = {}
        age_group["repas"] = repas

    for meal_name in ("dejeuner", "gouter"):
        meal = repas.get(meal_name)

        if isinstance(meal, dict):
            _normalise_meal(meal)


def _merge_age_group(
    target_age_group: dict[str, Any],
    source_age_group: dict[str, Any],
) -> None:
    """
    Fusionne deux groupes de même tranche d'âge :
    allergènes, régimes, repas et commentaires.
    """
    _normalise_age_group(target_age_group)

    source_copy = deepcopy(source_age_group)
    _normalise_age_group(source_copy)

    target_age_group["allergenes"] = _unique(
        target_age_group.get("allergenes", [])
        + source_copy.get("allergenes", [])
    )

    target_regimes = target_age_group.setdefault(
        "regimes_specifiques",
        {},
    )

    for regime, source_value in source_copy.get(
        "regimes_specifiques",
        {},
    ).items():
        target_regimes[regime] = bool(
            target_regimes.get(regime, False)
        ) or bool(source_value)

    target_repas = target_age_group.setdefault("repas", {})

    for meal_name, source_meal in source_copy.get("repas", {}).items():
        if not isinstance(source_meal, dict):
            continue

        if meal_name not in target_repas:
            target_repas[meal_name] = deepcopy(source_meal)
            continue

        if not isinstance(target_repas[meal_name], dict):
            target_repas[meal_name] = deepcopy(source_meal)
            continue

        _merge_meal(target_repas[meal_name], source_meal)


def _normalise_day(day: dict[str, Any]) -> None:
    """Fusionne les éventuels doublons de tranche d'âge dans un jour."""
    day["ferie"] = bool(day.get("ferie", False))

    age_groups = day.get("tranche_age", {})

    if not isinstance(age_groups, dict):
        day["tranche_age"] = {}
        return

    for age_group in age_groups.values():
        if isinstance(age_group, dict):
            _normalise_age_group(age_group)


def _merge_day(
    target_day: dict[str, Any],
    source_day: dict[str, Any],
) -> None:
    """Fusionne deux jours partageant la même date."""
    _normalise_day(target_day)

    source_copy = deepcopy(source_day)
    _normalise_day(source_copy)

    if target_day.get("jour_semaine") in (None, ""):
        target_day["jour_semaine"] = source_copy.get("jour_semaine")

    if target_day.get("theme") != source_copy.get("theme"):
        target_day["theme"] = _merge_comment(
            target_day.get("theme"), source_copy.get("theme")
        )

    target_day["ferie"] = bool(target_day.get("ferie", False)) or bool(
        source_copy.get("ferie", False)
    )

    target_age_groups = target_day.setdefault("tranche_age", {})

    for age_key, source_age_group in source_copy.get(
        "tranche_age",
        {},
    ).items():
        if not isinstance(source_age_group, dict):
            continue

        if age_key not in target_age_groups:
            target_age_groups[age_key] = deepcopy(source_age_group)
            continue

        if not isinstance(target_age_groups[age_key], dict):
            target_age_groups[age_key] = deepcopy(source_age_group)
            continue

        _merge_age_group(
            target_age_groups[age_key],
            source_age_group,
        )


def merge_menu_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Regroupe plusieurs payloads de menus.

    Invariants garantis :
    - un seul objet dans ``jours`` par date ;
    - une seule entrée par tranche d'âge dans un jour ;
    - union dédupliquée des allergènes ;
    - OR logique sur les régimes ;
    - concaténation par type des contenus des repas, sans doublons identiques ;
    - concaténation des commentaires distincts dans l'ordre des fichiers ;
    - conservation des différentes périodes.
    """
    result: dict[str, Any] = {
        "etablissement_id": "",
        "periode": "",
        "jours": [],
    }

    days_by_date: dict[str, dict[str, Any]] = {}
    periods: list[str] = []

    for payload in payloads:
        if not isinstance(payload, dict):
            raise ValueError("Chaque payload doit être un objet JSON.")

        if not result["etablissement_id"] and payload.get("etablissement_id"):
            result["etablissement_id"] = str(payload["etablissement_id"])

        if payload.get("periode"):
            periods.append(str(payload["periode"]))

        days = payload.get("jours", [])

        if not isinstance(days, list):
            raise ValueError("La propriété 'jours' doit être un tableau.")

        for source_day in days:
            if not isinstance(source_day, dict):
                raise ValueError(
                    "Chaque élément de 'jours' doit être un objet."
                )

            date = source_day.get("date")

            if not isinstance(date, str) or not date:
                raise ValueError(
                    "Chaque objet 'jour' doit contenir une date valide."
                )

            if date not in days_by_date:
                copied_day = deepcopy(source_day)
                _normalise_day(copied_day)

                days_by_date[date] = copied_day
                result["jours"].append(copied_day)
                continue

            _merge_day(days_by_date[date], source_day)

    result["periode"] = " | ".join(_unique(periods))
    result["jours"].sort(key=lambda day: day["date"])

    return result
