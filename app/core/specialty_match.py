import re
import unicodedata


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\\s]", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def is_professional_compatible_with_service(service_category: str, professional_specialty: str) -> bool:
    category = _normalize(service_category)
    specialty = _normalize(professional_specialty)
    if not category or not specialty:
        return False

    if category in specialty:
        return True

    if category.endswith("s") and len(category) > 3 and category[:-1] in specialty:
        return True

    if f"{category}s" in specialty:
        return True

    category_tokens = set(category.split(" "))
    specialty_tokens = set(specialty.split(" "))
    return bool(category_tokens.intersection(specialty_tokens))
