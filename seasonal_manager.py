import os


CURRENT_SEASON = os.getenv("CURRENT_SEASON", "low").lower()

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
    if CURRENT_SEASON in SEASON_CONTEXTS:
        return CURRENT_SEASON

    return "low"


def get_season_context():
    return SEASON_CONTEXTS[get_current_season()]


def get_seasonal_system_prompt(base_prompt):
    return f"{base_prompt}\n\n{get_season_context()}"
