import requests
import json
import re
import base64
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── НАСТРОЙКИ ───────────────────────────────────────────────
CLICKUP_TOKEN = os.getenv("CLICKUP_TOKEN")
CLICKUP_LIST_ID = "901112676641"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "RoseAhmar/stats-ban"
GITHUB_FILE = "index.html"

# Поля из ClickUp (имена кастомных полей — проверим при первом запуске)
FIELD_INTERNAL_STATUS = "internal status"
FIELD_GMAIL_SELLER = "Gmail Seller"
FIELD_DOC_SELLER = "Doc seller"
FIELD_ACCOUNT_STATUS = "Account Status"
FIELD_TYPE_BAN = "Тип бана"
FIELD_ID_BUY = "ID_buy"
FIELD_BUYER = "Баер (для кого)"

# ─── СТАТУСЫ ─────────────────────────────────────────────────
VALID_INTERNAL = ["Выдан"]
INVALID_INTERNAL = [
    "no valid при заведении (пустышка)",
    "no valid - после 1 логина",
    "no valid - после прогрева"
]
VERIFIED_STATUSES = [
    "ACTIVE", "APPEAL SUCCESSFUL  ПП/Unpaid/БизВериф", "Active/Pause",
    "END-1. Перевязать карту перед удалением",
    "END-2. Средства выведены/Карта отвязана",
    "End-3 Перевязать карту но оставить на этом же статусе",
    "FREEZE",
]

QUEUE_STATUSES = [
    "READY TO WORK", "Review", "В процессе верификации",
    "НА ВЕРИФ", "Business Verification",
]
NA_ZAMENU = "НА ЗАМЕНУ"
# Все doc seller учитываются
BAN_TYPES = [
    "Бан по докам", "Упал на номер", "Мультиакк",
    "20 минутный таск", "Бан на ревью (ИЛИ сразу после)"
]

# ─── ЗАГРУЗКА ЗАДАЧ ИЗ CLICKUP ───────────────────────────────
def fetch_tasks_batch(headers, archived=False):
    """Загружает все задачи — обычные или архивированные."""
    tasks = []
    page = 0
    label = "архивированных" if archived else "обычных"
    while True:
        url = f"https://api.clickup.com/api/v2/list/{CLICKUP_LIST_ID}/task"
        params = {
            "page": page,
            "limit": 100,
            "include_closed": "true",
            "date_created_gt": 1772323200000,  # 1 марта 2026 UTC
            "date_created_lt": int(datetime.now().timestamp() * 1000),  # сейчас
        }
        if archived:
            params["archived"] = "true"
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            print(f"Ошибка ClickUp API ({label}): {resp.status_code} {resp.text}")
            break
        data = resp.json()
        batch = data.get("tasks", [])
        if not batch:
            break
        tasks.extend(batch)
        if len(tasks) % 500 == 0:
            print(f"  Загружено {label}: {len(tasks)}")
        if data.get("last_page"):
            break
        page += 1
    return tasks

def fetch_all_tasks():
    headers = {"Authorization": CLICKUP_TOKEN}

    print("Загружаю обычные задачи из ClickUp...")
    normal = fetch_tasks_batch(headers, archived=False)
    print(f"  Обычных задач: {len(normal)}")

    print("Загружаю архивированные задачи...")
    archived = fetch_tasks_batch(headers, archived=True)
    print(f"  Архивированных задач: {len(archived)}")

    # Объединяем, убирая дубли по task id
    all_ids = set(t["id"] for t in normal)
    unique_archived = [t for t in archived if t["id"] not in all_ids]
    tasks = normal + unique_archived

    print(f"Всего уникальных задач: {len(tasks)}")
    return tasks

def get_field(task, field_name):
    """Достаём значение кастомного поля по имени."""
    for f in task.get("custom_fields", []):
        if f.get("name", "").lower() == field_name.lower():
            val = f.get("value")
            if val is None:
                return None
            field_type = f.get("type", "")
            # Dropdown — value это orderindex числом, маппим на имя опции
            if field_type == "drop_down":
                options = f.get("type_config", {}).get("options", [])
                for o in options:
                    if str(o.get("orderindex")) == str(val):
                        return o.get("name")
                return None
            # Short text и другие текстовые
            if field_type in ("short_text", "text", "url", "email", "phone"):
                return str(val).strip() if str(val).strip() else None
            # Dict
            if isinstance(val, dict):
                return val.get("name") or val.get("label") or str(val)
            # Users field
            if field_type == "users":
                if isinstance(val, list) and val:
                    return val[0].get("username") or val[0].get("name")
                return None
            # List
            if isinstance(val, list):
                return val[0].get("name") if val else None
            return str(val).strip() if str(val).strip() else None
    return None

