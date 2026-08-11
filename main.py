def send_product_result(from_number, txt, urls, bot_id, lang, query, best_only=False, max_stores=None, relevance_mode="exact"):
    if not txt:
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return "none"
    if is_service_answer(txt):
        send_whatsapp_text(from_number, txt, bot_id)
        return "service"
    store_limit = MAX_STORES if max_stores is None else max(1, int(max_stores))
    offers = extract_store_offers(txt, limit=store_limit)
    if not offers:
        send_whatsapp_text(from_number, txt, bot_id)
        return "info"
    if relevance_mode == "similar":
        offers = repair_similar_offer_store_names(offers, urls)

    offers = filter_relevant_offers(query, offers, urls, mode=relevance_mode)
    if not offers:
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return "none"

    title = product_title(txt, query)
    if title:
        send_whatsapp_text(from_number, title, bot_id)

    core = title[2:].strip() if title.startswith("📦") else query
    fq = short_query(core) or short_query(query)
    if best_only:
        best = next((o for o in offers if o["best"]), offers[0])
        offers = [best]

    sent = 0
    fallback_ctas = []

    for o in offers[:store_limit]:
        url = match_url(o["name"], urls)
        if url and not store_url_matches_store(o["name"], url):
            url = ""

        # === v77.1: بدائل مشابهة - لا نقبل إلا صفحة منتج مباشرة ===
        if relevance_mode == "similar":
            product_name = _similar_offer_product_name(o)
            # مصحح: بدون قوس زائد، وبدون متغير url1
            if not is_direct_store_url(url):
                try:
                    url = resolve_direct_product_page(o["name"], product_name, url)
                except Exception as e:
                    print(f"SIMILAR RESOLVE ERR {o['name']}: {e}")
                    url = ""

            if not url or not is_direct_store_url(url) or not store_url_matches_store(o["name"], url):
                print(f"SIMILAR CTA DROP — NO DIRECT PRODUCT PAGE: {o['name']} | {product_name} -> {url}")
                continue

            send_whatsapp_cta(from_number, o["line"], url, bot_id, f"🛒 {o['name'][:18]}")
            sent += 1
            continue

        # الوضع العادي
        if not is_direct_store_url(url):
            try:
                host = urllib.parse.urlparse(url or "").netloc.lower()
            except:
                host = ""
            if url and url.startswith("http") and host and "google." not in host and "bing." not in host:
                fallback_ctas.append((o, url))
            else:
                hp = resolve_store_homepage(o["name"])
                if hp:
                    fallback_ctas.append((o, hp))
            continue

        send_whatsapp_cta(from_number, o["line"], url, bot_id, f"🛒 {o['name'][:18]}")
        sent += 1

    if relevance_mode!= "similar" and fallback_ctas and sent < store_limit:
        remaining = max(0, store_limit - sent)
        checked = list(RESOLVER.map(lambda ou: (ou[0], ou[1], url_is_alive(ou[1])), fallback_ctas[:remaining]))
        for o, url, alive in checked:
            if not alive: continue
            note = "\n🔎 الزر يفتح المتجر — ادور المنتج داخله" if lang == "ar" else "\n🔎 Button opens the store"
            send_whatsapp_cta(from_number, (o["line"] + note)[:1024], url, bot_id, f"🛒 {o['name'][:18]}")
            sent += 1

    if sent == 0:
        if relevance_mode == "similar":
            return "none"
        ranked = sorted(offers[:store_limit], key=lambda o: _extract_numeric_price(o.get("line", "")) or 10**9)
        lines_out = []
        for i, o in enumerate(ranked):
            body_line = re.sub(r"^(?:✅|🏆|•)\s*", "", o.get("line", "")).strip()
            lines_out.append(f"{'✅' if i == 0 else '•'} {body_line}")
        body = "\n".join(lines_out).strip()
        if body:
            send_whatsapp_text(from_number, body, bot_id)
            return "product"
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return "none"
    return "product"
