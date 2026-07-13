# Panel Profiler / Probes — TODO

Замена overview-статусов на **латентностный профилировщик** каждого именованного code-path в селекторе. Цель — уметь ответить на вопросы вида "ASN resolve через ipmeta или через HTTP API — что быстрее?" за секунду в UI.

Не путать с текущим Overview/Dashboard (там state + counters). Здесь — count, throughput, p50/p95/p99 latency, err-rate, sparkline, compare mode.

---

## Архитектура

### 1. Ядро — `internal/tools/probe/`

Новый пакет. Один файл: `probe.go`.

```go
package probe

type Probe struct {
    Name     string      // "routing.decide", "asn.ipmeta", "iptables.restore"
    Group    string      // "routing" | "ipmeta" | "firewall" | "dns" | "sni" | "feeds" | ...
    ring     [1024]sample  // фиксированный размер — предсказуемая память
    head     atomic.Uint64 // wrapping index
    count    atomic.Uint64
    errs     atomic.Uint64
    lastNs   atomic.Int64  // last activity timestamp (unix ns)
}

type sample struct {
    ns  uint32 // latency в наносекундах (uint32 покрывает до ~4 сек — хватает)
    at  int64  // wall clock ns
    err bool
}

type Handle struct {
    p     *Probe
    start int64 // monotonic ns
}

func (p *Probe) Start() Handle {
    return Handle{p: p, start: nanotime()}
}

func (h Handle) End(err error) {
    dur := nanotime() - h.start
    if dur < 0 { dur = 0 }
    if dur > (1<<32)-1 { dur = (1<<32) - 1 }
    idx := h.p.head.Add(1) - 1
    h.p.ring[idx%1024] = sample{ns: uint32(dur), at: time.Now().UnixNano(), err: err != nil}
    h.p.count.Add(1)
    if err != nil { h.p.errs.Add(1) }
    h.p.lastNs.Store(time.Now().UnixNano())
}
```

- `nanotime()` через `//go:linkname runtime.nanotime` — быстрее `time.Since` (нет обёртки).
- Ring размер 1024 — компромисс: покрывает bursts, память ~10 KB на пробу × ~50 проб = 500 KB (пренебрежимо).
- Overhead: 2 nanotime + 1 atomic.Add + 1 memory-write ≈ 40-60 ns на вызов. Не помешает в hot-path.

**Global registry**:
```go
var registry sync.Map // map[string]*Probe

func Register(name, group string) *Probe { ... }  // идемпотентно; повторный Register(name) возвращает существующий

func All() []*Probe { ... }
```

**Percentiles on demand** — не streaming, а сортировка снапшота ring'а на GET (O(n log n) при n=1024 = быстрее любой сетевой ходки):
```go
type Snapshot struct {
    Name     string
    Group    string
    Count    uint64
    Errs     uint64
    LastNs   int64
    P50, P95, P99 uint32 // ns
    Mean, Max uint32
    Recent   [32]sample // последние 32 сэмпла для sparkline
}

func (p *Probe) Snapshot() Snapshot { ... }
```

### 2. Инструментация — где расставить пробы

Каждая проба = 2 строки: `h := probe.Start(p_xxx); defer h.End(err)`.

Готовые пробы (создаются в `init()` соответствующего пакета через `probe.Register`):

**routing** (`internal/services/routing/`):
- `routing.decide` — `routeFor()` / `routeForDst()` в `decision.go:117`
- `routing.compile` — `compileRouteRulesGen()` в `rule_engine.go:79`
- `routing.rebuild_shadow` — `rebuildShadowRuleTable()` в `rule_shadow.go:21`
- `routing.apply` — `awgApplyRoutingOS()` в `routing_linux.go:77`
- `routing.expand_entries` — `expandEntries()` в `expand.go:40`

**ipmeta** (`internal/tools/ipmeta/`):
- `ipmeta.lookup` — `Lookup(ip)` в `ipmeta.go:469`
- `ipmeta.cidrs_for_asn` — `CIDRsForASN()` в `ipmeta.go:372`
- `ipmeta.cidrs_for_country` — `CIDRsForCountry()` в `ipmeta.go:395`
- `ipmeta.rebuild` — `rebuild()` в `ipmeta.go:253`
- `ipmeta.read_asn_file` — `readAsnFile()` в `ipmeta.go:674`
- `ipmeta.load_cache` — `loadCache()` в `ipmeta.go` (найти линию)

