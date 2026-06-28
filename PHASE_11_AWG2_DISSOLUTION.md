# Phase 11 — Растворение AWG2-вкладки

## Архитектурный принцип (важно)

**Tunnels-вкладка** — только про существование и жизненный цикл тоннелей:
создание, редактирование конфига, ключи, peers, deploy на VPS,
up/down/delete, статус (handshake/RX/TX), диагностика (speedtest).
**Никаких priorities, никаких fallback'ов, никакого "куда направить
трафик" — всё это не про Tunnel.**

**Routing-вкладка** — только про правила: какой трафик идёт в какой
тоннель и в каком порядке. Глобальные настройки маршрутизации
(killswitch / SNI / DNS chain / MTU clamp / trace) тоже тут.

Это разделение единственный способ не размазать одну ответственность
по двум вкладкам. Когда добавляется 6-й tunnel-kind, изменения в
Tunnels вкладке ограничены формой для нового kind'а; Routing вкладка
не трогается.

**Допустимое исключение в Tunnels**: per-peer `AllowedIPs` в форме —
это **WireGuard cryptokey-routing primitive** (что peer криптографически
принимает), а не routing-policy. Внешне выглядит как "роутинг", по
семантике это часть конфига тоннеля.

> **Признание**: после Phase 6 я оставил `frontend/src/features/awg2/AWG2.tsx`
> и весь его поддерево как есть, а параллельно поставил две новых вкладки
> «Туннели» / «Маршрутизация». Получилось дублирование: некоторые операции
> доступны и через старую и через новую вкладку, причём настройки в них
> хранятся в разных файлах (`awg.json` vs `tunnels.json` + `routing.json`).
> Это противоречит изначально согласованной протокол-агностичной модели.
>
> Phase 11 разносит **все** функции старой AWG2-вкладки по новым «Туннели»
> и «Маршрутизация» так, чтобы они работали единообразно для AmneziaWG /
> WireGuard / Hysteria, и затем удаляет легаси целиком.

## Карта функций AWG2 → новые вкладки

| Что в AWG2 | Куда переезжает | Замечания |
|---|---|---|
| Список серверов + кнопка «Добавить» | Уже в Tunnels | Готово (TunnelsList + AddTunnelModal) |
| Импорт `.conf` | Tunnels → AddTunnelModal | Сейчас отсутствует — добавить таб «Импорт» |
| Per-server SSH-deploy (генерация конфига на VPS) | Tunnels → TunnelDetail | Только для kinds с Provisioner (AWG/WG); Hysteria без deploy |
| Engine mode (userspace/kernel) | Tunnels → TunnelDetail | Per-AWG-tunnel, не глобально |
| Multitunnel toggle (1..4 ифейсов) | Tunnels → TunnelDetail | Per-AWG-tunnel |
| Configure server (host/port/user/key) | Tunnels → TunnelDetail → раздел «VPS» | Только для kinds с Provisioner |
| Configure tunnel (endpoint/keys/peers/obf) | Tunnels → TunnelDetail (уже в AwgForm) | AwgForm готов для add, нужен edit-mode |
| Per-client peers (gen/QR/export) | Tunnels → TunnelDetail → раздел «Клиенты» | Был PeerShareModal |
| SpeedTest tunnel-vs-direct | Tunnels → TunnelDetail | Был SpeedTestCard |
| QueueTile (tx queue health) | Tunnels → TunnelsList row OR detail | Опционально |
| Refresh status / last_handshake | Tunnels (UNCHANGED status block) | Уже в TunnelsList |
| ServerSummary (host/endpoint/connected) | Tunnels (UNCHANGED) | Уже есть |
| Per-server delete | Tunnels (UNCHANGED) | Уже есть × button |
| Per-server enable/disable | Tunnels → TunnelDetail | Сейчас только delete; нужен toggle |
| Mode (off/zones/full) | Routing → GlobalSettings | Уже в DefaultRule, но без явного UI-выбора режима |
| Zones list (Pi-hole-like) | Routing → RulesList | Готово (RulesList + RuleEditor) |
| MTU (`routing.mtu`) | Routing → GlobalSettings | Был в RoutingPane; не вариант per-rule |
| Killswitch | Routing → GlobalSettings | Глобальная защита от leak |
| SNI routing toggle | Routing → GlobalSettings | Подсетка SNI sniffer'а |
| DNS proxy mode + chain | Routing → GlobalSettings | Pi-hole integration |
| Domain source (resolve/dnsproxy) | Routing → GlobalSettings | Поведение matcher |
| TraceEnabled toggle | Routing → TracePane | Включает per-flow логирование |
| Apply / Commit / 90s-deadman | Routing → header кнопка «Применить» | Готово |
| Per-device routing | Routing → DevicesPane | Был DevicesRoutingPane (mode picker по MAC/IP) |
| Trace stream (DNS+SNI) | Routing → TracePane | Был отдельный таб TracePane |
| «Copy zones from server» | Routing → RulesList action | Был отдельный modal |
| «Insert rule at top» | Routing → RulesList action | Был отдельный кнопка |

