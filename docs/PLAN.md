# AI News — Mimari ve Uygulama Planı

> Yapay zeka haberlerini RSS kaynaklarından toplayan, uzun haberleri Gemini (Flash, ücretsiz katman) ile
> Türkçe özetleyen ve bir web arayüzünde sunan uygulama.
>
> Bu belge yaşayan bir plandır: her adım tamamlandıkça işaretlenir, kararlar değiştikçe güncellenir.

---

## 1. Hedefler ve Kapsam

**Hedefler**
- Birden fazla RSS kaynağından yapay zeka haberlerini düzenli olarak toplamak.
- Kısa haberleri olduğu gibi göstermek, **uzun** haberleri Gemini ile Türkçe özetlemek.
- Ücretsiz katmanın düşük rate limit'ine takılmadan, **kuyruk** mantığıyla özetlemek.
- Temiz, test edilmiş, belgelenmiş — portföyde gösterilebilir — bir proje.

**Kapsam dışı (şimdilik)**
- Kullanıcı hesapları / giriş sistemi (sadece basit bir admin API anahtarı olacak).
- Çoklu sunucu, dağıtık kuyruk (Redis/Celery). Tek süreç yeterli.
- Mobil uygulama.

---

## 2. Genel Mimari

```
                 ┌──────────────────────────── backend (FastAPI, tek süreç) ───────────────────────────┐
                 │                                                                                     │
 RSS kaynakları ─┼─► [Fetch job] ──► [Extract] ──► Article (DB) ──► [Summary queue worker] ──► Gemini   │
  (feedparser)   │   her 30 dk      trafilatura    status=pending     her ~N sn, 1 haber      API       │
                 │        ▲                              │                     │                        │
                 │        └──────── APScheduler ─────────┴─────────────────────┘                        │
                 │                                                                                     │
                 │   REST API (/api/...)  ◄──── SQLite (SQLModel) ────►  rate limiter + günlük kota    │
                 └───────────────▲─────────────────────────────────────────────────────────────────────┘
                                 │ JSON
                 ┌───────────────┴──────────── frontend (Vue 3 + Vite) ──────────────┐
                 │  Haber listesi · Haber detayı · Kaynak yönetimi · Kuyruk durumu    │
                 └────────────────────────────────────────────────────────────────────┘
```

Veri akışı tek yönlüdür: **topla → zenginleştir → kuyruğa koy → özetle → sun.**
Her aşama bir öncekinin çıktısını veritabanından okur; bu sayede bir aşama çökse bile diğerleri etkilenmez
ve uygulama yeniden başladığında kaldığı yerden devam eder.

---

## 3. Temel Tasarım Kararları

### 3.1 Kuyruk: Veritabanı tabanlı (Redis/Celery değil)

| Seçenek | Artı | Eksi |
|---|---|---|
| **DB tabanlı kuyruk (seçilen)** | Ek servis yok, kalıcı, öğrenmesi kolay, durum DB'de görünür | Çok yüksek hacimde yavaşlar |
| Celery + Redis | Endüstri standardı, ölçeklenir | Ekstra altyapı; bu hacim için gereksiz |
| Bellek içi `asyncio.Queue` | Çok basit | Süreç yeniden başlarsa kuyruk kaybolur |

Saatte birkaç düzine haber ve dakikada birkaç API isteğiyle sınırlıyız; darboğaz kuyruk değil, Gemini kotası.
Bu yüzden **`Article.summary_status` alanı kuyruğun kendisidir.**

**Durum makinesi:**

```
            (kısa içerik)
 new ───────────────────────► skipped
  │
  │ (uzun içerik)
  ▼
 pending ──► processing ──► done
  ▲              │
  │   (geçici    │ (kalıcı hata veya
  │    hata,     │  max deneme aşıldı)
  │   backoff)   ▼
  └─────────── failed
```

- Worker her çalıştığında `status=pending AND next_attempt_at <= now` olan **en eski** haberi alır.
- Geçici hata (429, 503, timeout) → `attempts += 1`, `next_attempt_at = now + backoff` (üstel: 1, 2, 4, 8 dk…), tekrar `pending`.
- Kalıcı hata (içerik engellendi, geçersiz yanıt) veya `attempts >= MAX_ATTEMPTS` → `failed`, hata mesajı kaydedilir.
- Uygulama açılışında `processing`'de takılı kalmış kayıtlar `pending`'e geri alınır (crash recovery).