**dns** (`internal/services/routing/dnsproxy_linux.go`):
- `dns.proxy_hop` — весь query pipeline (входящий UDP → upstream → респонс → traceAppend)
- `dns.upstream_call` — только HTTP/UDP к upstream'у
- `dns.cache_hit` / `dns.cache_miss` — счётчики (без latency; замерять через отдельные `probe.Register("dns.cache_hit"...)` + `.End(nil)` в fast-path)
- `dns.pihole_check` — `piholeWouldBlock()` вызов

**sni** (`internal/services/routing/snisniff_linux.go`):
- `sni.parse` — парсинг ClientHello
- `sni.decide` — routeForDst из sniffer'а
- `sni.pihole_verify` — piholeWouldBlock из sni-пути

**firewall** (`internal/services/routing/firewall_per_tunnel_linux.go`, `firewall_linux.go`):
- `firewall.ipset_add_async` — от ipsetAddAsync до реального применения
- `firewall.ipset_restore` — `ipset restore` batched
- `firewall.iptables_run` — каждый shell-out iptables/nft
- `firewall.per_tunnel_rebuild` — prepopulatePerTunnelIpsets

**awg / tunnel** (`internal/services/awgroute/`, `internal/services/routing/tunnel/`):
- `awg.client_up` — client_up вызов
- `awg.uapi_config_apply` — UAPI SetConfig
- `awg.iface_stats` — per-tick sysstats sample

**feeds** (`internal/app/app_feeds.go`):
- `feeds.fetch_asn_tsv` / `feeds.fetch_geoip_dat` / `feeds.fetch_geosite_dat` / `feeds.fetch_list` — per-kind
- `feeds.parse_asn_tsv` — parse-only latency (после fetch)
- `feeds.write_artefact` — disk write

**pihole** (`internal/services/pihole/`):
- `pihole.poll` — периодический poll containers
- `pihole.docker_exec` — shell-out в docker exec

**trace** (`internal/services/routing/trace.go`):
- `trace.append` — traceAppend путь (полезно понять сколько tracing стоит)
- `trace.lookup_matched_asn` — enrichment

**monitor / dashboard** (`internal/services/monitor/`):
- `monitor.dashboard_snapshot` — snapshot генерация
- `monitor.perf_tick` — perf sample

Всего ~35-45 проб. Инструментация — 1-2 дня механически.

### 3. HTTP API

Файл: `internal/server/probes_api.go`.

```
GET /api/probes                    → все пробы, снапшот всего
GET /api/probes/:name              → одна проба + последние 32 сэмпла
GET /api/probes/:name/samples?n=N  → сырые сэмплы (для custom-графиков)
GET /api/probes/stream (SSE)       → live-стрим агрегатов, 1 tick/sec
POST /api/probes/reset             → занулить ring (для чистого измерения)
POST /api/probes/reset/:name       → одну пробу
```

Схема JSON:
```json
{
  "probes": [
    {
      "name": "asn.ipmeta",
      "group": "ipmeta",
      "count": 1234,
      "errs": 0,
      "last_ns": 1783969552000000000,
      "p50_ns": 850,
      "p95_ns": 3200,
      "p99_ns": 12000,
      "mean_ns": 1100,
      "max_ns": 45000,
      "recent": [{"ns": 900, "at": 1783..., "err": false}, ...]
    },
    ...
  ]
}
```

SSE стрим шлёт тот же payload 1 раз в секунду с diff'ом от предыдущего (только изменившиеся пробы) — экономит трафик.

Регистрация в `server.go`:
```go
m.HandleFunc("GET /api/probes", etagBuffered(s.probesList))
m.HandleFunc("GET /api/probes/{name}", s.probeDetail)
m.HandleFunc("GET /api/probes/{name}/samples", s.probeSamples)
m.HandleFunc("GET /api/probes/stream", s.probesStream)
m.HandleFunc("POST /api/probes/reset", s.probesResetAll)
m.HandleFunc("POST /api/probes/reset/{name}", s.probesResetOne)
```