## Под-фазы

### 11a — Феатурный inventory (этот документ)

- [x] Карта AWG2 → новые вкладки выше.
- [x] Список backend-endpoint'ов, которые надо мигрировать (см. ниже).
- [x] Список UI-компонентов которые надо перенести / переписать.

### 11b — Backend: per-tunnel endpoints

Каждая операция, которая раньше шла через `/api/awg2/...` с подразумеваемым
«активный сервер», теперь идёт через `/api/tunnels/{id}/...`. Активный
сервер как концепция уходит — у Registry все туннели равноправны, а
«какие сейчас UP» определяется per-tunnel статусом.

| Старое | Новое |
|---|---|
| `POST /api/awg2/servers/{id}/deploy` | `POST /api/tunnels/{id}/deploy` |
| `POST /api/awg2/servers/{id}/select` | (удалить — нет понятия active) |
| `POST /api/awg2/servers/{id}/enabled` | `PATCH /api/tunnels/{id}` `{enabled}` |
| `POST /api/awg2/engine/mode` | `PATCH /api/tunnels/{id}` `{config:{engine_mode}}` |
| `POST /api/awg2/multitunnel` | `PATCH /api/tunnels/{id}` `{config:{multitunnel}}` |
| `POST /api/awg2/peers` | `POST /api/tunnels/{id}/peers` |
| `DELETE /api/awg2/peers/{pid}` | `DELETE /api/tunnels/{id}/peers/{pid}` |
| `GET /api/awg2/peers/{pid}/config` | `GET /api/tunnels/{id}/peers/{pid}/config` |
| `POST /api/awg2/import` | `POST /api/tunnels/import` (kind определяется по content) |
| `POST /api/awg2/install` | `POST /api/tunnels/{id}/install` |
| `POST /api/awg2/config` | `PATCH /api/tunnels/{id}` `{config}` |
| `POST /api/awg2/client/up\|down` | `POST /api/tunnels/{id}/up\|down` (готово) |
| `POST /api/awg2/status/refresh` | `POST /api/tunnels/{id}/status/refresh` |
| `POST /api/awg2/speedtest` | `POST /api/tunnels/{id}/speedtest` (SSE) |
| `GET /api/awg2` (heavy status) | `GET /api/tunnels/{id}` (готово) |
| `GET /api/awg2/live` (counters) | `GET /api/tunnels/{id}/live` |

Реализация: каждое PATCH/POST/DELETE — тонкий handler, который через
`tunnel.Registry.Get(id)` находит тоннель, опционально берёт его
`tunnel.Tunnel.Manager()` (для AWG-семейства, через type assertion на
`awgTunnel.Manager()`), вызывает соответствующую существующую функцию
`awg.Manager` или `routing.Service.awgClient*OS`. Hysteria-туннели для
peer-related endpoint'ов возвращают 405 Method Not Allowed.

### 11c — Backend: routing globals + trace

Глобальные настройки маршрутизации (то, что раньше жило в
`awg.ServerConfig.Routing`) переезжают на уровень routing-сервиса и
персистятся в `routing.json` (а не в каждом сервере).

```go
// routing.json schema additions
type Settings struct {
    Killswitch    bool   `json:"killswitch"`
    SNIRouting    bool   `json:"sni_routing"`
    DNSChainEnabled bool `json:"dns_chain_enabled"`
    DomainSource  string `json:"domain_source"` // "resolve" | "dnsproxy"
    MTUClamp      int    `json:"mtu_clamp"` // 0 = no clamp
    TraceEnabled  bool   `json:"trace_enabled"`
}
```

Endpoint'ы:
- `GET /api/routing/settings` (готово через RulesView частично — расширить)
- `PATCH /api/routing/settings`
- `GET /api/routing/trace` (history, was /api/awg2/trace)
- `GET /api/routing/trace/status`
- `POST /api/routing/trace/enabled`
- `POST /api/routing/trace/clear`
- `GET /api/events/trace` (EventSource — уже существует, но прибит к awg2; переименовать алиас)
- `POST /api/routing/rules/copy` — было `awg2/routing/rules/copy`
- `POST /api/routing/rules/insert-top` — было

Миграция при чтении: `awg.json.servers[active].routing.*` → `routing.json.settings.*`
выполняется единожды одновременно с миграцией zones → rules в `migrateLegacy()`.

