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
FIELD_DATE_ZAMENA = "Дата 2-го логина"
FIELD_DATE_VYDACHI = "Дата выдачи"
FIELD_MB_TEAM = "MB Team"

# ─── СЕБЕСТОИМОСТЬ ───────────────────────────────────────────
# Цена 1 почты по ID_Buy (обновлять каждый месяц)
EMAIL_PRICE_BY_ID = {
    # Март (куплены в марте, выданы в апреле)
    5:  2.00, 6:  1.10, 7:  2.00, 8:  1.10, 9:  2.00,
    10: 1.10, 11: 1.10, 12: 2.00, 13: 2.00, 14: 2.00,
    15: 1.10, 16: 2.00, 17: 2.00, 18: 2.00, 19: 0.50,
    20: 1.10, 21: 1.10, 22: 2.00, 23: 0.00, 24: 1.10,
    25: 1.11, 26: 1.00, 27: 1.70, 28: 2.00, 29: 1.70,
    30: 2.30, 31: 2.20, 32: 1.70, 33: 3.07, 34: 3.07,
    35: 2.30, 36: 2.10, 37: 1.93, 38: 1.93, 39: 1.93,
    40: 1.03, 41: 1.70, 42: 1.03, 43: 2.00, 44: 1.00,
    45: 2.00, 46: 2.00, 47: 2.00, 48: 2.00, 49: 1.70,
    50: 1.78,
    # Апрель
    52: 3.05, 53: 2.00, 54: 2.00, 55: 2.00, 56: 2.87,
    57: 1.39, 58: 2.30, 59: 2.00, 60: 2.00, 61: 2.45,
    62: 2.12, 63: 2.12, 64: 2.12, 65: 2.00, 66: 2.00,
    67: 2.00, 68: 2.00, 69: 2.45, 70: 2.45, 71: 0.00,
    72: 2.12, 73: 2.12, 74: 2.08, 75: 2.08, 76: 2.50,
    77: 2.50, 78: 2.22, 79: 2.22, 80: 2.22, 81: 2.22,
    82: 2.22, 83: 2.29, 84: 2.29, 85: 2.09, 86: 2.09,
    87: 2.30, 88: 2.30, 89: 2.30, 90: 2.30, 91: 1.91,
    92: 2.37, 93: 2.37, 94: 2.39, 95: 2.13, 96: 2.36,
    97: 2.36, 98: 1.88,
}
DOC_PRICE_BY_SELLER = {'1-k1': 7.0, '3-lod': 5.5, 'Fels': 7.0, '6-artmak': 7.0, '': 7.0}
PROXY_COST   = 1.77
NO_ID_FLAT   = 9.0

def compute_cost_stats(rows, date_start_ms, date_end_ms):
    """Считает среднюю себестоимость платных / замен / общую."""
    apr = [r for r in rows
           if date_start_ms <= int(r.get("date_vydachi_ms") or 0) < date_end_ms
           and r.get("internal_status") in VALID_INTERNAL]
    if not apr:
        return None
    paid_costs, zamena_costs = [], []
    for r in apr:
        id_buy_raw = r.get("id_buy")
        doc_seller = r.get("doc_seller") or ""
        is_zamena  = r.get("has_zamena_tag", False)
        if not id_buy_raw:
            cost = NO_ID_FLAT
        else:
            try:
                id_buy = int(id_buy_raw)
            except Exception:
                id_buy = None
            if id_buy is None or id_buy not in EMAIL_PRICE_BY_ID:
                cost = NO_ID_FLAT
            else:
                doc_key = doc_seller if doc_seller in DOC_PRICE_BY_SELLER else ""
                cost = EMAIL_PRICE_BY_ID[id_buy] + DOC_PRICE_BY_SELLER[doc_key] + PROXY_COST
        if is_zamena:
            zamena_costs.append(cost)
        else:
            paid_costs.append(cost)
    all_costs = paid_costs + zamena_costs
    return {
        "avg_paid":   round(sum(paid_costs)   / len(paid_costs),   2) if paid_costs   else None,
        "avg_zamena": round(sum(zamena_costs) / len(zamena_costs), 2) if zamena_costs else None,
        "avg_total":  round(sum(all_costs)    / len(all_costs),    2) if all_costs    else None,
        "count_paid":   len(paid_costs),
        "count_zamena": len(zamena_costs),
        "count_total":  len(all_costs),
    }

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
ZAMENEN = "Заменен"
FAILED_STATUSES = (NA_ZAMENU, ZAMENEN)
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

