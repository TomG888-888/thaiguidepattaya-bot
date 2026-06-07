COMMON_PAYMENT_METHODS = ["наличные", "перевод"]
COMMON_CANCELLATION_POLICY = "Условия отмены зависят от даты поездки и подтверждаются при бронировании."
COMMON_TRAVEL_TIME = "около 1 часа на минивене и 15 минут на скоростном катере"
LOW_SEASON_ACTIVE_NOTE = "В низкий сезон выезды по запросу. Актуальные даты уточняйте в сообщениях."
PUBLIC_TOUR_FIELDS = (
    "title",
    "category",
    "status",
    "short_description",
    "full_description",
    "route",
    "photos",
    "included",
    "not_included",
    "duration",
    "travel_time",
    "departure",
    "hotels",
    "price_adult",
    "price_child",
    "price_from",
    "payment_methods",
    "cancellation_policy",
    "what_to_bring",
    "tags",
)
DEFAULT_PHOTOS = {
    "cover": "",
    "gallery": ["", "", "", ""],
    "required": [],
}


def normalize_gallery(gallery=None):
    normalized_gallery = list(gallery or [])
    return (normalized_gallery + ["", "", "", ""])[:4]


def make_photos(photos=None):
    tour_photos = {
        "cover": DEFAULT_PHOTOS["cover"],
        "gallery": normalize_gallery(DEFAULT_PHOTOS["gallery"]),
        "required": list(DEFAULT_PHOTOS["required"]),
    }
    if photos:
        tour_photos["cover"] = photos.get("cover") or tour_photos["cover"]
        tour_photos["gallery"] = normalize_gallery(photos.get("gallery"))
        tour_photos["required"] = list(photos.get("required") or tour_photos["required"])
    return tour_photos


def make_tour(
    title,
    short_description,
    full_description,
    included,
    category="tour",
    status="active",
    route=None,
    photos=None,
    not_included=None,
    duration="по запросу",
    travel_time="по запросу",
    departure=None,
    hotels=None,
    price_adult="по запросу",
    price_child="по запросу",
    price_from=None,
    internal_net_price=None,
    payment_methods=None,
    cancellation_policy=COMMON_CANCELLATION_POLICY,
    what_to_bring=None,
    tags=None,
):
    if status == "active" and LOW_SEASON_ACTIVE_NOTE not in full_description:
        full_description = f"{full_description} {LOW_SEASON_ACTIVE_NOTE}"

    tour = {
        "title": title,
        "category": category,
        "status": status,
        "short_description": short_description,
        "full_description": full_description,
        "route": route or [],
        "photos": make_photos(photos),
        "included": included,
        "not_included": not_included or ["личные расходы", "дополнительные активности"],
        "duration": duration,
        "travel_time": travel_time,
        "departure": departure or "уточняется при бронировании",
        "hotels": hotels or [],
        "price_adult": price_adult,
        "price_child": price_child,
        "price_from": price_from if price_from is not None else price_adult,
        "payment_methods": payment_methods or COMMON_PAYMENT_METHODS,
        "cancellation_policy": cancellation_policy,
        "what_to_bring": what_to_bring
        or ["купальник", "полотенце", "солнцезащитный крем", "головной убор", "наличные"],
        "tags": tags or [],
    }
    if internal_net_price is not None:
        tour["internal_net_price"] = internal_net_price
    return tour


