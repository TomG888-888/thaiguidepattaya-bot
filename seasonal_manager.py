import os

from database import get_setting, set_setting


DEFAULT_SEASON = os.getenv("CURRENT_SEASON", "low").lower()
SEASON_SETTING_KEY = "current_season"

SEASON_CONTEXTS = {
    "high": """Текущий сезон: high.
Учитывай высокий сезон: мест меньше, цены выше, популярные даты быстро заканчиваются.
Делай акцент на бронирование заранее, быстрый выбор и подтверждение мест.""",
    "low": """Текущий сезон: low.
Учитывай низкий сезон: больше скидок, меньше туристов, спокойный отдых и гибкие даты.
Делай акцент на выгодные даты, приватные туры и комфорт без толп.""",
    "rainy": """Текущий сезон: rainy.
Учитывай сезон дождей: не предлагай всё подряд, осторожнее с морскими турами.
Проверяй погоду, предлагай безопасные маршруты и запасные варианты.""",
}


def get_current_season():
    try:
        current_season = (get_setting(SEASON_SETTING_KEY) or DEFAULT_SEASON).lower()
    except Exception:
        current_season = DEFAULT_SEASON

    if current_season in SEASON_CONTEXTS:
        return current_season

    return "low"


def init_current_season():
    if get_setting(SEASON_SETTING_KEY):
        return

    set_setting(SEASON_SETTING_KEY, get_current_season())


def set_current_season(season):
    normalized_season = season.lower()
    if normalized_season not in SEASON_CONTEXTS:
        return False

    set_setting(SEASON_SETTING_KEY, normalized_season)
    return True


def get_season_context():
    return SEASON_CONTEXTS[get_current_season()]


def get_seasonal_system_prompt(base_prompt):
    return f"{base_prompt}\n\n{get_season_context()}"
