# emasbot

Bot Telegram 24/7 untuk monitoring harga emas **GALERI 24**, **ANTAM**, dan **UBS** (tabel lengkap semua pecahan) dari halaman:

- https://galeri24.co.id/harga-emas

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
2) Jalankan `/newbot` → ikuti instruksi sampai BotFather memberi **token**.
3) Simpan token ke `.env`:

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

Catatan:

- Bot ini memakai **getUpdates (long polling)**. Jangan aktifkan webhook di token yang sama.
- Jangan jalankan bot di 2 tempat sekaligus (lokal + VPS) dengan token yang sama, nanti bisa conflict `409`.

## Cara mendapatkan TELEGRAM_CHAT_ID

`TELEGRAM_CHAT_ID` adalah ID chat tempat bot boleh merespons command.

### A) Private chat (DM ke bot)

1) Chat bot kamu, kirim pesan apa saja.
2) Panggil `getUpdates` dan ambil `chat.id`.

Contoh cepat (Linux/VPS):

```bash
curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/getUpdates" | head
```

### B) Group / Supergroup

1) Tambahkan bot ke grup.
2) Kirim `/cekharga` di grup.
3) Panggil `getUpdates` dan ambil `chat.id`.

Jika grup upgrade ke supergroup, Telegram bisa mengirim `migrate_to_chat_id`; gunakan ID supergroup yang baru.

## Setup Ubuntu VPS (Python 3.10+) sampai running

Langkah di bawah diasumsikan Anda berada di VPS Ubuntu dan project ada di `~/emasbot`.

### 1) Install Python + tools

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

### 2) Upload / clone project

Letakkan folder `emasbot/` di server, misalnya:

```bash
mkdir -p ~/emasbot
# tar/copy repository Anda, atau git clone lalu masuk ke folder
cd ~/emasbot/emasbot
```

### 3) Buat virtualenv + install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4) Install browser untuk Playwright (fallback JS-rendered)

```bash
python -m playwright install --with-deps chromium
```

Catatan:

- Perintah di atas menginstall Chromium + dependency OS yang dibutuhkan.
- Jika Anda memilih install deps secara manual, Playwright bisa butuh paket tambahan (tergantung distro).

### 5) Set env vars

Opsi A (paling gampang): gunakan `.env`.

```bash
cd ~/emasbot/emasbot
nano .env
```

Opsi B: export env vars langsung:

```bash
export TELEGRAM_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

### 6) Jalankan manual

```bash
cd ~/emasbot/emasbot
source .venv/bin/activate
python main.py
```

Jika sukses, log akan tampil dan bot mulai polling.

## Menjalankan di Windows (local)

Jalankan dari folder yang berisi `main.py` (folder `emasbot/`).

### 1) Buat virtualenv + install dependency

PowerShell / CMD (pilih salah satu):

```bat
cd /d "D:\02. PROJECT\BOT TELEGRAM\harga-emas\emasbot"
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

## Menjalankan 24/7 dengan systemd

### Contoh file service

Buat file:

- `/etc/systemd/system/emasbot.service`

Isi contoh (sesuaikan path dan user):

```ini
[Unit]
Description=emasbot - Telegram Galeri24 gold price monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/emasbot/emasbot
EnvironmentFile=/home/ubuntu/emasbot/emasbot/.env
ExecStart=/home/ubuntu/emasbot/emasbot/.venv/bin/python /home/ubuntu/emasbot/emasbot/main.py
Restart=always
RestartSec=5

# Hardening (opsional tapi bagus)
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

Aktifkan:

```bash
sudo systemctl daemon-reload
sudo systemctl enable emasbot
sudo systemctl start emasbot
sudo systemctl status emasbot --no-pager
```

Lihat log:

```bash
journalctl -u emasbot -f
```

## Menjalankan dengan Docker (VPS)

Project ini bisa dijalankan sebagai container background (tanpa port HTTP).

### 1) Siapkan folder + `.env`

Buat file `.env` di folder `emasbot/` (satu folder dengan `main.py`):

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
cd /srv/hargaemas
docker compose up -d --build
```

### 3) Cek status & log

```bash
docker compose ps
docker compose logs -f emasbot
```

Catatan:

- Jangan jalankan bot ini di dua tempat sekaligus (mis. lokal + VPS) dengan token yang sama, karena fitur `/cekharga` (getUpdates) bisa conflict.

## Catatan parsing (tabel penuh)

Bot men-scrape section HTML dengan `id`:

- `GALERI 24`
- `ANTAM`
- `UBS`

Lalu membaca baris-baris tabel (Berat / Harga Jual / Harga Buyback) untuk masing-masing vendor.

- pertama: `sell_price` (harga jual)
- kedua: `buyback_price`

Konversi contoh:

- `Rp74.536.000` → `74536000` (hapus semua non-digit)

## Troubleshooting cepat

- Tidak ada pesan Telegram: pastikan `TELEGRAM_CHAT_ID` benar (untuk grup biasanya negatif seperti `-100...`) dan bot sudah di-add ke grup.
- Error `403 Forbidden: bots can't send messages to bots`: `TELEGRAM_CHAT_ID` Anda kemungkinan adalah **ID bot**, bukan ID user/grup. Ambil `chat_id` yang benar:
	1) Buka chat dengan bot Anda, kirim `/start`
	2) Jalankan `getUpdates` (jangan bagikan token):

		 ```bash
		 curl "https://api.telegram.org/bot<TELEGRAM_TOKEN>/getUpdates"
		 ```

		 Lihat bagian `message.chat.id` lalu isi ke `TELEGRAM_CHAT_ID`.
	3) Untuk grup: tambahkan bot ke grup, kirim pesan di grup, lalu cari `chat.id` (biasanya `-100...`).
- Perintah `/cekharga` di grup tidak dibalas: pastikan `TELEGRAM_CHAT_ID` di `.env` mencantumkan **ID grup** (mis. `-100...`). Jika grup memakai **Topics**, bot akan membalas ke topic yang sama.
- Sudah betulkan `TELEGRAM_CHAT_ID` tapi belum ada notifikasi: bot hanya kirim saat harga berubah. Untuk test cepat, stop bot lalu hapus `emasbot.db` (atau set `DB_PATH` ke file baru) agar siklus berikutnya dianggap “pertama kali” dan mengirim notifikasi.
- Error `409 Conflict: terminated by other getUpdates request`: ada **lebih dari satu** proses bot yang jalan memakai token yang sama (mis. bot jalan di VPS dan local bersamaan, atau Anda menjalankan bot di dua terminal). Solusi:
	- Pastikan hanya 1 instance yang running.
	- Jika pernah pakai `curl .../getUpdates` atau menjalankan skrip lain yang juga `getUpdates`, hentikan itu.
	- Opsional: clear webhook (jika pernah set webhook):

		```bash
		curl "https://api.telegram.org/bot<TELEGRAM_TOKEN>/deleteWebhook?drop_pending_updates=true"
		```
- Playwright error di VPS: jalankan `python -m playwright install --with-deps chromium`.
- Sering timeout: naikkan `REQUEST_TIMEOUT_SECONDS`.
