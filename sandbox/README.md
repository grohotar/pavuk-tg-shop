# Песочница бота и мини-аппа

Полная копия прода у тебя на Mac. В настоящую панель, платёжки и на серверы ничего не ходит.

| Что | Прод | Песочница |
|---|---|---|
| Бот | `/root/pavuk-tg-shop` на панели, коммит `db90ef6`, Python 3.11 | `bot-sandbox`, тот же коммит + режим polling, Python 3.11, библиотеки один в один (`prod-requirements.lock`) |
| Мини-апп | образ maposia `4.0.1` на панели и на selec first, `app-config.json` смонтирован | `miniapp-sandbox`, исходники тега `v4.0.1`, Node 18.20.8, pnpm 10.11.0, тот же `app-config.json`, сборка как в Dockerfile |
| Панель | Remnawave 3.3.2 | `fake-panel.js`: те же адреса API; оформление страниц подписки — копия прода (`subpage_configs.json`) |
| База | Postgres 17 | локальный Postgres 17, тестовые данные (`seed.py`) |

## Где что работает

- **Бот** — на Mac, polling, отвечает только `ADMIN_IDS` и `SANDBOX_TESTER_IDS` (тестовые аккаунты без админки; `seed` даёт им подписку, истёкшую 5 дней назад). Чужие ID пишутся в лог: `SANDBOX: ignored update from …`. Тестовый бот @ppntestbot, токен в `.env`.
- **Мини-апп** — `https://ppn.na4u.ru` (netangels, контейнер c61358). Под Node 18.20.8, как в проде: хостинг даёт только 18.0.0, поэтому `hello.js` перезапускает приложение под `~/.nvm/versions/node/v18.20.8`. В сборке sharp для linux-x64 (сверен с lockfile).
- **Фейковая панель** — `https://ppn-panel.na4u.ru`, без ключа отвечает 401. Ключ — `PANEL_API_KEY` в `.env`. Просмотр мини-аппа в браузере: `https://ppn-panel.na4u.ru/frame?key=<PANEL_API_KEY>`.
- **База бота** — локальный Postgres 17 на Mac.

## Команды

```
sandbox/run.sh           запустить бота (Ctrl+C — остановить)
sandbox/run.sh seed      пересоздать тестовые данные (база на Mac + panel_state.json на хостинге)
sandbox/run.sh deploy    пересобрать мини-апп и выложить мини-апп и панель на netangels
sandbox/run.sh local     всё на Mac без хостинга, мини-апп в браузере: http://127.0.0.1:3999/frame
```

Проверить ответы панели схемами мини-аппа: в `miniapp-sandbox` выполнить
`PANEL_URL=https://ppn-panel.na4u.ru PANEL_KEY=<ключ> node sandbox/check-panel.js`.

## Чего песочница не проверяет

- Оплату: платёжки шлют ответы на адрес прода. Флоу до кнопки «оплатить» смотреть можно, а выдачу подписки после оплаты — через админку.
- Вебхуки панели (автопродление и уведомления за сутки до конца подписки).
- Настоящие подключения VPN: ссылки в мини-аппе фейковые.

## Раскатка в прод (каждый шаг — только после «да»)

**Бот.** Прод собирается на панели из `/root/pavuk-tg-shop` (`docker compose up -d --build`).
1. Коммит, push в GitHub, на сервере `git pull`. Режим polling в проде не включается: там задан `WEBHOOK_BASE_URL`.
2. Ловушка: в `requirements.txt` не закреплён `pydantic_settings` и транзитивные библиотеки. Свежая сборка подтянет новые версии, не те, что в проде и песочнице. Перед сборкой ставить из `sandbox/prod-requirements.lock` (поправить одну строку в Dockerfile).
3. Пересобрать только контейнер бота: `docker compose up -d --build --no-deps remnawave-tg-shop`. База не трогается, прерывание — секунды.
4. Если меняли `locales/`: в проде папка смонтирована, хватит `git pull` и перезапуска.

**Мини-апп.** Сейчас в проде чужой образ (maposia), поэтому для своей версии нужно:
1. Форк `maposia/remnawave-telegram-sub-mini-app` в свой GitHub, правки в ветке от `v4.0.1`.
2. Собрать свой образ (его Dockerfile) и в `/opt/remnawave-telegram-sub-mini-app/docker-compose.yml` заменить `image` — **на обоих серверах**: на панели и на selec first.
3. После смены конфигов подписки в панели мини-апп перезапускать: конфиги он читает только при старте.

## Отличия .env песочницы от прода (сделано нарочно)

- `MY_DEVICES_SECTION_ENABLED=False`, как в проде (14.11 пользователь решил раздел «Мои устройства» пока не использовать). Если включать: при пустом `osVersion` бот пишет «iOS None» — поправить в `bot/handlers/user/subscription/core.py`.
- `TRIAL_ENABLED=True` (в проде `False`): чтобы было что потыкать.
- Platega включена (СБП, «Карта МИР», автопродление `PLATEGA_SUBSCRIPTION_ENABLED=True`), но ходит в фейковую Platega в `fake-panel.js` (`PLATEGA_API_BASE_URL`). На её страницах «Оплатить» / «Отказаться» / «Оформить подписку» — деньги не списываются, а уведомления складываются в очередь; бот в песочнице забирает её раз в 2 с (`sandbox/platega_events.py`) и прогоняет через тот же `process_callback`, что вебхук прода. Управление автопродлениями (следующее списание, неудача, отмена клиентом): `https://ppn-panel.na4u.ru/platega?key=<PANEL_API_KEY>`. Очередь и подписки фейковой Platega живут в памяти — после `deploy` оформлять заново. Конспект настоящего API — `sandbox/PLATEGA.md`. В `platega_service.py` адрес API можно переопределить этой переменной; без неё — настоящий `https://app.platega.io`, так что в проде ничего не меняется.
- Остальные платёжки и уведомления выключены, `LOG_CHAT_ID` пустой.
