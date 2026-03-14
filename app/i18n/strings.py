_STRINGS: dict[str, dict[str, str]] = {
    "welcome": {
        "ru": "Receipt Bot\n\n"
              "Отправь фото чека или задай вопрос текстом.\n"
              "/clear — сбросить диалог\n"
              "/lang — сменить язык",
        "en": "Receipt Bot\n\n"
              "Send a photo of a receipt or ask a question in text.\n"
              "/clear — reset dialog\n"
              "/lang — change language",
    },
    "choose_language": {
        "ru": "Выберите язык:",
        "en": "Welcome! Please choose your language:",
    },
    "choose_language_prompt": {
        "ru": "Choose your language / Выберите язык:",
        "en": "Choose your language / Выберите язык:",
    },
    "lang_set": {
        "ru": "Язык установлен: Русский.",
        "en": "Language set to English.",
    },
    "dialog_cleared": {
        "ru": "Контекст диалога очищен.",
        "en": "Dialog context cleared.",
    },
    "receiving_photo": {
        "ru": "Получаю фото чека...",
        "en": "Receiving receipt photo...",
    },
    "processing_receipt": {
        "ru": "Обрабатываю чек...",
        "en": "Processing receipt...",
    },
    "analyzing_photo": {
        "ru": "Анализирую {label} нейронкой...",
        "en": "Analyzing {label} with AI...",
    },
    "photo_label_single": {
        "ru": "фото",
        "en": "photo",
    },
    "photo_label_multi": {
        "ru": "{n} фото",
        "en": "{n} photos",
    },
    "analysis_error": {
        "ru": "Ошибка анализа: {error}",
        "en": "Analysis error: {error}",
    },
    "duplicate_found": {
        "ru": "<b>Дубликат!</b> Этот чек уже сохранён (#{id}).\n"
              "{merchant} | {date} | <b>{total} {currency}</b>",
        "en": "<b>Duplicate!</b> This receipt is already saved (#{id}).\n"
              "{merchant} | {date} | <b>{total} {currency}</b>",
    },
    "thinking": {
        "ru": "Думаю...",
        "en": "Thinking...",
    },
    "query_error": {
        "ru": "Ошибка: {error}",
        "en": "Error: {error}",
    },
    "send_image_file": {
        "ru": "Отправь фото чека или изображение как файл.",
        "en": "Send a receipt photo or image as a file.",
    },
    "receipt_header": {
        "ru": "<b>Чек #{id}</b>",
        "en": "<b>Receipt #{id}</b>",
    },
    "photos_count": {
        "ru": "({n} фото)",
        "en": "({n} photos)",
    },
    "merchant_label": {
        "ru": "Магазин:",
        "en": "Merchant:",
    },
    "items_label": {
        "ru": "<b>Товары:</b>",
        "en": "<b>Items:</b>",
    },
    "items_more": {
        "ru": "  <i>...и ещё {n} позиций</i>",
        "en": "  <i>...and {n} more items</i>",
    },
    "tax_label": {
        "ru": "Налог:",
        "en": "Tax:",
    },
    "discount_label": {
        "ru": "Скидка:",
        "en": "Discount:",
    },
    "total_label": {
        "ru": "ИТОГО:",
        "en": "TOTAL:",
    },
    "payment_label": {
        "ru": "Оплата:",
        "en": "Payment:",
    },
    "accuracy_label": {
        "ru": "Точность:",
        "en": "Accuracy:",
    },
    "low_confidence_warning": {
        "ru": "Низкая точность — проверьте данные.",
        "en": "Low accuracy — please verify the data.",
    },
    "max_steps_exceeded": {
        "ru": "Превышено максимальное количество шагов. Попробуйте переформулировать вопрос.",
        "en": "Maximum number of steps exceeded. Please rephrase your question.",
    },
}


def t(key: str, lang: str = "ru", **kwargs: object) -> str:
    entry = _STRINGS.get(key, {})
    template = entry.get(lang, entry.get("ru", key))
    if kwargs:
        return template.format(**kwargs)
    return template
