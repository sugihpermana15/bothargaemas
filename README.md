# bothargaemas

Bot Telegram 24/7 untuk monitoring harga emas **GALERI 24**, **ANTAM**, dan **UBS** (tabel lengkap semua pecahan) dari halaman:

- https://galeri24.co.id/harga-emas

Kode bot ada di folder `emasbot/`.

## Fitur

Bot akan polling tiap `30` detik (default), ambil **harga jual** dan **harga buyback** untuk semua pecahan di 3 vendor di atas, lalu:

- Jika berubah dibanding data terakhir: simpan ke SQLite + kirim notifikasi Telegram
- Jika tidak berubah: tidak mengirim pesan

Selain notifikasi otomatis, bot juga mendukung perintah Telegram:

- `/cekharga` → bot membalas **realtime** tabel lengkap GALERI 24 + ANTAM + UBS
- `/galeri24` → bot membalas **realtime** tabel GALERI 24 saja
- `/antam` → bot membalas **realtime** tabel ANTAM saja
- `/ubs` → bot membalas **realtime** tabel UBS saja

Catatan keamanan: bot hanya akan merespons perintah dari chat yang `chat_id`-nya tercantum di `TELEGRAM_CHAT_ID` di `.env`.

Scraping:

- Coba `requests` + `BeautifulSoup4` dulu
- Jika HTML dari `requests` tidak memuat data (mis. karena rendering JavaScript), fallback ke **Playwright**

## Struktur folder

WAJIB sesuai spesifikasi:

```
emasbot/
├── main.py
├── scraper.py
├── database.py
├── notifier.py
├── config.py
├── requirements.txt
└── README.md
```

## Environment variables

Wajib:

- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID` (bisa 1 atau beberapa chat id dipisah koma)

Opsional:

- `DB_PATH` (default: `emasbot.db`)
- `POLL_INTERVAL_SECONDS` (default: `30`)
- `REQUEST_TIMEOUT_SECONDS` (default: `15`)
- `MAX_RETRIES` (default: `3`)
- `RETRY_BACKOFF_BASE_SECONDS` (default: `1.5`)

### Contoh `.env`

Buat file `.env` di folder `emasbot/`:

```env
TELEGRAM_TOKEN=123456:ABCDEF_your_bot_token
TELEGRAM_CHAT_ID=6951917620,-1003703084240

DB_PATH=emasbot.db
POLL_INTERVAL_SECONDS=30
REQUEST_TIMEOUT_SECONDS=15
MAX_RETRIES=3
RETRY_BACKOFF_BASE_SECONDS=1.5
```

## Menjalankan di Windows (local)

Jalankan dari folder `emasbot/`.

### 1) Buat virtualenv + install dependency

PowerShell / CMD (pilih salah satu):

```bat
cd /d "D:\\02. PROJECT\\BOT TELEGRAM\\harga-emas-full\\emasbot"
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2) Buat `.env`

Buat file `.env` di folder `emasbot/` (satu folder dengan `main.py`). Minimal:

```env
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### 3) Install Playwright browser (fallback JS)

```bat
.venv\Scripts\python.exe -m playwright install chromium
```

### 4) Run

```bat
.venv\Scripts\python.exe main.py
```

## Menjalankan dengan Docker (VPS)

Project ini bisa dijalankan sebagai container background (tanpa port HTTP).

### 1) Siapkan folder + `.env`

Di folder yang berisi `docker-compose.yml` dan `Dockerfile`, buat file `.env`:

```env
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=6951917620,-1003703084240

# Opsional
POLL_INTERVAL_SECONDS=30
REQUEST_TIMEOUT_SECONDS=15
MAX_RETRIES=3
RETRY_BACKOFF_BASE_SECONDS=1.5
```

### 2) Build & run

```bash
docker compose up -d --build
```

### 3) Cek status & log

```bash
docker compose ps
docker compose logs -f emasbot
```

Catatan:

- Jangan jalankan bot ini di dua tempat sekaligus (mis. lokal + VPS) dengan token yang sama, karena fitur command (getUpdates) bisa conflict.

## Catatan parsing (tabel penuh)

Bot men-scrape section HTML dengan `id`:

- `GALERI 24`
- `ANTAM`
- `UBS`

Lalu membaca baris-baris tabel (Berat / Harga Jual / Harga Buyback) untuk masing-masing vendor.