### 11d — Tunnels: TunnelDetail drawer

Per-tunnel detail-view, открывается кликом на строку в TunnelsList.
Содержимое разделено на табы внутри drawer'а.

> Напоминание про границу: ни одна вкладка drawer'а **не содержит**
> priority / fallback / "куда отправлять X" / RouteRule-related UI. Если
> хочешь обсуждать сюда такое — это сигнал что фича не туда.

1. **Обзор**
   - Идентификация (ID, kind badge, status dot)
   - Live counters (RX/TX, last_handshake, peer endpoint)
   - SpeedTest button — открывает встроенный card с NDJSON-progress
   - QueueTile (если линукс kmod выдаёт qdisc stats)
   - Datapath allocation (read-only): iface name, fwmark, table — это
     «как ядро видит этот тоннель», не routing rule.

2. **Конфигурация туннеля** (AWG: AwgForm в edit-mode; Hysteria: HysteriaForm в edit-mode)
   - Кнопка «Сохранить» → PATCH /api/tunnels/{id}
   - Per-AWG specific: engine mode (kernel/userspace) + multitunnel count + регенерация ключей через keypair endpoint

3. **VPS** (показывается только когда `Tunnel.Provisioner() != nil`)
   - SSH credentials (host/port/user/auth_kind/password/key_pem/known_key)
   - Deploy button — стримит progress через SSE
   - Last deploy result + per-step log

4. **Клиенты** (показывается только когда `Tunnel.Provisioner() != nil`, т.е. серверный туннель)
   - Список peers (без router peer)
   - Add peer (генерация ключа + автоназначение address)
   - Per-peer: edit name, QR code, export .conf/.vpn, delete

### 11e — Routing: GlobalSettings card

Сверху Routing-вкладки, прямо над RulesList:

```
┌─ Глобальные настройки ───────────────────────────────────┐
│  Killswitch       [ON ●]   Блокировать leak при tunnel down │
│  SNI routing      [ON ●]   Слушать TLS ClientHello для match│
│  DNS chain        [ON ●]   Pi-hole перехватывает LAN :53    │
│  Domain source    [DNS proxy▾]  Источник IP для domain rules│
│  MTU clamp        [1380]   0 = без clamp                    │
│  Trace            [OFF ○]  Per-flow логирование (производит.)│
└──────────────────────────────────────────────────────────┘
```

Toggle'ы → PATCH /api/routing/settings → routing.json → backend ре-аплаит
mangle chain через event-driven reconcile (Phase 8a).

### 11f — Routing: DevicesPane

Альтернативный вид для тех, кто думает в терминах устройств, не правил.
По сути это generator правил с MAC/IP-source-match.

```
┌─ Устройства (LAN) ───────────────────────────────────────┐
│ Phone (192.168.31.100, aa:bb:..)  [через tun-awg ▾] [fb:bypass▾] │
│ MacBook (192.168.31.50)            [direct ▾]                  │
│ srv (192.168.31.243)               [через tun-hys ▾] [fb:drop▾]│
└──────────────────────────────────────────────────────────┘
```

Изменение → синтезирует / редактирует rule с `src_ips=[192.168.31.100]`,
`action.tunnel_id=tun-awg-...`, `priority=100+row*10`, имя
`device:192.168.31.100`. На дисплее RulesList эти правила всё равно
видны, просто DevicesPane — короткий UI для повседневного use case.

Сейчас в роутинге уже есть `rule-z0-device192168318` — мигрированные
device-правила. DevicesPane просто даёт удобный view над ними.

### 11g — Routing: TracePane

Перетащить TracePane.tsx (568 строк) внутрь `features/routing/` и:
- Заменить `/api/awg2/trace/*` на `/api/routing/trace/*`
- Заменить `/api/events/trace` ничем (URL не меняется, просто переподписать handler в server.go).
- Заменить «вставить как rule» action на постинг RouteRule через POST /api/routing/rules.

### 11h — Routing: RulesList parity

Что не хватает в текущем RulesList vs legacy RulesTable:
- **Drag-reorder priority**: сейчас priority меняется только в editor. Добавить drag-handle колонку (react-dnd или нативный HTML5 dnd).
- **Copy from server**: «скопировать правила из конфига такого-то туннеля» — потому что когда у тебя 5 AWG-серверов, проще скопировать zones чем перебивать. Modal со списком туннелей → клон правил с переименованием на новый Action.TunnelID.
- **Insert at top**: «вставить новое с priority<всех существующих» — частая операция (правило-исключение поверх catch-all).
- **Pattern type hints**: визуальные badges «regex», «geosite», «list», «cidr» под доменами / IP / etc.

