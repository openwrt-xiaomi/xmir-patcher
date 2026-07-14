# AWG2 selector — xray-rules + per-device roadmap

Цель: в AWG2-вкладке селектора `nfqws2-keenetic-strategy-selector` поддержать
формат правил Xray (для импорта существующих конфигов) **и** per-source-device
маршрутизацию, при этом туннелем остаётся AmneziaWG (amneziawg-go), не Xray.

Все изменения — в форке `feat/awg2` (или ветке от него), backend на Go,
UI правится в `internal/server/web/index.html` (vite single-file build).

## Phase 0 — per-source-device в zones

| Файл | Что |
|---|---|
| `internal/services/awg/config.go` | `Zone` → новое поле `SourceIPs []string `json:"source_ips"`` (опционально, пусто = вся сеть) |
| `internal/services/awgroute/firewall_linux.go` | при рендере mangle-правил: если `SourceIPs` непуст → для каждого IP `-s <ip>` перед `-j MARK` |
| `internal/services/awgroute/mode.go` (и `mode_test.go`) | покрыть тестом: одна зона с SourceIPs матчит только нужный IP |
| UI: `internal/server/web/index.html` | в форме зоны под доменами добавить поле «Источники (IP/CIDR)» + помощь «оставь пустым → для всех» |

**Готов критерий**: одна зона с `source_ips: ["192.168.31.243"]` и `*` в доменах
гонит ровно `.243` через awg0, остальные устройства идут напрямую.

## Phase 1 — geosite в zones + автообновление

### 1a. Geo доступен в awgroute

| Файл | Что |
|---|---|
| `internal/tools/geo/geo.go` | публичный метод `Enumerate(kind, category string) ([]string, error)` |
| `internal/app/app.go` | передать `*geo.Geo` в `awgroute.New(...)` |
| `internal/services/awgroute/awgroute.go` | хранить `geo *geo.Geo`, использовать на резолве |

### 1b. Префиксы в zone-парсере

В существующем поле «домены» зоны строки `geosite:CATEGORY`, `domain:foo.bar`,
`full:exact.bar` распознаются:

- `domain:foo.bar` → суффиксная маска (как `*.foo.bar`)
- `full:foo.bar` → ровный матч
- `geosite:CN` → разворачивается через `geo.Enumerate("geosite","cn")` на лету
  при `Apply()`. Если geosite.dat ещё не загружен → ошибка в `Apply`-ответ
  «загрузите geosite.dat или включи автообновление».
- `geoip:CN` → раскрывается в CIDR-список в существующее поле IPs.
- `list:NAME` → читает `/opt/etc/nfqws2/lists/NAME.list` (те же файлы что nfqws2
  использует для hostlist/ipset DPI-фильтров: `user`, `exclude`, `auto`,
  `ipset`, `ipset_exclude`). Распознавание IPs vs доменов по `isIPish()`.

| Файл | Что |
|---|---|
| `internal/services/awgroute/sets_linux.go` (или где идёт `range zone.Domains`) | новый helper `expandDomains(zone, geo) (plain []string, ips []string, err error)` |
| `internal/services/awg/match.go` | парсер префиксов |

### 1c. Фоновый фетчер

| Файл | Что |
|---|---|
| `internal/services/awgroute/awgroute.go` | в `New(...)` стартует goroutine с тикером (по умолчанию 24h, выкл если URL пуст) |
| `internal/services/awgroute/geo_fetch.go` (новый) | `func fetchGeo(ctx, url, kind) ([]byte, error)`, кладёт в существующий `Geo` store через `geo.Upload(...)` |
| `internal/services/awg/config.go` | новый блок `GeoUpdate { Enabled bool; GeositeURL, GeoipURL string; IntervalHours int; LastFetchedAt int64; LastError string }` в `ServerConfig` |

Дефолт URL: `https://github.com/v2fly/domain-list-community/releases/latest/download/geosite.dat`
и `https://github.com/v2fly/geoip/releases/latest/download/geoip.dat`.

### 1d. UI: панель «Geo»

В `index.html` (vite single-file, придётся `npm --prefix frontend run build`):

- В Routing tab над списком зон секция «GeoSite / GeoIP»:
  - текущая версия + `last_fetched_at`
  - две URL-поля (geosite/geoip), интервал в часах, тогл «авто»
  - кнопка «Обновить сейчас» → `POST /api/geo/fetch-now`
  - последняя ошибка (если была)

| Файл | Что |
|---|---|
| `internal/server/server.go` | новый `POST /api/geo/fetch-now`, ручка зовёт fetcher синхронно |
| `frontend/src/...` | компонент GeoPanel |
| `scripts/build.sh` | без изменений (vite-build уже есть) |

## Phase 2 — Xray JSON importer

### 2a. Endpoint

`POST /api/awg2/routing/import-xray` принимает:
```json
{"json": "<xray routing config text>", "dry_run": true}
```