TOUR_CATALOG = {
    "samet_1d_lunch": make_tour(
        title="Остров Самет 1 день с обедом",
        short_description="Пляжный день на Самете с трансфером, катером, обедом и русским гидом.",
        full_description=(
            "Однодневная программа на остров Самет для гостей, которые хотят красивое море, "
            "пляж Ао Пай, понятную организацию и легкий обед без ночевки."
        ),
        included=[
            "трансфер от отеля в Паттайе и обратно",
            "скоростной катер до острова и обратно",
            "билет в национальный парк",
            "лежаки и зонтики на пляже Ао Пай",
            "легкий обед",
            "сопровождение русского гида",
        ],
        not_included=["личные расходы", "напитки сверх программы", "дополнительные активности на пляже"],
        duration="1 день",
        travel_time=COMMON_TRAVEL_TIME,
        departure="утренний выезд из Паттайи",
        price_adult="по запросу",
        price_child="по запросу",
        tags=["самет", "острова", "море", "пляж", "обед", "1 день", "паттайя"],
    ),
    "samet_1d_no_lunch": make_tour(
        title="Остров Самет 1 день без обеда",
        short_description="Самет на 1 день для тех, кто хочет больше свободы на пляже.",
        full_description=(
            "Однодневная поездка на Самет без включенного обеда: удобно, если хочется "
            "самостоятельно выбрать кафе, провести день у моря и не привязываться к питанию."
        ),
        included=[
            "трансфер от отеля в Паттайе и обратно",
            "скоростной катер до острова и обратно",
            "билет в национальный парк",
            "пляжное время на острове Самет",
            "сопровождение русского гида",
        ],
        not_included=["обед", "личные расходы", "напитки", "дополнительные активности на пляже"],
        duration="1 день",
        travel_time=COMMON_TRAVEL_TIME,
        departure="утренний выезд из Паттайи",
        price_adult="по запросу",
        price_child="по запросу",
        tags=["самет", "острова", "море", "пляж", "без обеда", "1 день", "паттайя"],
    ),
    "samet_1d_fireshow": make_tour(
        title="Остров Самет 1 день с файер-шоу",
        short_description="Дневной отдых на Самете с вечерней атмосферой и файер-шоу.",
        full_description=(
            "Формат для тех, кто хочет не только пляжный день, но и вечернюю атмосферу Самета. "
            "Программа подходит гостям, которые хотят задержаться на острове дольше обычного дня."
        ),
        included=[
            "трансфер от отеля в Паттайе и обратно",
            "скоростной катер до острова и обратно",
            "билет в национальный парк",
            "пляжное время на острове Самет",
            "вечернее файер-шоу",
            "сопровождение русского гида",
        ],
        not_included=["личные расходы", "питание и напитки сверх программы", "дополнительные активности"],
        duration="1 день с вечерней программой",
        travel_time=COMMON_TRAVEL_TIME,
        departure="утренний выезд из Паттайи, возвращение после фаер-шоу",
        price_adult="по запросу",
        price_child="по запросу",
        tags=["самет", "острова", "море", "файер шоу", "вечер", "паттайя"],
    ),
    "samet_2d_seabreeze": make_tour(
        title="Остров Самет 2 дня Sea Breeze",
        short_description="Спокойный отдых на Самете с ночевкой в Sea Breeze.",
        full_description=(
            "Двухдневная программа для тех, кто хочет остаться на Самете с ночевкой, "
            "не спешить и провести больше времени у моря."
        ),
        included=[
            "трансфер от отеля в Паттайе и обратно",
            "скоростной катер до острова и обратно",
            "билет в национальный парк",
            "проживание в Sea Breeze",
        ],
        not_included=["личные расходы", "питание, не указанное в выбранном варианте отеля"],
        duration="2 дня",
        travel_time=COMMON_TRAVEL_TIME,
        departure="утренний выезд из Паттайи",
        hotels=["Sea Breeze"],
        price_adult="по запросу",
        price_child="по запросу",
        what_to_bring=["купальник", "полотенце", "сменная одежда", "солнцезащитный крем", "наличные"],
        tags=["самет", "2 дня", "ночевка", "sea breeze", "острова", "паттайя"],
    ),
    "samet_2d_silver_sand": make_tour(
        title="Остров Самет 2 дня Silver Sand Hotel",
        short_description="Самет на 2 дня с проживанием в Silver Sand Hotel.",
        full_description="Формат для спокойного отдыха с ночевкой и удобной организацией дороги из Паттайи.",
        included=[
            "трансфер от отеля в Паттайе и обратно",
            "скоростной катер до острова и обратно",
            "билет в национальный парк",
            "проживание в Silver Sand Hotel",
        ],
        duration="2 дня",
        travel_time=COMMON_TRAVEL_TIME,
        departure="утренний выезд из Паттайи",
        hotels=["Silver Sand Hotel"],
        price_adult="по запросу",
        price_child="по запросу",
        tags=["самет", "2 дня", "silver sand", "ночевка", "острова", "паттайя"],
    ),
    "samet_2d_silver_sand_full": make_tour(
        title="Остров Самет 2 дня Silver Sand Hotel полный пакет",
        short_description="Расширенный формат Самета на 2 дня с Silver Sand Hotel.",
        full_description=(
            "Полный пакет для гостей, которым важно заранее закрыть максимум организационных вопросов "
            "и спокойно отдохнуть на острове с ночевкой."
        ),
        included=[
            "трансфер от отеля в Паттайе и обратно",
            "скоростной катер до острова и обратно",
            "билет в национальный парк",
            "проживание в Silver Sand Hotel",
            "расширенное сопровождение по программе",
        ],
        duration="2 дня",
        travel_time=COMMON_TRAVEL_TIME,
        departure="утренний выезд из Паттайи",
        hotels=["Silver Sand Hotel"],
        price_adult="по запросу",
        price_child="по запросу",
        tags=["самет", "2 дня", "silver sand", "полный пакет", "ночевка", "паттайя"],
    ),
    "samet_2d_toks": make_tour(
        title="Остров Самет 2 дня Tok’s Little Hut",
        short_description="Самет на 2 дня с проживанием в Tok’s Little Hut.",
        full_description="Вариант для спокойного отдыха с ночевкой на острове и простым пляжным настроением.",
        included=[
            "трансфер от отеля в Паттайе и обратно",
            "скоростной катер до острова и обратно",
            "билет в национальный парк",
            "проживание в Tok’s Little Hut",
        ],
        duration="2 дня",
        travel_time=COMMON_TRAVEL_TIME,
        departure="утренний выезд из Паттайи",
        hotels=["Tok’s Little Hut"],
        price_adult="по запросу",
        price_child="по запросу",
        tags=["самет", "2 дня", "toks little hut", "ночевка", "острова", "паттайя"],
    ),
    "samet_2d_samed_villa": make_tour(
        title="Остров Самет 2 дня Samed Villa",
        short_description="Самет на 2 дня с проживанием в Samed Villa.",
        full_description="Комфортный вариант отдыха с ночевкой для тех, кто хочет провести на острове больше времени.",
        included=[
            "трансфер от отеля в Паттайе и обратно",
            "скоростной катер до острова и обратно",
            "билет в национальный парк",
            "проживание в Samed Villa",
        ],
        duration="2 дня",
        travel_time=COMMON_TRAVEL_TIME,
        departure="утренний выезд из Паттайи",
        hotels=["Samed Villa"],
        price_adult="по запросу",
        price_child="по запросу",
        tags=["самет", "2 дня", "samed villa", "ночевка", "острова", "паттайя"],
    ),
    "samet_2d_samed_pavilion": make_tour(
        title="Остров Самет 2 дня Samed Pavilion",
        short_description="Самет на 2 дня с проживанием в Samed Pavilion.",
        full_description="Вариант для гостей, которым нужен более комфортный формат отдыха с ночевкой на Самете.",
        included=[
            "трансфер от отеля в Паттайе и обратно",
            "скоростной катер до острова и обратно",
            "билет в национальный парк",
            "проживание в Samed Pavilion",
        ],
        duration="2 дня",
        travel_time=COMMON_TRAVEL_TIME,
        departure="утренний выезд из Паттайи",
        hotels=["Samed Pavilion"],
        price_adult="по запросу",
        price_child="по запросу",
        tags=["самет", "2 дня", "samed pavilion", "ночевка", "острова", "паттайя"],
    ),
    "samet_transfer": make_tour(
        title="Трансфер на Самет",
        short_description="Трансфер из Паттайи на Самет для тех, кто сам выбирает отель.",
        full_description=(
            "Подходит тем, кто едет на остров на несколько дней и хочет сам выбрать отель. "
            "В программу входит дорога от отеля в Паттайе, катер до острова и билет в национальный парк."
        ),
        included=[
            "трансфер от отеля в Паттайе и обратно",
            "скоростной катер до острова Самет",
            "билет в национальный парк",
        ],
        not_included=["проживание", "питание", "личные расходы", "дополнительный транспорт по острову"],
        duration="по датам клиента",
        travel_time=COMMON_TRAVEL_TIME,
        departure="по согласованию",
        price_adult="по запросу",
        price_child="по запросу",
        what_to_bring=["документы", "багаж", "наличные", "подтверждение брони отеля"],
        tags=["самет", "трансфер", "катер", "острова", "паттайя"],
    ),
    "tropical_cruise_9_islands": make_tour(
        title="Тропический круиз 9 островов",
        short_description="Морская прогулка по 9 островам для любителей красивых видов и отдыха на воде.",
        full_description=(
            "Программа для тех, кто хочет провести день в формате морского путешествия, "
            "увидеть несколько островов и получить больше впечатлений за одну поездку."
        ),
        included=[
            "остановки по маршруту",
            "обзор островов с лодки",
            "организация маршрута",
            "сопровождение по программе",
        ],
        not_included=["личные расходы", "дополнительные активности", "напитки и питание сверх программы"],
        duration="1 день",
        travel_time="зависит от маршрута и погодных условий",
        departure="07:30–08:00 из Паттайи",
        route={
            "stops": ["Koh Talu", "Koh Ku Dee", "Koh Kram", "Koh Samet"],
            "boat_view": ["Kruai", "Pla Tin", "Klet", "Yung Klua", "Khang Khao"],
        },
        price_adult="по запросу",
        price_child="по запросу",
        internal_net_price={"adult": 2000, "child": 1700},
        tags=["тропический круиз", "9 островов", "море", "острова", "паттайя"],
    ),
    "transfer_bkk_airport_pattaya": make_tour(
        title="Трансфер аэропорт Бангкока - Паттайя",
        category="transfer",
        short_description="Индивидуальный трансфер из аэропорта Бангкока в Паттайю.",
        full_description=(
            "Индивидуальный трансфер на легковом автомобиле. До 3 пассажиров с багажом "
            "или до 4 пассажиров без крупного багажа. Маршрут и время согласуются индивидуально."
        ),
        included=[
            "индивидуальный трансфер на легковом автомобиле",
            "встреча в аэропорту Бангкока",
            "поездка до адреса в Паттайе",
            "согласование времени и маршрута",
        ],
        not_included=["платные парковки при длительном ожидании", "дополнительные остановки вне маршрута"],
        duration="по маршруту",
        travel_time="зависит от аэропорта, адреса и дорожной ситуации",
        departure="по согласованию",
        price_adult=None,
        price_child=None,
        price_from="по запросу",
        what_to_bring=["номер рейса", "адрес в Паттайе", "контактный телефон", "информация о багаже"],
        tags=["трансфер", "аэропорт", "бангкок", "паттайя", "индивидуальный трансфер"],
    ),
    "transfer_pattaya_bkk_airport": make_tour(
        title="Трансфер Паттайя - аэропорт Бангкока",
        category="transfer",
        short_description="Индивидуальный трансфер из Паттайи в аэропорт Бангкока.",
        full_description=(
            "Индивидуальный трансфер на легковом автомобиле. До 3 пассажиров с багажом "
            "или до 4 пассажиров без крупного багажа. Маршрут и время согласуются индивидуально."
        ),
        included=[
            "индивидуальный трансфер на легковом автомобиле",
            "подача по адресу в Паттайе",
            "поездка до аэропорта Бангкока",
            "согласование времени и маршрута",
        ],
        not_included=["платные парковки при длительном ожидании", "дополнительные остановки вне маршрута"],
        duration="по маршруту",
        travel_time="зависит от адреса, аэропорта и дорожной ситуации",
        departure="по согласованию",
        price_adult=None,
        price_child=None,
        price_from="по запросу",
        what_to_bring=["время вылета", "адрес подачи", "контактный телефон", "информация о багаже"],
        tags=["трансфер", "аэропорт", "паттайя", "бангкок", "индивидуальный трансфер"],
    ),
    "transfer_custom_route": make_tour(
        title="Индивидуальный трансфер по маршруту",
        category="transfer",
        short_description="Индивидуальный трансфер по согласованному маршруту.",
        full_description=(
            "Индивидуальный трансфер на легковом автомобиле. До 3 пассажиров с багажом "
            "или до 4 пассажиров без крупного багажа. Маршрут и время согласуются индивидуально."
        ),
        included=[
            "индивидуальный трансфер на легковом автомобиле",
            "маршрут по согласованию",
            "подача в согласованное время",
            "консультация по времени в пути",
        ],
        not_included=["платные парковки", "платные дороги", "дополнительное ожидание сверх договоренности"],
        duration="по маршруту",
        travel_time="зависит от маршрута и дорожной ситуации",
        departure="по согласованию",
        price_adult=None,
        price_child=None,
        price_from="по запросу",
        what_to_bring=["адрес подачи", "адрес назначения", "время поездки", "контактный телефон", "информация о багаже"],
        tags=["трансфер", "индивидуальный трансфер", "паттайя", "таиланд", "маршрут по запросу"],
    ),
    "chang": make_tour(
        title="Ко Чанг",
        status="draft",
        short_description="Поездка на Ко Чанг для отдыха у моря и смены обстановки.",
        full_description="Маршрут подбирается под даты, состав группы и формат отдыха.",
        included=["подбор программы", "консультация по маршруту"],
        tags=["ко чанг", "острова", "море", "паттайя"],
    ),
    "bangkok": make_tour(
        title="Бангкок",
        status="draft",
        short_description="Экскурсия в Бангкок с подбором маршрута под интересы гостей.",
        full_description="Программа подбирается под даты, состав группы и желаемый темп поездки.",
        included=["подбор программы", "консультация по маршруту"],
        what_to_bring=["удобная обувь", "документы", "наличные"],
        tags=["бангкок", "экскурсии", "город", "паттайя"],
    ),
    "nongnooch": make_tour(
        title="Нонг Нуч",
        status="draft",
        short_description="Поездка в тропический сад Нонг Нуч для прогулки и красивых фото.",
        full_description="Формат и детали программы уточняются под даты и состав гостей.",
        included=["подбор программы", "консультация по маршруту"],
        what_to_bring=["удобная обувь", "головной убор", "наличные"],
        tags=["нонг нуч", "сад", "экскурсии", "паттайя"],
    ),
    "khao_kheow": make_tour(
        title="Кхао Кхео",
        status="draft",
        short_description="Поездка в открытый зоопарк Кхао Кхео для семей и любителей животных.",
        full_description="Детали программы уточняются под даты, возраст гостей и формат поездки.",
        included=["подбор программы", "консультация по маршруту"],
        what_to_bring=["удобная обувь", "головной убор", "наличные"],
        tags=["кхао кхео", "зоопарк", "семейный отдых", "паттайя"],
    ),
}