### 3.2 Rate limit ve kota yönetimi

Ücretsiz katman limitleri Google tarafından zaman zaman değiştiriliyor; bu yüzden **hiçbir limit koda gömülmez**,
hepsi `.env` üzerinden ayarlanır (`GEMINI_RPM`, `GEMINI_DAILY_LIMIT` vb.). Kurulumda güncel değerler
Google AI Studio'daki rate limit sayfasından kontrol edilecek.

Üç katmanlı koruma:
1. **Zamanlama:** Worker `60 / GEMINI_RPM` saniyeden sık çalışmaz (biraz pay bırakarak).
2. **Günlük sayaç:** `ApiUsage` tablosunda gün başına istek sayısı tutulur; limite ulaşınca worker o gün durur.
3. **Reaktif:** 429 gelirse yanıttaki bekleme süresine (varsa) uyulur, yoksa üstel backoff uygulanır.

### 3.3 "Uzun haber" ne demek?

- RSS'teki `summary/description` genellikle kısa ve HTML'lidir. Asıl metin için haber URL'si **trafilatura** ile çekilir.
- Temizlenmiş metin `SUMMARY_MIN_CHARS` (ör. 1500 karakter) üzerindeyse → `pending`. Altındaysa → `skipped`.
- Gemini'ye gönderilen metin `SUMMARY_MAX_INPUT_CHARS` ile kırpılır (token tasarrufu).

### 3.4 Gemini çağrısı: yapılandırılmış çıktı

`google-genai` SDK'sı ile **structured output** (JSON şeması = Pydantic modeli) kullanılır. Böylece serbest metin
ayrıştırmak yerine doğrulanmış bir nesne alırız:

```text
SummaryResult:
  title_tr: str          # Türkçe başlık
  summary_tr: str        # 3–5 cümlelik özet
  key_points: list[str]  # 3–5 madde
```

Prompt ilkeleri: sadece verilen metne dayan, bilgi uydurma, teknik terimleri gerektiğinde orijinal haliyle bırak,
tarafsız haber dili kullan. Model adı `.env`'den gelir (`GEMINI_MODEL`), böylece yeni Flash sürümüne geçmek kod değişikliği gerektirmez.

### 3.5 Zamanlayıcı (APScheduler) nerede çalışacak?

- **Seçilen:** FastAPI'nin `lifespan` olayında başlatılan `BackgroundScheduler` (thread tabanlı). Tek komutla her şey çalışır.
- **Dikkat:** `uvicorn --workers 4` veya bazı reload senaryolarında her süreç kendi scheduler'ını başlatır → işler çift çalışır.
  Bu yüzden `SCHEDULER_ENABLED` ayarı olacak ve backend tek worker ile çalıştırılacak.
- **Alternatif (ileride):** Scheduler'ı ayrı bir `python -m app.worker` sürecine taşımak. Kod bu ayrıma uygun yazılacak
  (işler `services/` içinde, scheduler sadece onları çağırır).

### 3.6 Senkron mu, asenkron mu?

Arka plan işleri (RSS çekme, trafilatura, Gemini) thread'lerde **senkron** çalışacak; SQLModel oturumları da senkron.
Async SQLAlchemy + async scheduler daha "modern" görünür ama öğrenme maliyeti yüksek, bu hacimde getirisi yok.
API uçları da senkron `def` olacak (FastAPI bunları otomatik olarak thread havuzunda çalıştırır).

SQLite + thread'ler için: `check_same_thread=False`, **WAL modu** (okuma/yazma çakışmalarını azaltır) ve her iş için ayrı oturum.

### 3.7 Telif ve etik

- Arayüzde tam metin **gösterilmez**; sadece özet + orijinal habere bağlantı + kaynak adı.
- Çekme isteklerinde tanımlayıcı bir `User-Agent` kullanılır, kaynaklar makul aralıklarla çekilir.
- RSS için `ETag` / `Last-Modified` saklanır → değişmeyen feed tekrar indirilmez.

---

## 4. Veri Modeli (SQLModel)

