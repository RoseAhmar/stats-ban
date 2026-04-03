import requests

CLICKUP_TOKEN = "pk_81486271_BUO4L45L5J6DQHAK3DFSNFOAU3NKPYGD"
CLICKUP_LIST_ID = "901112676641"

DATE_START_MS = 1772323200000
DATE_END_MS   = 1775174399000

VALID_INTERNAL = ["Выдан"]

def fetch_all_tasks():
    headers = {"Authorization": CLICKUP_TOKEN}
    tasks = []
    for archived in [False, True]:
        page = 0
        while True:
            params = {
                "page": page, "limit": 100,
                "include_closed": "true", "subtasks": "true",
                "date_created_gt": DATE_START_MS,
                "date_created_lt": DATE_END_MS,
            }
            if archived:
                params["archived"] = "true"
            resp = requests.get(f"https://api.clickup.com/api/v2/list/{CLICKUP_LIST_ID}/task",
                                headers=headers, params=params)
            data = resp.json()
            batch = data.get("tasks", [])
            if not batch:
                break
            tasks.extend(batch)
            if data.get("last_page"):
                break
            page += 1
    # дедупликация
    seen = set()
    result = []
    for t in tasks:
        if t["id"] not in seen:
            seen.add(t["id"])
            result.append(t)
    return result

def get_field(task, name):
    for f in task.get("custom_fields", []):
        if f.get("name", "").lower() == name.lower():
            val = f.get("value")
            if val is None:
                return None
            ft = f.get("type", "")
            if ft == "drop_down":
                for o in f.get("type_config", {}).get("options", []):
                    if str(o.get("orderindex")) == str(val):
                        return o.get("name")
                return None
            if ft == "users":
                if isinstance(val, list) and val:
                    return val[0].get("username") or val[0].get("name")
                return None
            if ft in ("short_text", "text", "url", "email", "phone"):
                return str(val).strip() or None
            if isinstance(val, dict):
                return val.get("name") or val.get("label") or str(val)
            if isinstance(val, list):
                return val[0].get("name") if val else None
            return str(val).strip() or None
    return None

print("Загружаю задачи...")
tasks = fetch_all_tasks()
print(f"Всего задач: {len(tasks)}")

# Собираем все аккаунты: Выдан + buyer + в диапазоне дат
in_buyers = []
in_purchases = []

for t in tasks:
    dc = int(t.get("date_created") or 0)
    if not (DATE_START_MS <= dc <= DATE_END_MS):
        continue

    internal = get_field(t, "internal status")
    if internal not in VALID_INTERNAL:
        continue

    buyer  = get_field(t, "Баер (для кого)")
    gmail  = get_field(t, "Gmail Seller")
    id_buy = get_field(t, "ID_buy")

    if buyer:
        in_buyers.append({"name": t.get("name","")[:50], "buyer": buyer,
                          "gmail": gmail, "id_buy": id_buy})
    if buyer and gmail and id_buy:
        in_purchases.append(id_buy)

print(f"\nВ баерах (Выдан + buyer):     {len(in_buyers)}")
print(f"В закупках (Выдан + buyer + gmail + id_buy): {len(in_purchases)}")
print(f"Разница: {len(in_buyers) - len(in_purchases)}")

# Находим те что есть в баерах но не прошли фильтр закупок
missing = [r for r in in_buyers if not (r["gmail"] and r["id_buy"])]
if missing:
    print(f"\n=== {len(missing)} аккаунтов есть в баерах, но нет в закупках ===")
    print(f"{'Задача':<52} {'Баер':<20} {'Gmail':<10} {'ID_buy':<10}")
    print("-" * 95)
    for r in missing:
        print(f"{r['name']:<52} {r['buyer']:<20} {str(r['gmail']):<10} {str(r['id_buy']):<10}")
else:
    print("\nРазницы нет — все аккаунты с buyer имеют и gmail и id_buy.")
    print("Расхождение в числах скорее всего из-за краёв диапазона дат.")
