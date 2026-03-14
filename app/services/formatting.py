from ..i18n.strings import t


def format_reply(data: dict, receipt_id: int, n_photos: int = 1, lang: str = "ru") -> str:
    lines = [t("receipt_header", lang, id=receipt_id)]
    if n_photos > 1:
        lines[0] += " " + t("photos_count", lang, n=n_photos)

    if data.get("merchant"):
        lines.append(f"<b>{t('merchant_label', lang)}</b> {data['merchant']}")
    if data.get("address"):
        lines.append(f"{data['address']}")
    if data.get("purchase_date"):
        time_ = data.get("purchase_time") or ""
        lines.append(f"{data['purchase_date']}" + (f" {time_}" if time_ else ""))
    if data.get("receipt_number"):
        lines.append(f"#{data['receipt_number']}")

    lines.append("")

    items = data.get("items") or []
    if items:
        lines.append(t("items_label", lang))
        for item in items[:30]:
            name = item.get("name", "?")
            qty = item.get("quantity", 1)
            price = item.get("total_price") or item.get("unit_price")
            currency = data.get("currency", "")
            category = item.get("category")
            cat_str = f" <i>[{category}]</i>" if category is not None else ""
            if price is not None:
                lines.append(f"  {name} x{qty} — {price} {currency}{cat_str}")
            else:
                lines.append(f"  {name} x{qty}{cat_str}")
        if len(items) > 30:
            lines.append(t("items_more", lang, n=len(items) - 30))
        lines.append("")

    if data.get("tax_amount"):
        lines.append(f"{t('tax_label', lang)} {data['tax_amount']} {data.get('currency', '')}")
    if data.get("discount_amount"):
        lines.append(f"{t('discount_label', lang)} {data['discount_amount']} {data.get('currency', '')}")

    total = data.get("total_amount")
    currency = data.get("currency", "")
    if total is not None:
        lines.append(f"\n<b>{t('total_label', lang)} {total} {currency}</b>")

    if data.get("payment_method"):
        lines.append(f"{t('payment_label', lang)} {data['payment_method']}")

    if data.get("description"):
        lines.append(f"\n<i>{data['description']}</i>")

    conf = data.get("confidence")
    if conf is not None:
        lines.append(f"\n<i>{t('accuracy_label', lang)} {int(conf * 100)}%</i>")
        if conf < 0.7:
            lines.append(f"\n<i>{t('low_confidence_warning', lang)}</i>")

    return "\n".join(lines)