**Feed**
| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| name | str | "OpenAI Blog" |
| url | str, unique | RSS adresi |
| site_url | str? | |
| is_active | bool | |
| etag, modified | str? | koşullu istek için |
| last_fetched_at | datetime? | |
| last_error | str? | |

**Article**
| Alan | Tip | Not |
|---|---|---|
| id | int PK | |
| feed_id | FK → Feed | |
| guid | str | feed'deki kimlik |
| url | str, unique | tekilleştirme anahtarı (normalize edilmiş) |
| title | str | orijinal başlık |
| author | str? | |
| published_at | datetime? | |
| rss_summary | str? | feed'deki kısa açıklama |
| content | str? | trafilatura metni (gösterilmez) |
| content_length | int | |
| title_tr, summary_tr | str? | Gemini çıktısı |
| key_points | JSON? | |
| summary_status | enum | new / pending / processing / done / skipped / failed |
| summary_attempts | int | |
| summary_error | str? | |
| next_attempt_at | datetime? | backoff için |
| summarized_at | datetime? | |
| model_used | str? | hangi model özetledi |
| created_at | datetime | |

İndeksler: `(summary_status, next_attempt_at)`, `published_at`, `feed_id`.

**ApiUsage** — `date` (PK), `request_count`. Günlük kota takibi.

Şema değişiklikleri için **Alembic** (veritabanı migration aracı) eklenmesi 10. adımda değerlendirilecek;
başlangıçta `SQLModel.metadata.create_all` yeterli.

---

## 5. API Tasarımı