PHOTO_REQUIREMENTS = {
    "samet_1d_lunch": [
        "обложка: аэрофото пляжа Самет",
        "фото 1: пирс/русалка",
        "фото 2: пляж Ао Пай",
        "фото 3: скоростной катер",
        "фото 4: лежаки/кафе/обед",
    ],
    "samet_1d_no_lunch": [
        "обложка: пляж Самет с чистой водой",
        "фото 1: пирс/русалка",
        "фото 2: пляж Ао Пай",
        "фото 3: скоростной катер",
        "фото 4: свободный отдых на пляже",
    ],
    "samet_1d_fireshow": [
        "обложка: вечерний пляж Самет",
        "фото 1: пирс/русалка",
        "фото 2: пляж Ао Пай днем",
        "фото 3: скоростной катер",
        "фото 4: фаер-шоу",
    ],
    "samet_2d_seabreeze": [
        "обложка: главное фото Самета",
        "фото 1: Sea Breeze",
        "фото 2: номер/территория",
        "фото 3: пляж рядом с отелем",
        "фото 4: кафе или зона отдыха",
    ],
    "samet_2d_silver_sand": [
        "обложка: главное фото Самета",
        "фото 1: Silver Sand Hotel",
        "фото 2: номер/территория",
        "фото 3: пляж у отеля",
        "фото 4: завтрак/кафе",
    ],
    "samet_2d_silver_sand_full": [
        "обложка: главное фото Самета",
        "фото 1: Silver Sand Hotel",
        "фото 2: номер/территория",
        "фото 3: пляж у отеля",
        "фото 4: завтрак/кафе",
    ],
    "samet_2d_toks": [
        "обложка: главное фото Самета",
        "фото 1: Tok’s Little Hut",
        "фото 2: номер/территория",
        "фото 3: пляж рядом с отелем",
        "фото 4: кафе или зона отдыха",
    ],
    "samet_2d_samed_villa": [
        "обложка: главное фото Самета",
        "фото 1: Samed Villa",
        "фото 2: номер/территория",
        "фото 3: пляж рядом с отелем",
        "фото 4: кафе или зона отдыха",
    ],
    "samet_2d_samed_pavilion": [
        "обложка: главное фото Самета",
        "фото 1: Samed Pavilion",
        "фото 2: номер/территория",
        "фото 3: пляж рядом с отелем",
        "фото 4: бассейн/территория",
    ],
    "samet_transfer": [
        "обложка: пляж Самет",
        "фото 1: пирс",
        "фото 2: скоростной катер",
        "фото 3: багаж/посадка",
        "фото 4: дорога к острову или пляж Самет",
    ],
    "tropical_cruise_9_islands": [
        "обложка: морской круиз",
        "фото 1: Koh Talu или Koh Ku Dee",
        "фото 2: Koh Kram или Koh Samet",
        "фото 3: снорклинг/катер",
        "фото 4: обзорные острова",
    ],
    "transfer_bkk_airport_pattaya": [
        "обложка: аэропорт Бангкока",
        "фото 1: автомобиль/трансфер",
        "фото 2: багаж",
        "фото 3: дорога Бангкок–Паттайя",
        "фото 4: встреча/табличка или зона прилета",
    ],
    "transfer_pattaya_bkk_airport": [
        "обложка: трансфер из Паттайи",
        "фото 1: автомобиль/трансфер",
        "фото 2: багаж",
        "фото 3: дорога Паттайя–Бангкок",
        "фото 4: аэропорт Бангкока",
    ],
    "transfer_custom_route": [
        "обложка: индивидуальный трансфер",
        "фото 1: автомобиль/трансфер",
        "фото 2: багаж",
        "фото 3: дорога по маршруту",
        "фото 4: посадка пассажиров",
    ],
}