def debug_field(tasks, field_name, limit=3):
    """Печатает сырую структуру поля для отладки."""
    found = 0
    for t in tasks:
        for f in t.get("custom_fields", []):
            if f.get("name", "").lower() == field_name.lower():
                if f.get("value") is not None and found < limit:
                    print(f"\n[DEBUG] поле '{field_name}' в задаче '{t.get('name','')[:40]}':")
                    print(f"  type:        {f.get('type')}")
                    print(f"  value:       {f.get('value')}")
                    print(f"  type_config: {str(f.get('type_config',''))[:200]}")
                    found += 1
    if found == 0:
        print(f"\n[DEBUG] поле '{field_name}': ни у одной задачи нет значения!")

def parse_tasks(tasks):
    """Парсим задачи в список словарей."""
    rows = []
    for t in tasks:
        row = {
            "id": t.get("id"),
            "name": t.get("name"),
            "date_created": t.get("date_created"),
            "internal_status": get_field(t, FIELD_INTERNAL_STATUS),
            "gmail_seller": get_field(t, FIELD_GMAIL_SELLER),
            "doc_seller": get_field(t, FIELD_DOC_SELLER),
            "account_status": get_field(t, FIELD_ACCOUNT_STATUS),
            "type_ban": get_field(t, FIELD_TYPE_BAN),
            "id_buy": get_field(t, FIELD_ID_BUY),
            "buyer": get_field(t, FIELD_BUYER),
        }
        rows.append(row)
    return rows

# ─── ПОДСЧЁТ СТАТИСТИКИ ──────────────────────────────────────
def pct(n, base):
    return round(n / base * 100, 1) if base > 0 else 0