def get_field_raw_date(task, field_name):
    """Возвращает сырое числовое значение date-поля (timestamp ms)."""
    for f in task.get("custom_fields", []):
        if f.get("name", "").lower() == field_name.lower():
            val = f.get("value")
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return None
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
            "mb_team": get_field(t, FIELD_MB_TEAM),
            "has_zamena_tag": any(tag.get("name", "").lower() == "zamena" for tag in t.get("tags", [])),
            "date_zamena_ms": int(get_field_raw_date(t, FIELD_DATE_ZAMENA) or 0),
            "date_vydachi_ms": int(get_field_raw_date(t, FIELD_DATE_VYDACHI) or 0),
        }
        rows.append(row)
    return rows

# ─── ПОДСЧЁТ СТАТИСТИКИ ──────────────────────────────────────
def pct(n, base):
    return round(n / base * 100, 1) if base > 0 else 0

def compute_data(rows):
    # Фильтр по дате создания задачи: 1 марта 2026 — сейчас
    DATE_START_MS = 1772319600000  # March 1 2026 00:00 Europe/Brussels (UTC+1)
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

    # Глобальный тотал (все задачи в периоде, как в ClickUp)
    total_mar_global = sum(1 for r in rows if DATE_START_MS <= int(r.get("date_created") or 0) < APR_SPLIT)
    total_apr_global = sum(1 for r in rows if APR_SPLIT <= int(r.get("date_created") or 0) <= DATE_END_MS)

    # Глобальное "произведено" — все Выдан в периоде (включая без buyer/ID_buy)
    produced_mar_global = sum(1 for r in rows
                              if DATE_START_MS <= int(r.get("date_created") or 0) < APR_SPLIT
                              and r.get("internal_status") in VALID_INTERNAL)
    produced_apr_global = sum(1 for r in rows
                              if APR_SPLIT <= int(r.get("date_created") or 0) <= DATE_END_MS
                              and r.get("internal_status") in VALID_INTERNAL)

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

        # Новая логика валидности фарма: прошли / (прошли + провалили), без "не проверено"
        FARM_PASS = ("Выдан", "DONE", "на выдачу", "На выдачу")
        passed_farm = [r for r in group if r["gmail_seller"] and r["internal_status"] in FARM_PASS]
        not_checked = sum(1 for r in group if r["gmail_seller"] and not r["internal_status"])
        farm_checked = len(passed_farm) + len(inval)
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
            failed = [r for r in dval if r["account_status"] in FAILED_STATUSES]
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
            "passed_farm": len(passed_farm),
            "not_checked": not_checked,
            "valid_pct": pct(len(passed_farm), farm_checked),
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
    return purchases, {"mar": reserve_mar_global, "apr": reserve_apr_global,
                       "total_mar": total_mar_global, "total_apr": total_apr_global,
                       "produced_mar": produced_mar_global, "produced_apr": produced_apr_global}