### 4. Frontend — новая вкладка "Probes" (или "Profiler")

**Новая top-level вкладка в главном layout'е** (рядом с Overview / Routing / DNS / Diag / Logs). Файлы:
- `frontend/src/features/probes/index.tsx` — контейнер, poll `/api/probes` + SSE
- `frontend/src/features/probes/ProbesTable.tsx` — основная таблица
- `frontend/src/features/probes/ProbeRow.tsx` — expandable row с sparkline
- `frontend/src/features/probes/CompareView.tsx` — compare mode (2-4 пробы наложенные)
- `frontend/src/features/probes/Sparkline.tsx` — минимальный inline SVG-график

**Таблица (default view)**:

| ☐ | Name | Group | Count/s | p50 | p95 | p99 | Err % | Last | Sparkline |
|---|------|-------|---------|-----|-----|-----|-------|------|-----------|

- Сортировка по любой колонке (SortableHead из shadcn).
- Search input (filter by name substring).
- Group filter (chips: routing / ipmeta / firewall / ...).
- Checkbox выделения (max 4) → кнопка "Compare (N)" сверху → CompareView.
- Rate: `count/s` считается как `(now.count - prev.count) / dt` из diff SSE.
- Sparkline: последние 32 сэмпла в мини-SVG (~60×20 px). Красный dot если err.

**Expandable row** (клик):
- Полный список последних 32 сэмплов таблицей (ns, wall-time, err).
- Кнопка "Reset probe" — POST /api/probes/reset/:name.
- Ссылка "View 1024" — GET /api/probes/:name/samples?n=1024, показывает scatter-plot (recharts или самописный canvas).

**CompareView** (модалка или отдельный роут `#probes/compare`):
- 2-4 выбранные пробы.
- Наложенные sparkline'ы (разные цвета).
- Таблица дельт: `probe A p50 vs probe B p50 → Δ = +42%`.
- "Winner" бейдж по каждой колонке (кто ниже — тот выигрывает).
- Кнопка "Copy comparison as markdown" — генерит markdown-таблицу для вставки в issue/notes.

**i18n keys** (в `frontend/src/i18n/ru.json` и `en.json`):
```
probes.title, probes.desc, probes.tabTitle,
probes.col.name, probes.col.group, probes.col.rate, probes.col.p50, probes.col.p95, probes.col.p99, probes.col.errPct, probes.col.last,
probes.action.compare, probes.action.reset, probes.action.viewSamples,
probes.compare.title, probes.compare.winnerBadge, probes.compare.exportMd,
probes.filter.hotOnly, probes.filter.search
```

### 5. Overhead-бюджет и наблюдения