def compute_data(rows):
    # Фильтр по дате создания задачи: 1 марта 2026 — сейчас
    DATE_START_MS = 1772323200000
    DATE_END_MS   = int(datetime.now().timestamp() * 1000)

    by_id = {}
    skipped_no_id = 0
    skipped_out_date = 0
    skipped_no_date = 0
    for r in rows:
        if not r["id_buy"]:
            skipped_no_id += 1
            continue
        dc = int(r.get("date_created") or 0)
        if dc == 0:
            skipped_no_date += 1
            continue
        if not (DATE_START_MS <= dc <= DATE_END_MS):
            skipped_out_date += 1
            continue
        by_id.setdefault(r["id_buy"], []).append(r)
    print(f"  Пропущено без ID_buy: {skipped_no_id}")
    print(f"  Пропущено вне даты (не март-апрель 2026): {skipped_out_date}")
    print(f"  Пропущено без даты: {skipped_no_date}")

    # Глобальный резерв по дате задачи (для метрик, как в ClickUp)
    APR_SPLIT = 1774994400000
    all_valid = [r for r in rows
                 if DATE_START_MS <= int(r.get("date_created") or 0) <= DATE_END_MS
                 and r.get("internal_status") in ("DONE", "на выдачу", "На выдачу")]
    reserve_mar_global = sum(1 for r in all_valid if int(r.get("date_created") or 0) < APR_SPLIT)
    reserve_apr_global = sum(1 for r in all_valid if int(r.get("date_created") or 0) >= APR_SPLIT)

    # Реальный тотал
    real_totals = {k: len(v) for k, v in by_id.items()}

    purchases = []
    for id_buy, group in sorted(by_id.items(), key=lambda x: (str(x[0]).zfill(10))):
        group_f = [r for r in group if r["gmail_seller"] and r["internal_status"]]
        total = len(group_f)
        if total == 0:
            continue

        # Выдан + баер указан = произведено аккаунтов
        val = [r for r in group if r["internal_status"] in VALID_INTERNAL and r["buyer"]]
        inval = [r for r in group_f if r["internal_status"] in INVALID_INTERNAL]
        # Считаем из всей группы (не только с gmail+status)
        pust = sum(1 for r in group if r["internal_status"] == "no valid при заведении (пустышка)")
        after1 = sum(1 for r in group if r["internal_status"] == "no valid - после 1 логина")
        after_warm = sum(1 for r in group if r["internal_status"] == "no valid - после прогрева")
        # В запасе = DONE + на выдачу (только задачи с gmail_seller, как group_f)
        APR_SPLIT = 1774994400000  # April 1 00:00 Europe/Brussels (UTC+2)
        _is_done = lambda r: r["internal_status"] == "DONE"
        _is_nav  = lambda r: r["internal_status"] in ("на выдачу", "На выдачу")
        done_count = sum(1 for r in group_f if _is_done(r))
        na_vydachu = sum(1 for r in group_f if _is_nav(r))
        reserve = done_count + na_vydachu
        reserve_mar = sum(1 for r in group_f if (_is_done(r) or _is_nav(r)) and int(r.get("date_created") or 0) < APR_SPLIT)
        reserve_apr = sum(1 for r in group_f if (_is_done(r) or _is_nav(r)) and int(r.get("date_created") or 0) >= APR_SPLIT)
        gmails = [r["gmail_seller"] for r in group_f if r["gmail_seller"]]
        gmail = max(set(gmails), key=gmails.count) if gmails else "—"

        # По doc seller — все
        docs = []
        doc_group_all = [r for r in group_f if r["doc_seller"]]
        doc_sellers_in_group = sorted(set(r["doc_seller"] for r in doc_group_all))

        for doc in doc_sellers_in_group:
            dg = [r for r in doc_group_all if r["doc_seller"] == doc]
            dval = [r for r in dg if r["internal_status"] in VALID_INTERNAL]
            passed = [r for r in dval if r["account_status"] in VERIFIED_STATUSES]
            failed = [r for r in dval if r["account_status"] == NA_ZAMENU]
            total_vna = len(passed) + len(failed)
            not_yet = len(dval) - total_vna

            # В очереди — с разбивкой по статусам
            queue_upper = [s.upper() for s in QUEUE_STATUSES]
            queued = [r for r in dval if r["account_status"] and
                      r["account_status"].strip().upper() in queue_upper]
            queue_counts = {}
            for r in queued:
                s = r["account_status"]
                queue_counts[s] = queue_counts.get(s, 0) + 1

            # Прочие — не прошли, не на замену, не в очереди, не None
            all_known = set(VERIFIED_STATUSES) | {NA_ZAMENU} | set(QUEUE_STATUSES)
            others = [r for r in dval if r["account_status"] and
                      r["account_status"] not in all_known]
            other_counts = {}
            for r in others:
                s = r["account_status"]
                other_counts[s] = other_counts.get(s, 0) + 1

            ban_counts = {}
            for r in failed:
                bt = r["type_ban"]
                if bt:
                    ban_counts[bt] = ban_counts.get(bt, 0) + 1
            no_reason = sum(1 for r in failed if not r["type_ban"])

            bans = {}
            for bt in BAN_TYPES:
                n = ban_counts.get(bt, 0)
                if n > 0:
                    bans[bt] = {"n": n, "pct": pct(n, len(failed))}
            if no_reason > 0:
                bans["Без причины"] = {"n": no_reason, "pct": pct(no_reason, len(failed))}

            docs.append({
                "doc": doc,
                "total": len(dg),
                "valid": len(dval),
                "valid_pct": pct(len(dval), len(dg)),
                "passed": len(passed),
                "failed": len(failed),
                "queued": len(queued),
                "queue_counts": queue_counts,
                "others": other_counts,
                "vna": total_vna,
                "not_yet": not_yet,
                "success_pct": pct(len(passed), total_vna),
                "bans": bans,
            })

        # Минимальная дата создания среди задач этой закупки
        dates = [int(r.get("date_created") or 0) for r in group if r.get("date_created")]
        min_date = min(dates) if dates else 0

        # Причины потерь на фарме
        pustishka = sum(1 for r in group_f if r["internal_status"] == "no valid при заведении (пустышка)")
        after1 = sum(1 for r in group_f if r["internal_status"] == "no valid - после 1 логина")
        after_warm = sum(1 for r in group_f if r["internal_status"] == "no valid - после прогрева")

        purchases.append({
            "id": str(id_buy),
            "gmail": gmail,
            "total": total,
            "real_total": real_totals.get(id_buy, total),
            "valid": len(val),
            "invalid": len(inval),
            "valid_pct": pct(len(val), total),
            "pustishka": pustishka,
            "after1": after1,
            "after_warm": after_warm,
            "reserve": reserve,
            "reserve_mar": reserve_mar,
            "reserve_apr": reserve_apr,
            "docs": docs,
            "date_created_ms": min_date,
        })

    # Сортируем по дате создания + ID
    purchases.sort(key=lambda x: (x["date_created_ms"], int(x["id"]) if x["id"].isdigit() else 0))
    return purchases, {"mar": reserve_mar_global, "apr": reserve_apr_global}