Парсит `routing.rules`:
- `outboundTag: "proxy"` → Include-зона (в туннель)
- `outboundTag: "direct"` → Exclude-зона (мимо туннеля)
- `outboundTag: "block"` → в новую отдельную Drop-зону (опционально; иначе игнор с предупреждением)

Каждое правило раскидывается в `domains`/`ips` по типу:
- `domain` → строки `domain:`/`geosite:`/`regexp:` сохраняются с префиксом, парсер фазы 1 их расширит
- `ip` → CIDR в `ips`, `geoip:CN` сохраняется с префиксом
- `port`/`protocol`/`source`/`inboundTag` → не поддерживаем, в ответе
  `dropped: [{rule_index, reason}]`

### 2b. Конвертер regexp → wildcards

`internal/services/awg/xray_regex.go` (новый):

- `(^|\.)foo\.(com|ru)$` → `*.foo.com`, `*.foo.ru`
- `(^|\.)foo[a-z0-9-]*\.com$` → `*.foo*.com` (если поддержим), иначе сохранить как `regexp:` для фазы 3
- Сложнее — оставить как `regexp:` (фаза 3) с пометкой `lossy`

### 2c. UI: «Импорт Xray JSON»

В Routing tab кнопка → модалка с textarea (paste JSON):
- сначала dry_run, показывает preview:
  ```
  Зона proxy: 1247 доменов, 2 CIDR (выйдет в туннель)
  Зона direct: 156 доменов, 2 CIDR (мимо туннеля)
  Пропущено: 3 правила (port-based, inboundTag)
  ```
- кнопка «Применить» → второй POST без dry_run, заменяет существующие зоны

| Файл | Что |
|---|---|
| `internal/server/server.go` | новый handler |
| `internal/services/awg/xray_import.go` (новый) | парсер + конвертер |
| `internal/services/awg/xray_regex.go` (новый) | regexp → wildcards |
| `frontend/src/...` | компонент XrayImportDialog |

## Phase 3 — Regexp / keyword runtime

`iptables --match-set` работает по IP, а не по домену. Domain-уровневый матч идёт
через `snisniff_linux.go` (читает SNI из TCP ClientHello).

### 3a. Хранение скомпилированных матчеров

| Файл | Что |
|---|---|
| `internal/services/awg/config.go` | в `Zone` новые поля: `Regexps []string`, `Keywords []string` |
| `internal/services/awgroute/sni.go` | при `Apply` компилировать regexp'ы один раз, держать кэш |

### 3b. Матчер в SNI sniffer

| Файл | Что |
|---|---|
| `internal/services/awgroute/snisniff_linux.go` | в hot-path callback'е (когда пришёл SNI): проверка по compiled regexp + substring keyword'ам. Матч → resolve(SNI host) → запихнуть IP в существующий ipset `awgSetSNI` |

Текущая инфраструктура (MARK по ipset, ip rule, ip route, NAT) переиспользуется
как есть.

### 3c. UI

Тот же textarea зоны автоматически принимает строки:
```
regexp:^(.*\.)?yandex\.(ru|com)$
keyword:porn
```

Парсер 1b и 2b их раскидывает по `Regexps`/`Keywords` (не путать с `Domains`).

## Сборка / деплой

```sh
cd /tmp/nfqws2-sel
npm --prefix frontend install
npm --prefix frontend run build   # для фаз 1d, 2c
GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -trimpath -ldflags '-s -w' \
  -o /tmp/nfqws2-strategy ./cmd/nfqws2-strategy
scp /tmp/nfqws2-strategy root@192.168.31.1:/opt/usr/bin/nfqws2-strategy
ssh root@192.168.31.1 '
  kill $(pidof nfqws2-strategy) 2>/dev/null
  ( /opt/usr/bin/nfqws2-strategy serve </dev/null >/opt/var/log/nfqws2-strategy/serve.log 2>&1 & )
'
```

## Smoke-тесты после деплоя

1. Фаза 0: зона `{source_ips:[".243"], domains:["*"]}` → с .243 `ipinfo.io` показывает `185.209.21.51`, с другого устройства — реальный IP.
2. Фаза 1: импортить `geosite.dat`, зона с `geosite:cn` → доменов > 1000 в ответе `apply`.
3. Фаза 2: paste минимального xray JSON, dry_run, preview корректный.
4. Фаза 3: добавить `regexp:^(.*\.)?example\.com$`, открыть `https://sub.example.com` — IP попадает в ipset, трафик идёт в awg0.

## Что НЕ делаем (намеренно)

- `keyword:` substring через iptables `-m string` — пакеты могут быть фрагментированы, ложные срабатывания, не делаем
- `inboundTag` xray-стиля — у нас нет input-tag концепции, пропускаем с предупреждением
- `domainStrategy: IPIfNonMatch` и подобные — резолвим всё через выбранный `DomainSource`
- `port`/`protocol` правила — селектор работает на L3, не L4-routing, пропускаем
