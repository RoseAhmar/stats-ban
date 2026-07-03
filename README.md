# statsdoc — дашборд статистики ClickUp

Скрипт тянет задачи из ClickUp, считает статистику (закупки, баера, doc-sellers,
биллинг, верификация) и публикует 4 HTML-страницы на GitHub Pages:
<https://roseahmar.github.io/stats-ban/>

## Файлы

| Файл | Назначение |
|------|-----------|
| `update_dashboard.py` | Главный скрипт: выгрузка из ClickUp → расчёт → генерация HTML → пуш на GitHub |
| `dashboard_v5_4.html` | Шаблон дашборда (Закупки / Баера / Doc Sellers) |
| `billing_template.html` | Шаблон биллинга |
| `verif_template.html` | Шаблон верификаций |
| `index.html` | Главное меню сайта |
| `*_preview.html`, `dashboard.html`, `billing.html`, `verif.html` | Сгенерированные файлы (перезаписываются скриптом) |

Скрипт читает `*_template.html` / `dashboard_v5_4.html`, подставляет данные и
пишет результат в `*.html` + `*_preview.html`, после чего пушит их в репозиторий
`RoseAhmar/stats-ban` через GitHub API.

## Установка на новой машине (Mac + PyCharm)

1. **Клонировать репозиторий**
   ```bash
   git clone https://github.com/RoseAhmar/stats-ban.git statsdoc
   cd statsdoc
   ```

2. **Открыть в PyCharm** и создать виртуальное окружение
   (PyCharm предложит автоматически, либо вручную):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Установить зависимости**
   ```bash
   pip install -r requirements.txt
   ```

4. **Создать `.env`** — скопировать шаблон и вписать токены
   ```bash
   cp .env.example .env
   ```
   Затем открыть `.env` и подставить реальные значения
   (те же, что в `.env` на Windows-машине):
   ```
   CLICKUP_TOKEN=...
   GITHUB_TOKEN=...
   ```
   > `.env` в `.gitignore` и в репозиторий не попадает — токены нужно
   > перенести вручную.

5. **Запуск**
   ```bash
   python3 update_dashboard.py
   ```
   Скрипт выгрузит данные, обновит HTML и запушит их на GitHub Pages.

## Токены

- `CLICKUP_TOKEN` — Personal API Token из ClickUp (Settings → Apps).
- `GITHUB_TOKEN` — Personal Access Token с правом `repo` для пуша в `RoseAhmar/stats-ban`.

## Ключевые настройки в `update_dashboard.py`

- `CLICKUP_LIST_ID` — ID списка ClickUp с задачами.
- `GITHUB_REPO` — репозиторий для публикации.
- Константы дат `DATE_START_MS`, `APR_SPLIT`, `MAY_1_MS`, `JUN_1_MS` — границы месяцев
  (00:00 по Брюсселю). При добавлении нового месяца завести аналогичную метку.
- `MB_TEAM_OVERRIDE` — ручное переопределение MB Team для баеров.
- `EMAIL_PRICE_BY_ID` — себестоимость почт по `ID_buy`.