# ─── СТАТИСТИКА ПО БАЕРАМ ────────────────────────────────────
def compute_buyers_data(rows, date_start_ms=None, date_end_ms=None):
    if date_start_ms is None:
        date_start_ms = 1772323200000
    if date_end_ms is None:
        date_end_ms = int(datetime.now().timestamp() * 1000)

    # Берём только аккаунты прошедшие фарм (Выдан) в нужном диапазоне дат
    accounts = []
    for r in rows:
        dc = int(r.get("date_created") or 0)
        if not (date_start_ms <= dc <= date_end_ms):
            continue
        if r["internal_status"] not in VALID_INTERNAL:
            continue
        accounts.append(r)

    by_buyer = {}
    for r in accounts:
        if not r["buyer"]:  # без баера не считаем
            continue
        by_buyer.setdefault(r["buyer"], []).append(r)

    buyers = []
    for buyer, group in sorted(by_buyer.items()):
        # Разбивка по account_status
        status_counts = {}
        for r in group:
            s = r["account_status"] or "Нет статуса"
            status_counts[s] = status_counts.get(s, 0) + 1

        # Группировка по 4 категориям
        passed   = sum(1 for r in group if r["account_status"] in VERIFIED_STATUSES)
        na_zam   = sum(1 for r in group if r["account_status"] == NA_ZAMENU)
        queue_upper = [s.upper() for s in QUEUE_STATUSES]
        queued   = sum(1 for r in group if r["account_status"] and r["account_status"].strip().upper() in queue_upper)
        all_known = set(VERIFIED_STATUSES) | {NA_ZAMENU} | set(QUEUE_STATUSES)
        others   = sum(1 for r in group if r["account_status"] and r["account_status"] not in all_known)
        no_status = sum(1 for r in group if not r["account_status"])
        vna_total = passed + na_zam

        # Разбивка по doc seller
        by_doc = {}
        for r in group:
            doc = r["doc_seller"] or "—"
            by_doc.setdefault(doc, []).append(r)

        doc_stats = []
        for doc, dg in sorted(by_doc.items()):
            dp = sum(1 for r in dg if r["account_status"] in VERIFIED_STATUSES)
            df = sum(1 for r in dg if r["account_status"] == NA_ZAMENU)
            dq = sum(1 for r in dg if r["account_status"] and r["account_status"].strip().upper() in queue_upper)
            do = sum(1 for r in dg if r["account_status"] and r["account_status"] not in all_known)
            dvna = dp + df
            # Причины замены
            failed_rows = [r for r in dg if r["account_status"] == NA_ZAMENU]
            ban_counts = {}
            for r in failed_rows:
                bt = r["type_ban"] or "Без причины"
                ban_counts[bt] = ban_counts.get(bt, 0) + 1
            doc_stats.append({
                "doc": doc,
                "total": len(dg),
                "passed": dp,
                "failed": df,
                "queued": dq,
                "others": do,
                "vna": dvna,
                "success_pct": pct(dp, dvna),
                "bans": ban_counts,
            })

        # Разбивка по gmail seller
        by_gmail = {}
        for r in group:
            gmail = r["gmail_seller"] or "—"
            by_gmail.setdefault(gmail, []).append(r)

        gmail_stats = []
        for gmail, gg in sorted(by_gmail.items()):
            gp = sum(1 for r in gg if r["account_status"] in VERIFIED_STATUSES)
            gf = sum(1 for r in gg if r["account_status"] == NA_ZAMENU)
            gvna = gp + gf
            gmail_stats.append({
                "gmail": gmail,
                "total": len(gg),
                "passed": gp,
                "failed": gf,
                "vna": gvna,
                "success_pct": pct(gp, gvna),
            })
        # Сортируем по % успеха (лучшие первыми)
        gmail_stats.sort(key=lambda x: x["success_pct"], reverse=True)

        buyers.append({
            "buyer": buyer,
            "total": len(group),
            "passed": passed,
            "failed": na_zam,
            "queued": queued,
            "others": others,
            "no_status": no_status,
            "vna": vna_total,
            "success_pct": pct(passed, vna_total),
            "status_counts": status_counts,
            "by_doc": doc_stats,
            "by_gmail": gmail_stats,
        })

    # Сортируем по количеству аккаунтов
    buyers.sort(key=lambda x: x["total"], reverse=True)
    return buyers