- Пробы **всегда включены** (не gate'ится через флаг) — 40-60 ns × 1000 rps = 60 µs/sec суммарно. Незаметно.
- Если позже окажется, что одна проба стоит слишком дорого (например, `dns.proxy_hop` вызывается 10k rps) — глобальный флаг `probe.SetEnabled(false)` через `POST /api/probes/enabled` в API. `probe.Start` тогда возвращает пустой Handle с no-op End.
- Ring выделяется один раз при Register — GC не давит.
- Reset обнуляет `count`/`errs`/`head`, очищает ring — для чистого повторного бенчмарка (например, "тап Reset, курлани 100 раз, посмотри p50").

### 6. Порядок работы

Ветка: `feat/probes`.

1. **Ядро** (0.5 дня):
   - `internal/tools/probe/probe.go` — struct, ring, Register/All/Snapshot.
   - `internal/tools/probe/nanotime_linkname.go` — go:linkname на runtime.nanotime.
   - `internal/tools/probe/probe_test.go` — unit-тесты на percentile расчёт (feed 1000 known values, assert p50/p95/p99 в пределах ±1%).

2. **API** (0.5 дня):
   - `internal/server/probes_api.go` — 6 хэндлеров.
   - Регистрация роутов в `server.go`.
   - SSE-стрим по подписке (перерасчёт снапшота 1 раз/сек).

3. **Инструментация — routing/ipmeta первым** (1 день):
   - Только группы `routing` и `ipmeta` — это ядро, эффектив с точки зрения "asn resolve vs api".
   - Проверить в панели что данные капают, sparkline рисуется.

4. **Frontend MVP** (1-2 дня):
   - `ProbesTable` со всеми колонками, sortable, searchable.
   - `Sparkline` (простой SVG polyline).
   - Row expand с 32-sample таблицей.
   - SSE poll → live update.

5. **Compare mode** (1 день):
   - Checkbox выделение.
   - `CompareView` компонент с наложенными sparkline'ами и таблицей дельт.
   - Winner badge.
   - Copy-as-markdown.

6. **Остальная инструментация** (1 день):
   - Группы `firewall`, `dns`, `sni`, `feeds`, `pihole`, `trace`, `monitor`, `awg`, `tunnel`.
   - По одной группе за коммит.

7. **Полировка** (1 день):
   - Group-фильтры (chips).
   - "Hot only" фильтр (top-10 по count/s).
   - Reset-кнопки.
   - `View 1024` scatter-plot для одной пробы.
   - Persist expand-state и column-sort в hash/localStorage.

### 7. Non-goals (не делать в этом рано)

- Per-goroutine attribution через pprof labels — оверхед и сложнее визуализация. Отдельная фича если понадобится.
- Отправка метрик в Prometheus/Grafana — SSE в панели покрывает 90% use-case; экспортер добавим если станут нужны исторические графики за дни.
- Flame graphs / trace timelines — есть `go tool pprof` для этого, дублировать в панели не имеет смысла.
- Гистограммы (bucketed histograms типа Prometheus) — сортировка 1024 сэмплов быстрее и точнее, буденьт если понадобится > 10k samples/window.

### 8. Проверка на реальном примере "ASN resolve: ipmeta vs HTTP"

После шага 3:
1. В `expandOne` (rule_engine.go) обернуть вызов `ipmeta.CIDRsForASN` в `probe.Start("asn.ipmeta")`.
2. Написать одноразовый бенч-эндпоинт (или use debug/pprof `?benchmark=asn.http` param): дёрнуть `https://iptoasn.com/data/ip2asn-v4.tsv.gz` → парсить → лукап. Обернуть в `probe.Start("asn.iptoasn_http")`. (Или ложный тест: `probe.Start("asn.http")` + `time.Sleep(200*time.Millisecond)` для проверки инфраструктуры.)
3. Дёрнуть каждый эндпоинт по 200 раз.
4. Panel → Probes → checkbox обе → Compare → видим `p50: 850ns vs 180ms` → HTTP на 5 порядков медленнее.

---

## Файлы, которые тронем

- `internal/tools/probe/probe.go` (новый)
- `internal/tools/probe/nanotime_linkname.go` (новый)
- `internal/tools/probe/probe_test.go` (новый)
- `internal/server/probes_api.go` (новый)
- `internal/server/server.go` (регистрация роутов)
- ~30-45 файлов инструментации (по 2 строки каждый)
- `frontend/src/features/probes/index.tsx` (новый)
- `frontend/src/features/probes/ProbesTable.tsx` (новый)
- `frontend/src/features/probes/ProbeRow.tsx` (новый)
- `frontend/src/features/probes/CompareView.tsx` (новый)
- `frontend/src/features/probes/Sparkline.tsx` (новый)
- `frontend/src/App.tsx` — добавить вкладку Probes в NAV
- `frontend/src/i18n/{ru,en}.json` — новые ключи
- `frontend/src/types/api.ts` — типы ProbeSnapshot / ProbeSamples

---

## Оценка

- MVP (ядро + API + инструментация routing/ipmeta + таблица + sparkline): **3 дня**
- + Compare mode: **+1 день**
- + Полная инструментация всех подсистем: **+1 день**
- + Полировка (фильтры, scatter-plot, reset UX): **+1 день**

**Итого 5-6 дней от старта до "готово в проде".** MVP уже отвечает на исходный вопрос про ASN resolve — после 3 дней можно смотреть цифры.