Tüm uçlar `/api` altında. Yazma işlemleri `X-Admin-Key` başlığı ile korunur (değer `.env`'de).

| Metot | Yol | Açıklama |
|---|---|---|
| GET | `/api/health` | Sağlık kontrolü |
| GET | `/api/articles` | Liste: `page`, `size`, `feed_id`, `status`, `q` (arama) |
| GET | `/api/articles/{id}` | Detay (özet, maddeler, kaynak linki) |
| POST | `/api/articles/{id}/resummarize` 🔒 | Kuyruğa yeniden ekle |
| GET | `/api/feeds` | Kaynak listesi |
| POST | `/api/feeds` 🔒 | Kaynak ekle (URL doğrulanır) |
| PATCH | `/api/feeds/{id}` 🔒 | Aktif/pasif, ad değiştir |
| DELETE | `/api/feeds/{id}` 🔒 | Kaynak sil |
| POST | `/api/feeds/{id}/refresh` 🔒 | Hemen çek |
| GET | `/api/queue/status` | Durumlara göre sayılar, bugünkü kullanım, sıradaki deneme zamanı |

Yanıtlar Pydantic/SQLModel "read" şemalarıyla döner (DB modeli doğrudan dışarı açılmaz; örn. `content` alanı gizli).
Liste yanıtı: `{ items, total, page, size }`.

---

## 6. Klasör Yapısı

```
ai-news/
├── CLAUDE.md
├── README.md
├── .gitignore
├── docs/
│   └── PLAN.md
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── main.py              # FastAPI app + lifespan (scheduler start/stop)
│   │   ├── config.py            # pydantic-settings ile ayarlar
│   │   ├── db.py                # engine, session, WAL pragması
│   │   ├── models.py            # SQLModel tabloları
│   │   ├── schemas.py           # API giriş/çıkış şemaları
│   │   ├── api/
│   │   │   ├── deps.py          # session, admin-key bağımlılıkları
│   │   │   ├── articles.py
│   │   │   ├── feeds.py
│   │   │   └── queue.py
│   │   ├── services/
│   │   │   ├── fetcher.py       # feedparser ile RSS çekme + tekilleştirme
│   │   │   ├── extractor.py     # trafilatura ile tam metin
│   │   │   ├── summarizer.py    # Gemini istemcisi + prompt + şema
│   │   │   ├── rate_limiter.py  # RPM + günlük kota
│   │   │   └── queue.py         # sıradaki işi al, durum geçişleri, backoff
│   │   ├── scheduler.py         # APScheduler işleri (sadece services'i çağırır)
│   │   └── seed.py              # varsayılan AI haber kaynakları
│   └── tests/
│       ├── conftest.py          # bellek içi SQLite, sahte Gemini
│       ├── fixtures/            # örnek RSS/HTML dosyaları
│       └── test_*.py
└── frontend/
    ├── package.json
    ├── vite.config.ts           # /api → localhost:8000 proxy
    ├── src/
    │   ├── main.ts
    │   ├── App.vue
    │   ├── router/index.ts
    │   ├── api/client.ts        # tipli fetch sarmalayıcısı
    │   ├── types/               # backend şemalarının TS karşılıkları
    │   ├── stores/              # Pinia: articles, feeds, queue
    │   ├── views/               # HomeView, ArticleView, FeedsView, StatusView
    │   └── components/          # ArticleCard, StatusBadge, Pagination, SearchBar...
    └── ...
```

**Katman kuralı:** `api/` → `services/` → `models`. API katmanı iş mantığı içermez; scheduler da sadece servis fonksiyonlarını çağırır.
Bu, servisleri hem API'den hem zamanlayıcıdan hem testlerden aynı şekilde kullanmayı sağlar.

---

## 7. Frontend Tasarımı

**Sayfalar (Vue Router)**
- `/` — Haber akışı: kartlar (Türkçe başlık, özet, kaynak, tarih, durum rozeti), kaynağa göre filtre, arama, sayfalama.
- `/articles/:id` — Detay: Türkçe başlık, özet, ana maddeler, "Orijinal habere git" bağlantısı.
- `/feeds` — Kaynak yönetimi: listele, ekle, aktif/pasif, hemen yenile (admin anahtarı gerekir).
- `/status` — Kuyruk paneli: pending/done/failed sayıları, bugünkü kota kullanımı, başarısız işler ve "tekrar dene".

**Durum yönetimi (Pinia):** `useArticlesStore`, `useFeedsStore`, `useQueueStore`. Her store `loading` / `error` durumlarını tutar.

**UI ilkeleri:** Tailwind ile responsive tasarım, karanlık mod, yükleme iskeletleri (skeleton), boş/hata durumları,
özeti henüz hazır olmayan haberlerde "Özet hazırlanıyor" rozeti. Admin anahtarı tarayıcıda `localStorage`'da tutulur
(sadece kişisel kullanım için kabul edilebilir; README'de not düşülecek).

---

## 8. Yapılandırma (`backend/.env.example`)

```dotenv
GEMINI_API_KEY=
GEMINI_MODEL=gemini-flash-latest      # kurulumda güncel Flash model adı doğrulanacak
GEMINI_RPM=5
GEMINI_DAILY_LIMIT=100
SUMMARY_MIN_CHARS=1500
SUMMARY_MAX_INPUT_CHARS=12000
SUMMARY_MAX_ATTEMPTS=5
FETCH_INTERVAL_MINUTES=30
SCHEDULER_ENABLED=true
DATABASE_URL=sqlite:///./data/ai_news.db
ADMIN_API_KEY=
CORS_ORIGINS=http://localhost:5173
```

`.env` asla commit edilmez; sadece `.env.example` repoda bulunur.

---

## 9. Test Stratejisi

- **Birim testleri:** tekilleştirme, uzun/kısa karar mantığı, backoff hesabı, durum geçişleri, rate limiter.
- **Entegrasyon:** FastAPI `TestClient` + bellek içi SQLite ile API uçları.
- **Dış servisler asla gerçekten çağrılmaz:** Gemini sahte (fake) bir istemciyle, RSS/HTML `tests/fixtures/` dosyalarıyla taklit edilir.
- **Frontend:** Vitest ile store ve kritik bileşenler için birkaç test (10. adım).
- Hedef: servis katmanında yüksek kapsama; "her şeyi test et" değil, "riskli mantığı test et".

---

## 10. Uygulama Adımları

Her adım küçük, kendi başına çalışır ve commit'lenebilir. Her adımın sonunda "bitti" kriteri var.

### Faz 0 — Hazırlık
- [x] **Adım 0: Repo iskeleti** — `.gitignore`, `README` taslağı, Python ortamı (**uv** seçildi), Ruff (linter/formatter).
  _Bitti:_ `backend/` içinde boş bir FastAPI `/api/health` döner.

### Faz 1 — Backend çekirdeği
- [x] **Adım 1: Ayarlar ve veritabanı** — `config.py` (pydantic-settings), `db.py`, `models.py`, tablo oluşturma.
  _Bitti:_ uygulama açılınca SQLite dosyası ve tablolar oluşur.
- [ ] **Adım 2: RSS çekme** — `fetcher.py`: feedparser, URL normalizasyonu, tekilleştirme, ETag/Last-Modified, `seed.py`.
  _Bitti:_ bir komutla kaynaklar çekilir, aynı haber iki kez eklenmez; testleri var.
- [ ] **Adım 3: İçerik çıkarma** — `extractor.py`: trafilatura, timeout, hata toleransı, uzun/kısa kararı (`pending`/`skipped`).
  _Bitti:_ haberlerin `content_length` ve `summary_status` alanları doğru dolar.
- [ ] **Adım 4: Okuma API'si** — `/api/articles` (sayfalama, filtre, arama), `/api/articles/{id}`, `/api/feeds`.
  _Bitti:_ Swagger (`/docs`) üzerinden veriler görülür; API testleri geçer.

### Faz 2 — Özetleme kuyruğu
- [ ] **Adım 5: Gemini özetleyici** — `summarizer.py`: google-genai istemcisi, prompt, structured output, hata sınıflandırması (geçici/kalıcı).
  _Bitti:_ tek bir haber elle özetlenebilir; sahte istemciyle testleri var.
- [ ] **Adım 6: Kuyruk ve rate limiter** — `queue.py`, `rate_limiter.py`, `ApiUsage`, backoff, crash recovery.
  _Bitti:_ testlerde 429 senaryosu, kota dolması ve max deneme davranışı doğrulanır.
- [ ] **Adım 7: Zamanlayıcı** — `scheduler.py` + `lifespan`: fetch işi ve özet worker'ı; `/api/queue/status`.
  _Bitti:_ uygulama kendi kendine haber toplayıp limitler içinde özetler.
- [ ] **Adım 8: Yazma uçları** — kaynak ekle/sil/güncelle/yenile, yeniden özetle; admin anahtarı; CORS.
  _Bitti:_ korumalı uçlar anahtarsız 401 döner.

### Faz 3 — Frontend
- [ ] **Adım 9a: Frontend iskeleti** — Vite + Vue 3 + TS, Tailwind, Router, Pinia, API istemcisi, Vite proxy, tipler.
- [ ] **Adım 9b: Haber akışı ve detay** — HomeView, ArticleView, kart ve rozet bileşenleri, sayfalama, arama.
- [ ] **Adım 9c: Kaynaklar ve durum paneli** — FeedsView, StatusView, admin anahtarı girişi, karanlık mod.
  _Bitti:_ uçtan uca akış tarayıcıda çalışır.

### Faz 4 — Portföy cilası
- [ ] **Adım 10: Kalite** — Alembic değerlendirmesi, Vitest, ESLint/Prettier, yapılandırılmış loglama.
- [ ] **Adım 11: CI** — GitHub Actions: backend lint + test, frontend lint + type-check + build.
- [ ] **Adım 12: Sunum** — İngilizce README (mimari diyagram, ekran görüntüleri, kurulum), isteğe bağlı Docker Compose.

---

## 11. Riskler ve Açık Sorular

| Risk / Soru | Önlem / Karar zamanı |
|---|---|
| Ücretsiz katman limitleri değişebilir | Tüm limitler `.env`'de; Adım 5'te güncel değerler kontrol edilecek |
| Bazı siteler trafilatura'yı engeller / paywall | `rss_summary`'ye geri düş; hata `skipped` olarak işaretlenir |
| Scheduler'ın çift çalışması | Tek uvicorn worker + `SCHEDULER_ENABLED` |
| Ücretsiz katmanda verilerin model eğitiminde kullanılabilmesi | Sadece kamuya açık haber metni gönderiliyor; README'de not |
| Hangi RSS kaynakları? | Adım 2'de birlikte seçilecek (ör. şirket blogları, teknoloji sitelerinin AI kategorileri) |
| Python paket yöneticisi (uv / pip) | ✅ uv seçildi |
| Deploy edilecek mi? | Faz 4'te karar (Render/Fly.io + statik frontend gibi) |