### 11i — Удаление AWG2 nav

```diff
- import AWG2 from "@/features/awg2/AWG2";
- awg2: { label: "AWG2 VPN", Component: AWG2, icon: ... },
- /* удалить из NAV_GROUPS */
```

И удалить весь `frontend/src/features/awg2/` каталог (~ 10 файлов,
~1700 строк TS/X).

### 11j — Удаление legacy backend

```diff
- m.HandleFunc("GET /api/awg2", ...)
- m.HandleFunc("GET /api/awg2/live", ...)
- m.HandleFunc("POST /api/awg2/servers", ...)
- /* 32 endpoint'a в server.go удалить */
```

И удалить из `routing/awgroute.go` всё с префиксом `AWG2*`:
- `AWG2Status` (вместо него TunnelSummary + RulesView)
- `AWG2ServerSummary`
- `AWG2DeployServerResult`
- `AWG2AddServer / AWG2SelectServer / AWG2SetServerEnabled / AWG2Import /
  AWG2DeleteServer / AWG2SetConfig / AWG2Deploy / AWG2DeployServer /
  AWG2DeployServers / AWG2RoutingConfig / AWG2RoutingApply / ...`

Перенести то что они делали в эквивалент через `tunnels.Registry.Get(id).Manager()`.

`internal/app/awg.go` тоже зачистить — type aliases `AWG2Status =
routing.AWG2Status` и делегаторы удалить.

### 11k — Cut over dual-engine shadow → single engine

Сейчас `routeFor` крутит legacy zone-engine и shadow rule-engine
параллельно, логирует расхождения. Когда AWG2 уйдёт:
- legacy `Zone` struct остаётся в `awg.ServerConfig.Routing.Zones` для
  миграции (но не используется в runtime)
- `zonesToRules()` остаётся как один-раз-при-чтении конвертер
- `compareShadow` / `shadowEquivalent` удаляются
- `Service.routeFor` напрямую делегирует в `routeForRules`
- `awgRouteState.routeTable` (старый) удаляется, остаётся только `ruleTable`

## Подсчёт работ

| Под-фаза | LOC backend | LOC frontend | Сложность |
|---|---|---|---|
| 11a inventory | — | — | done |
| 11b per-tunnel API | +800 | — | high (32 endpoints) |
| 11c routing globals | +400 | — | medium |
| 11d TunnelDetail | — | +1500 | very high (4 tabs × kind) |
| 11e GlobalSettings | — | +200 | low |
| 11f DevicesPane | — | +400 | medium |
| 11g TracePane | — | +600 (port + adapt) | medium |
| 11h RulesList parity | +50 | +400 | medium (drag+copy modal) |
| 11i drop AWG2 nav | — | -1700 | trivial |
| 11j drop legacy backend | -1200 | — | high (touching live code path) |
| 11k single engine | -300 | — | medium |
| **итого** | **~ +750 net** | **~ +1400 net** | **multi-day** |

## Порядок исполнения (предложение)

Делаем bottom-up, чтобы на каждом коммите всё работало:

1. **11b + 11c** (backend extensions) — добавляем новые endpoint'ы РЯДОМ
   с legacy. Старые UI продолжают работать. Phase 4 dual-shadow ловит,
   если мы где-то расходимся.
2. **11d** (TunnelDetail) — самая большая UI-работа. Открывает все
   per-tunnel операции в Tunnels-вкладке. После этого AWG2-ServerPane
   функционально дублируется. Старая вкладка ОСТАЁТСЯ.
3. **11e + 11f + 11g + 11h** (Routing parity) — закрываем feature gap.
   После этого функционально AWG2 не нужна.
4. **11i** (drop AWG2 nav) — убираем вкладку из nav. Файлы остаются на
   диске для возможного быстрого отката.
5. **11j** (drop legacy backend) — удаляем `/api/awg2/*` handler'ы
   только когда подтвердили что фронт не делает к ним fetch.
6. **11k** (single engine) — удаляем shadow-comparator и legacy
   Zone-walker. После этого `Service.routeFor` минимальный.

## Откат / safety

- Текущая ветка `feat/routing-multi-protocol` имеет 22 коммита + Phase 11
  будет ещё ~15-20.
- На каждой границе под-фазы коммит, чтобы можно было `git revert <range>`
  если что-то сломалось на прод-роутере.
- Шаг 11j (удаление legacy `/api/awg2/*`) — единственный действительно
  необратимый; делаем только когда 11d/e/f/g/h полностью верифицированы
  на прод-роутере (текущий деплой 1a3d8b3).
- Backup binary на роутере: `/opt/usr/bin/nfqws2-strategy.bak.preroutingrefactor`.
