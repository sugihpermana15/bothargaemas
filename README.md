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

## Membuat bot via BotFather (awal sampai jadi)

1) Buka Telegram, cari akun **BotFather**.
2) Jalankan perintah:

- `/newbot` → ikuti instruksi sampai BotFather memberi **token**.

3) Simpan token itu ke `.env`:

```env
TELEGRAM_TOKEN=123456:ABCDEF_your_bot_token
```

4) (Opsional tapi disarankan) Set daftar command di BotFather:

- `/setcommands` → pilih bot → tempel ini:

```text
cekharga - Cek harga semua vendor (GALERI 24, ANTAM, UBS)
galeri24 - Cek harga GALERI 24 saja
antam - Cek harga ANTAM saja
ubs - Cek harga UBS saja
```

5) (Opsional) Set deskripsi dan about:

- `/setdescription` → deskripsi panjang
- `/setabouttext` → intro singkat

Catatan:

- Bot ini memakai **getUpdates (long polling)**. Jangan aktifkan webhook di token yang sama.
- Jangan jalankan bot di 2 tempat sekaligus (lokal + VPS) dengan token yang sama, nanti bisa conflict `409`.

## Cara mendapatkan TELEGRAM_CHAT_ID

`TELEGRAM_CHAT_ID` adalah ID chat tempat bot boleh merespons command.

### A) Private chat (DM ke bot)

1) Chat bot kamu, kirim pesan apa saja (mis. `test`).
2) Jalankan perintah ini dari mesin yang sudah punya `TELEGRAM_TOKEN`:

```bash
curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/getUpdates" | head
```

3) Cari `"chat":{"id": ... }` → itulah chat id yang dipakai.

### B) Group / Supergroup

1) Tambahkan bot ke grup.
2) Kirim `/cekharga` di grup.
3) Jalankan `getUpdates` seperti di atas.
4) Ambil `chat.id`:

- Group biasanya angka negatif.
- Supergroup biasanya diawali `-100...`.

Jika grup pernah upgrade dari group → supergroup, Telegram bisa mengirim field `migrate_to_chat_id`; gunakan ID supergroup yang baru.

## Menjalankan di VPS Ubuntu (tanpa Docker, 24/7 dengan systemd)

Langkah di bawah diasumsikan VPS Ubuntu 22.04/24.04, dan project akan diletakkan di `/opt/bothargaemas`.

### 1) Install dependency OS

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

### 2) Clone repository

```bash
sudo mkdir -p /opt/bothargaemas
sudo chown -R $USER:$USER /opt/bothargaemas
cd /opt/bothargaemas
git clone https://github.com/sugihpermana15/bothargaemas.git .
```

### 3) Buat virtualenv + install Python packages

```bash
cd /opt/bothargaemas/emasbot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4) Install Playwright Chromium (fallback)

```bash
python -m playwright install --with-deps chromium
```

### 5) Buat `.env`

```bash
cd /opt/bothargaemas/emasbot
nano .env
```

Isi minimal:

```env
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### 6) Test run manual

```bash
cd /opt/bothargaemas/emasbot
source .venv/bin/activate
python main.py
```

### 7) Buat service systemd

Buat file:

```bash
sudo nano /etc/systemd/system/bothargaemas.service
```

Isi (sesuaikan path bila berbeda):

```ini
[Unit]
Description=bothargaemas - Telegram gold price monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/bothargaemas/emasbot
EnvironmentFile=/opt/bothargaemas/emasbot/.env
ExecStart=/opt/bothargaemas/emasbot/.venv/bin/python /opt/bothargaemas/emasbot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Aktifkan:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bothargaemas
sudo systemctl status bothargaemas --no-pager
```

Lihat log:

```bash
journalctl -u bothargaemas -f
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