for tour_key, required_photos in PHOTO_REQUIREMENTS.items():
    TOUR_CATALOG[tour_key]["photos"]["required"] = required_photos


PHOTO_READY_TOURS = (
    "samet_1d_lunch",
    "samet_1d_no_lunch",
    "samet_1d_fireshow",
    "samet_2d_seabreeze",
    "samet_2d_silver_sand",
    "samet_2d_silver_sand_full",
    "samet_2d_toks",
    "samet_2d_samed_villa",
    "samet_2d_samed_pavilion",
    "samet_transfer",
    "tropical_cruise_9_islands",
)


def get_static_tour_photos(tour_key):
    return {
        "cover": f"/static/tours/{tour_key}/cover.jpg",
        "gallery": [
            f"/static/tours/{tour_key}/gallery_1.jpg",
            f"/static/tours/{tour_key}/gallery_2.jpg",
            f"/static/tours/{tour_key}/gallery_3.jpg",
            f"/static/tours/{tour_key}/gallery_4.jpg",
        ],
    }


for tour_key in PHOTO_READY_TOURS:
    TOUR_CATALOG[tour_key]["photos"].update(get_static_tour_photos(tour_key))


def normalize_tour_key(tour_key):
    return tour_key.replace("-", "_").lower()


def get_tour(tour_key):
    return TOUR_CATALOG.get(normalize_tour_key(tour_key))