# ─── СТАТИСТИКА ПО БАЕРАМ ────────────────────────────────────
def compute_buyers_data(rows, date_start_ms=None, date_end_ms=None):
    if date_start_ms is None:
        date_start_ms = 1772323200000
    if date_end_ms is None:
        date_end_ms = int(datetime.now().timestamp() * 1000)

    # Zamena counts по дате физической выдачи (date_vydachi_ms)
    zamena_by_buyer = {}
    for r in rows:
        if not r.get("has_zamena_tag"):
            continue
        dz = int(r.get("date_vydachi_ms") or 0)
        if not dz or not (date_start_ms <= dz <= date_end_ms):
            continue
        buyer = r.get("buyer")
        if buyer:
            zamena_by_buyer[buyer] = zamena_by_buyer.get(buyer, 0) + 1

    # Берём только аккаунты прошедшие фарм (Выдан), фильтр по Дата выдачи
    accounts = []
    for r in rows:
        dv = int(r.get("date_vydachi_ms") or 0)
        if not dv or not (date_start_ms <= dv <= date_end_ms):
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
        na_zam   = sum(1 for r in group if r["account_status"] in FAILED_STATUSES)
        zamena_count = zamena_by_buyer.get(buyer, 0)
        queue_upper = [s.upper() for s in QUEUE_STATUSES]
        queued   = sum(1 for r in group if r["account_status"] and r["account_status"].strip().upper() in queue_upper)
        all_known = set(VERIFIED_STATUSES) | set(FAILED_STATUSES) | set(QUEUE_STATUSES)
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
            df = sum(1 for r in dg if r["account_status"] in FAILED_STATUSES)
            dq = sum(1 for r in dg if r["account_status"] and r["account_status"].strip().upper() in queue_upper)
            do = sum(1 for r in dg if r["account_status"] and r["account_status"] not in all_known)
            dvna = dp + df
            # Причины замены
            failed_rows = [r for r in dg if r["account_status"] in FAILED_STATUSES]
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
            gf = sum(1 for r in gg if r["account_status"] in FAILED_STATUSES)
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

        # MB Team — берём самое частое значение среди аккаунтов баера
        mb_teams = [r.get("mb_team") for r in group if r.get("mb_team")]
        mb_team = max(set(mb_teams), key=mb_teams.count) if mb_teams else None

        buyers.append({
            "buyer": buyer,
            "mb_team": mb_team,
            "total": len(group),
            "passed": passed,
            "failed": na_zam,
            "zamena_count": zamena_count,
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

# ─── СТАТИСТИКА ПО DOC SELLERS ───────────────────────────────
def compute_doc_sellers_data(rows, date_start_ms=None, date_end_ms=None):
    if date_start_ms is None:
        date_start_ms = 1772323200000
    if date_end_ms is None:
        date_end_ms = int(datetime.now().timestamp() * 1000)

    accounts = []
    for r in rows:
        dv = int(r.get("date_vydachi_ms") or 0)
        if not dv or not (date_start_ms <= dv <= date_end_ms):
            continue
        if r["internal_status"] not in VALID_INTERNAL:
            continue
        accounts.append(r)

    by_seller = {}
    for r in accounts:
        doc = r.get("doc_seller") or "—"
        by_seller.setdefault(doc, []).append(r)

    queue_upper = [s.upper() for s in QUEUE_STATUSES]
    all_known = set(VERIFIED_STATUSES) | set(FAILED_STATUSES) | set(QUEUE_STATUSES)
    sellers = []
    for seller, group in sorted(by_seller.items()):
        passed  = sum(1 for r in group if r["account_status"] in VERIFIED_STATUSES)
        failed  = sum(1 for r in group if r["account_status"] in FAILED_STATUSES)
        queued  = sum(1 for r in group if r["account_status"] and r["account_status"].strip().upper() in queue_upper)
        others  = sum(1 for r in group if r["account_status"] and r["account_status"] not in all_known)
        no_status = sum(1 for r in group if not r["account_status"])
        vna = passed + failed

        # Разбивка по баерам
        by_buyer = {}
        for r in group:
            b = r.get("buyer") or "—"
            by_buyer.setdefault(b, []).append(r)
        buyer_stats = []
        for buyer, bg in sorted(by_buyer.items()):
            bp = sum(1 for r in bg if r["account_status"] in VERIFIED_STATUSES)
            bf = sum(1 for r in bg if r["account_status"] in FAILED_STATUSES)
            bq = sum(1 for r in bg if r["account_status"] and r["account_status"].strip().upper() in queue_upper)
            bvna = bp + bf
            buyer_stats.append({
                "buyer": buyer,
                "total": len(bg),
                "passed": bp,
                "failed": bf,
                "queued": bq,
                "vna": bvna,
                "success_pct": pct(bp, bvna),
            })
        buyer_stats.sort(key=lambda x: x["total"], reverse=True)

        sellers.append({
            "seller": seller,
            "total": len(group),
            "passed": passed,
            "failed": failed,
            "queued": queued,
            "others": others,
            "no_status": no_status,
            "vna": vna,
            "success_pct": pct(passed, vna),
            "by_buyer": buyer_stats,
        })

    sellers.sort(key=lambda x: x["total"], reverse=True)
    return sellers

# ─── БИЛЛИНГ ─────────────────────────────────────────────────
def compute_billing_data(rows, date_start_ms, date_end_ms, price_per_account=16):
    from datetime import timezone, timedelta
    APR_SPLIT = 1774994400000

    # Аккаунты по дням (по Дата выдачи) — всё выданное баеру
    buyer_daily = {}
    for r in rows:
        dv = int(r.get("date_vydachi_ms") or 0)
        if not dv or not (date_start_ms <= dv <= date_end_ms):
            continue
        if r["internal_status"] not in VALID_INTERNAL:
            continue
        buyer = r.get("buyer")
        if not buyer:
            continue
        offset_h = 2 if dv >= APR_SPLIT else 1
        dt_local = datetime.fromtimestamp(dv / 1000, tz=timezone.utc) + timedelta(hours=offset_h)
        date_str = dt_local.strftime("%Y-%m-%d")
        if buyer not in buyer_daily:
            buyer_daily[buyer] = {}
        buyer_daily[buyer][date_str] = buyer_daily[buyer].get(date_str, 0) + 1

    # Замены по дате физической выдачи (date_vydachi_ms)
    zamena_by_buyer = {}
    zamena_daily_by_buyer = {}
    for r in rows:
        if not r.get("has_zamena_tag"):
            continue
        dz = int(r.get("date_vydachi_ms") or 0)
        if not dz or not (date_start_ms <= dz <= date_end_ms):
            continue
        buyer = r.get("buyer")
        if not buyer:
            continue
        zamena_by_buyer[buyer] = zamena_by_buyer.get(buyer, 0) + 1
        offset_h = 2 if dz >= APR_SPLIT else 1
        from datetime import timezone, timedelta as td
        dt_local = datetime.fromtimestamp(dz / 1000, tz=timezone.utc) + td(hours=offset_h)
        date_str = dt_local.strftime("%Y-%m-%d")
        if buyer not in zamena_daily_by_buyer:
            zamena_daily_by_buyer[buyer] = {}
        zamena_daily_by_buyer[buyer][date_str] = zamena_daily_by_buyer[buyer].get(date_str, 0) + 1

    # MB Team по баеру (самый частый)
    mb_team_by_buyer = {}
    for r in rows:
        buyer = r.get("buyer")
        team = r.get("mb_team")
        if buyer and team:
            mb_team_by_buyer.setdefault(buyer, []).append(team)

    all_buyers = set(buyer_daily.keys()) | set(zamena_by_buyer.keys())
    result = []
    for buyer in sorted(all_buyers):
        daily = buyer_daily.get(buyer, {})
        merged_daily = daily
        total_accounts = sum(merged_daily.values())
        zamenas = zamena_by_buyer.get(buyer, 0)
        paid = total_accounts - zamenas
        total = total_accounts
        amount = paid * price_per_account
        daily_list = sorted(
            [{"date": d, "count": c} for d, c in merged_daily.items()],
            key=lambda x: x["date"]
        )
        zamena_daily_dict = zamena_daily_by_buyer.get(buyer, {})
        zamena_daily_list = sorted(
            [{"date": d, "count": c} for d, c in zamena_daily_dict.items()],
            key=lambda x: x["date"]
        )
        teams = mb_team_by_buyer.get(buyer, [])
        mb_team = max(set(teams), key=teams.count) if teams else None
        result.append({
            "buyer": buyer,
            "mb_team": mb_team,
            "daily": daily_list,
            "zamena_daily": zamena_daily_list,
            "total_accounts": total_accounts,
            "paid": paid,
            "zamenas": zamenas,
            "total": total,
            "amount": amount,
        })
    result.sort(key=lambda x: x["total"], reverse=True)
    return result

def update_billing_html(billing_mar, billing_apr, html_content, cost_mar=None, cost_apr=None):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    updated = html_content.replace("<!-- UPDATE_DATE -->", now)
    updated = re.sub(r"const BILLING_MAR = \[.*?\];",
                     "const BILLING_MAR = " + json.dumps(billing_mar, ensure_ascii=False) + ";",
                     updated, flags=re.DOTALL)
    updated = re.sub(r"const BILLING_APR = \[.*?\];",
                     "const BILLING_APR = " + json.dumps(billing_apr, ensure_ascii=False) + ";",
                     updated, flags=re.DOTALL)
    updated = re.sub(r"const COST_STATS_MAR = .*?;",
                     "const COST_STATS_MAR = " + json.dumps(cost_mar, ensure_ascii=False) + ";",
                     updated, flags=re.DOTALL)
    updated = re.sub(r"const COST_STATS_APR = .*?;",
                     "const COST_STATS_APR = " + json.dumps(cost_apr, ensure_ascii=False) + ";",
                     updated, flags=re.DOTALL)
    return updated

# ─── ОБНОВЛЕНИЕ HTML ─────────────────────────────────────────
def update_html(data, buyers_data, html_content, buyers_mar=None, buyers_apr=None, reserve_totals=None,
                doc_sellers=None, doc_sellers_mar=None, doc_sellers_apr=None):
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
    if doc_sellers is not None:
        updated = re.sub(r"const DOC_SELLERS_DATA = \[.*?\];",
                         "const DOC_SELLERS_DATA = " + json.dumps(doc_sellers, ensure_ascii=False) + ";",
                         updated, flags=re.DOTALL)
    if doc_sellers_mar is not None:
        updated = re.sub(r"const DOC_SELLERS_DATA_MAR = \[.*?\];",
                         "const DOC_SELLERS_DATA_MAR = " + json.dumps(doc_sellers_mar, ensure_ascii=False) + ";",
                         updated, flags=re.DOTALL)
    if doc_sellers_apr is not None:
        updated = re.sub(r"const DOC_SELLERS_DATA_APR = \[.*?\];",
                         "const DOC_SELLERS_DATA_APR = " + json.dumps(doc_sellers_apr, ensure_ascii=False) + ";",
                         updated, flags=re.DOTALL)
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
    doc_sellers = compute_doc_sellers_data(rows)
    doc_sellers_mar = compute_doc_sellers_data(rows, date_end_ms=APRIL_1_MS - 1)
    doc_sellers_apr = compute_doc_sellers_data(rows, date_start_ms=APRIL_1_MS)
    print(f"Doc Sellers найдено: {len(doc_sellers)} (март: {len(doc_sellers_mar)}, апрель: {len(doc_sellers_apr)})")

    # 4. Считаем биллинг
    print("\nСчитаю биллинг...")
    DATE_START_MS = 1772319600000  # 1 марта 2026 00:00 UTC+1
    billing_mar = compute_billing_data(rows, date_start_ms=DATE_START_MS, date_end_ms=APRIL_1_MS - 1)
    billing_apr = compute_billing_data(rows, date_start_ms=APRIL_1_MS, date_end_ms=int(datetime.now().timestamp() * 1000))
    print(f"Биллинг: март={len(billing_mar)} баеров, апрель={len(billing_apr)} баеров")
    cost_mar = None  # цены за март пока не заданы
    cost_apr = compute_cost_stats(rows, date_start_ms=APRIL_1_MS, date_end_ms=int(datetime.now().timestamp() * 1000))
    print(f"Себестоимость апрель: платные=${cost_apr['avg_paid'] if cost_apr else '—'}, замены=${cost_apr['avg_zamena'] if cost_apr else '—'}")

    # 5. Генерируем дашборд HTML
    print("\nГенерирую дашборд HTML...")
    with open("dashboard_v5_4.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    updated_html = update_html(data, buyers_data, html_content, buyers_mar=buyers_mar, buyers_apr=buyers_apr,
                               reserve_totals=reserve_totals, doc_sellers=doc_sellers,
                               doc_sellers_mar=doc_sellers_mar, doc_sellers_apr=doc_sellers_apr)
    with open("dashboard_preview.html", "w", encoding="utf-8") as f:
        f.write(updated_html)
    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(updated_html)
    print("Сохранено: dashboard_preview.html, dashboard.html")

    # 6. Генерируем биллинг HTML
    print("Генерирую биллинг HTML...")
    with open("billing_template.html", "r", encoding="utf-8") as f:
        billing_tmpl = f.read()
    billing_html = update_billing_html(billing_mar, billing_apr, billing_tmpl, cost_mar=cost_mar, cost_apr=cost_apr)
    with open("billing_preview.html", "w", encoding="utf-8") as f:
        f.write(billing_html)
    with open("billing.html", "w", encoding="utf-8") as f:
        f.write(billing_html)
    print("Сохранено: billing_preview.html, billing.html")

    print("\nГотово! (GitHub не обновлён — режим превью)")

if __name__ == "__main__":
    main()