# ─── ОБНОВЛЕНИЕ HTML ─────────────────────────────────────────
def update_html(data, buyers_data, html_content, buyers_mar=None, buyers_apr=None, reserve_totals=None):
    new_data_str = "const DATA = " + json.dumps(data, ensure_ascii=False) + ";"
    updated = re.sub(r"const DATA = \[.*?\];", new_data_str, html_content, flags=re.DOTALL)
    new_buyers_str = "const BUYERS_DATA = " + json.dumps(buyers_data, ensure_ascii=False) + ";"
    updated = re.sub(r"const BUYERS_DATA = \[.*?\];", new_buyers_str, updated, flags=re.DOTALL)
    if buyers_mar is not None:
        new_buyers_mar_str = "const BUYERS_DATA_MAR = " + json.dumps(buyers_mar, ensure_ascii=False) + ";"
        updated = re.sub(r"const BUYERS_DATA_MAR = \[.*?\];", new_buyers_mar_str, updated, flags=re.DOTALL)
    if buyers_apr is not None:
        new_buyers_apr_str = "const BUYERS_DATA_APR = " + json.dumps(buyers_apr, ensure_ascii=False) + ";"
        updated = re.sub(r"const BUYERS_DATA_APR = \[.*?\];", new_buyers_apr_str, updated, flags=re.DOTALL)
    if reserve_totals is not None:
        new_rt_str = "const RESERVE_TOTALS = " + json.dumps(reserve_totals, ensure_ascii=False) + ";"
        updated = re.sub(r"const RESERVE_TOTALS = \{.*?\};", new_rt_str, updated, flags=re.DOTALL)
    # Обновляем дату в заголовке
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    updated = re.sub(
        r"Почты → фарм → аккаунты → верификация, обновлено [^<]+",
        f"Почты → фарм → аккаунты → верификация, обновлено {now}",
        updated
    )
    return updated

# ─── GITHUB ──────────────────────────────────────────────────
def get_github_file():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        sha = data["sha"]
        return content, sha
    else:
        print(f"Ошибка получения файла из GitHub: {resp.status_code}")
        return None, None

def push_to_github(html_content, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    payload = {
        "message": f"Обновление дашборда {now}",
        "content": base64.b64encode(html_content.encode("utf-8")).decode("utf-8"),
        "sha": sha
    }
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        print(f"Дашборд успешно обновлён на GitHub!")
        print(f"Ссылка: https://roseahmar.github.io/stats-ban/")
    else:
        print(f"Ошибка публикации на GitHub: {resp.status_code}")
        print(resp.text)

# ─── MAIN ────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("Обновление дашборда")
    print("=" * 50)

    # 1. Загружаем задачи из ClickUp
    tasks = fetch_all_tasks()
    if not tasks:
        print("Нет задач — выходим.")
        return

    # 2. Парсим
    print("Парсю поля задач...")
    rows = parse_tasks(tasks)

    # Показываем первые несколько для проверки полей
    print("\nПример первых 3 задач (проверь что поля читаются правильно):")
    for r in rows[:3]:
        print(f"  {r['name'][:40]:40} | internal={r['internal_status']} | gmail={r['gmail_seller']} | doc={r['doc_seller']} | acc_status={r['account_status']} | id_buy={r['id_buy']}")

    # 3. Считаем статистику
    print("\nСчитаю статистику...")
    data, reserve_totals = compute_data(rows)
    print(f"Закупок найдено: {len(data)}")
    # April 1, 2026 00:00:00 Europe/Brussels (UTC+2) = March 31, 2026 22:00:00 UTC
    APRIL_1_MS = 1774994400000
    buyers_data = compute_buyers_data(rows)
    buyers_mar = compute_buyers_data(rows, date_end_ms=APRIL_1_MS - 1)
    buyers_apr = compute_buyers_data(rows, date_start_ms=APRIL_1_MS)
    print(f"Баеров найдено: {len(buyers_data)} (март: {len(buyers_mar)}, апрель: {len(buyers_apr)})")

    # 4. Генерируем превью HTML локально
    print("\nГенерирую превью HTML...")
    template_path = "dashboard_v5_4.html"
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    updated_html = update_html(data, buyers_data, html_content, buyers_mar=buyers_mar, buyers_apr=buyers_apr, reserve_totals=reserve_totals)

    # Сохраняем локально для превью
    with open("dashboard_preview.html", "w", encoding="utf-8") as f:
        f.write(updated_html)
    print("Превью сохранено: dashboard_preview.html")
    print("Открой этот файл в браузере чтобы проверить.")
    print()

    # Публикация на GitHub — раскомментируй когда готово:
    # print("Публикую на GitHub...")
    # _, sha = get_github_file()
    # push_to_github(updated_html, sha)
    # print(f"Ссылка: https://roseahmar.github.io/stats-ban/")

    print("Готово! (GitHub не обновлён — режим превью)")

if __name__ == "__main__":
    main()