def get_public_tour(tour_key):
    tour = get_tour(tour_key)
    if not tour:
        return None
    return {field: tour[field] for field in PUBLIC_TOUR_FIELDS if field in tour}


def format_tour_data(tour, include_route=True):
    """Return only public tour fields for GPT prompts and customer-facing cards."""
    public_tour = {field: tour[field] for field in PUBLIC_TOUR_FIELDS if field in tour}
    lines = [
        f"title: {public_tour['title']}",
        f"short_description: {public_tour['short_description']}",
        f"full_description: {public_tour['full_description']}",
    ]
    if include_route and public_tour.get("route"):
        route = public_tour["route"]
        if isinstance(route, dict):
            lines.extend(["route:", "stops:", *[f"- {item}" for item in route.get("stops", [])]])
            lines.extend(["boat_view:", *[f"- {item}" for item in route.get("boat_view", [])]])
        else:
            lines.extend(["route:", *[f"- {item}" for item in route]])

    lines.extend([
        "included:",
        *[f"- {item}" for item in public_tour["included"]],
        "not_included:",
        *[f"- {item}" for item in public_tour["not_included"]],
        f"duration: {public_tour['duration']}",
        f"travel_time: {public_tour['travel_time']}",
        f"departure: {public_tour.get('departure') or 'уточняется при бронировании'}",
        "hotels:",
        *[f"- {hotel}" for hotel in public_tour["hotels"]],
        f"price_adult: {public_tour['price_adult']}",
        f"price_child: {public_tour['price_child']}",
        f"price_from: {public_tour['price_from']}",
        "payment_methods:",
        *[f"- {method}" for method in public_tour["payment_methods"]],
        f"cancellation_policy: {public_tour['cancellation_policy']}",
        "what_to_bring:",
        *[f"- {item}" for item in public_tour["what_to_bring"]],
        "tags:",
        *[f"- {tag}" for tag in public_tour["tags"]],
    ])
    return "\n".join(lines)


def is_samet_tour(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    return normalized_tour_key.startswith("samet_") or normalized_tour_key == "tropical_cruise_9_islands"


def get_samet_catalog_context():
    return "\n\n".join(
        format_tour_data(get_public_tour(tour_key))
        for tour_key, tour in TOUR_CATALOG.items()
        if is_samet_tour(tour_key)
    )
