"""
OUTPUT — Modul Dashboard Monitoring & Visualisasi
==================================================
Berisi halaman dashboard admin untuk menampilkan:
- KPI Cards (total ulasan, sentimen negatif, rata-rata rating, rata-rata SERVPERF)
- Grafik bar rata-rata skor per dimensi SERVPERF
- Donut chart distribusi sentimen
- Donut chart proporsi metode reservasi
- Rekomendasi Prioritas DSS (rule-based)
- Horizontal bar chart Top 5 kata kunci keluhan negatif
- Tabel data ulasan tamu dengan filter
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import html
from datetime import timedelta, datetime, timezone

from core_utils import load_all_feedback
from process_nlp import extract_negative_findings

# Timezone WIB (UTC+7) — agar filter tanggal sesuai waktu lokal Indonesia
_WIB = timezone(timedelta(hours=7))

# ============================================================
# MAPPING LABEL DIMENSI MANAJERIAL (FITUR 2)
# ============================================================
DIMENSION_LABEL_MAP = {
    "Reliability": "Kenyamanan Kamar & Kualitas Tidur",
    "Assurance": "Kesopanan, Kompetensi & Keamanan",
    "Tangibles": "Kebersihan & Kelengkapan Fasilitas Fisik",
    "Empathy": "Kepedulian & Perhatian Personal",
    "Responsiveness": "Kecepatan & Kesiagapan Staf",
}

# ============================================================
# MAPPING DIMENSI → KATEGORI ABSA YANG RELEVAN
# ============================================================
# Setiap dimensi SERVPERF dipetakan ke kategori keluhan ABSA
# yang secara logis berkaitan dengan aspek dimensi tersebut.
DIMENSION_ABSA_MAP = {
    "Reliability": [
        "Serangga dan hewan pengganggu",
        "Lantai kamar berbunyi saat dipijak",
        "Kamar berbau tidak sedap",
        "Desain kamar kurang ergonomis",
        "Kenyamanan kasur/tempat tidur kurang",
        "Gangguan lingkungan",
        "Kamar panas",
    ],
    "Assurance": [
        "Kualitas pelayanan staf kurang",
        "Keamanan jalan menuju unit kurang",
        "Informasi fasilitas kurang jelas",
    ],
    "Tangibles": [
        "Tidak ada AC",
        "Fasilitas kamar tidak memadai",
        "Kamar mandi/toilet kurang bersih",
        "Kebersihan kamar kurang",
        "Sanitasi kolam ikan kurang terjaga",
        "Kebersihan lingkungan resort kurang",
        "Penerangan kamar dan lingkungan kurang",
        "Koneksi WiFi tidak stabil",
        "Kolam rendam kurang panas",
        "Kebersihan tempat makan/restoran kurang",
        "Parkir kurang memadai",
        "Perlengkapan kamar (toiletries) kurang lengkap",
        "Ketersediaan stop kontak/colokan listrik terbatas di kamar",
        "Variasi dan rasa makanan kurang",
    ],
    "Empathy": [
        "Kualitas pelayanan staf kurang",
    ],
    "Responsiveness": [
        "Waktu penyajian makanan lama",
        "Kualitas pelayanan staf kurang",
    ],
}

# ============================================================
# KNOWLEDGE BASE DSS PER DIMENSI — FISHBONE 6M (LEVEL DIMENSI)
# ============================================================
# Penyebab & rekomendasi umum pada level dimensi SERVPERF.
# Digunakan ketika skor dimensi rendah namun belum tentu ada
# keluhan teks yang terdeteksi ABSA.
DIMENSION_DSS_KB = {
    "Reliability": [
        {
            "faktor": "Material",
            "penyebab": "Kualitas material tempat tidur, kasur, atau insulasi ruangan tidak memenuhi standar kenyamanan",
            "rekomendasi": "Evaluasi dan remajakan material kasur serta tambahkan insulasi/peredam suara pada dinding kamar",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada prosedur pemeliharaan kenyamanan kamar (penghilang bau, kontrol suhu, pest control) sebelum tamu check-in",
            "rekomendasi": "Terapkan SOP persiapan kamar (termasuk pest control berkala dan sirkulasi udara) sebelum status 'Ready'",
        },
        {
            "faktor": "Mother Nature",
            "penyebab": "Faktor alam sekitar (serangga, suhu ekstrem, kebisingan hewan) yang mengganggu kenyamanan tidur",
            "rekomendasi": "Pasang pelindung ekstra seperti kasa nyamuk, dan sediakan fasilitas penunjang kenyamanan (AC/Kipas angin)",
        },
    ],
    "Assurance": [
        {
            "faktor": "Man",
            "penyebab": "Staf belum memiliki kompetensi dan sikap yang cukup untuk memberikan rasa aman dan nyaman kepada tamu",
            "rekomendasi": "Lakukan pelatihan service excellence & product knowledge secara rutin kepada seluruh staf",
        },
        {
            "faktor": "Method",
            "penyebab": "Prosedur penyampaian informasi dan jaminan keamanan belum jelas dan tidak tersosialisasi dengan baik",
            "rekomendasi": "Standardisasikan script informasi bagi front-line dan perjelas rambu keamanan di seluruh area resort",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Fasilitas keamanan pendukung (penerangan, CCTV, pagar pembatas) belum memadai",
            "rekomendasi": "Tingkatkan fasilitas keamanan fisik, terutama di area yang rawan atau kurang pencahayaan",
        },
    ],
    "Tangibles": [
        {
            "faktor": "Method",
            "penyebab": "SOP kebersihan area (kamar, toilet, restoran, lingkungan) belum dijalankan dengan konsisten",
            "rekomendasi": "Terapkan inspeksi kebersihan berkala menggunakan checklist digital dan cross-check oleh supervisor",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Peralatan fisik dan fasilitas (AC, WiFi, kolam, parkir, kelistrikan) belum memadai secara kuantitas maupun kualitas",
            "rekomendasi": "Audit dan lengkapi sarana fisik (termasuk stop kontak, amenities, & titik WiFi) sesuai standar modern",
        },
        {
            "faktor": "Man",
            "penyebab": "Kekurangan jumlah staf kebersihan atau tingginya beban kerja, terutama saat resort sedang ramai",
            "rekomendasi": "Sesuaikan rasio petugas kebersihan terhadap luasan area dan tingkat hunian",
        },
    ],
    "Empathy": [
        {
            "faktor": "Man",
            "penyebab": "Staf belum proaktif dalam memberikan perhatian personal dan memahami kebutuhan khusus tamu",
            "rekomendasi": "Berikan pelatihan hospitality fokus pada active listening dan empati dalam menghadapi tamu",
        },
        {
            "faktor": "Method",
            "penyebab": "Tidak ada sistem pencatatan preferensi atau keluhan tamu yang diteruskan antar shift",
            "rekomendasi": "Implementasikan sistem handover (operan) yang mencatat kebutuhan khusus dan preferensi tiap tamu",
        },
    ],
    "Responsiveness": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada penetapan Service Level Agreement (SLA) waktu tunggu dan respons keluhan tamu",
            "rekomendasi": "Tetapkan standar waktu maksimal penyajian makanan dan penanganan keluhan kamar",
        },
        {
            "faktor": "Man",
            "penyebab": "Keterbatasan jumlah personel saat jam sibuk (rush hour) mengakibatkan layanan menjadi lambat",
            "rekomendasi": "Atur ulang jadwal shift staf agar lebih banyak personel bersiaga pada jam-jam sibuk",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Sistem komunikasi antar departemen (FO ke Housekeeping/F&B) kurang efisien",
            "rekomendasi": "Gunakan sistem komunikasi digital yang mempercepat alur koordinasi penyelesaian permintaan tamu",
        },
    ],
}

# ============================================================
# KNOWLEDGE BASE DSS RULE-BASED — ANALISIS FISHBONE / 6M (FITUR 4)
# ============================================================
# Key harus PERSIS sama dengan field "name" di ABSA_CATEGORIES (process_nlp.py)
# Setiap entry = list of dict {"faktor", "penyebab", "rekomendasi"}
# Faktor mengacu pada Fishbone 6M: Man, Method, Machine/Tool, Material, Mother Nature, Measurement
DSS_KNOWLEDGE_BASE = {
    "Tidak ada AC": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada target kuantitatif & timeline pemerataan instalasi AC",
            "rekomendasi": "Susun Master Schedule & target anggaran kuantitatif bulanan yang mengikat",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Unit AC belum tersedia merata di seluruh kamar",
            "rekomendasi": "Prioritaskan pengadaan bertahap berdasarkan keluhan tertinggi",
        },
        {
            "faktor": "Measurement",
            "penyebab": "Belum ada pemetaan data prioritas kamar dengan keluhan suhu tertinggi",
            "rekomendasi": "Susun peta prioritas kamar berdasarkan frekuensi keluhan panas dari data DFS",
        },
    ],
    "Fasilitas kamar tidak memadai": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada jadwal peremajaan aset (preventive replacement)",
            "rekomendasi": "Buat logbook umur ekonomis aset & jadwal peremajaan sebelum aset aus",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Tidak ada logbook pelaporan kerusakan fasilitas",
            "rekomendasi": "Sediakan logbook digital pelaporan kerusakan terintegrasi dengan tim Engineering",
        },
        {
            "faktor": "Man",
            "penyebab": "Staf tidak terbiasa melaporkan kerusakan kecil sebelum menjadi besar",
            "rekomendasi": "Bangun budaya pelaporan dini melalui briefing rutin dan insentif kepatuhan",
        },
    ],
    "Serangga dan hewan pengganggu": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada jadwal pest control rutin",
            "rekomendasi": "Terapkan jadwal fumigasi/pest control berkala",
        },
        {
            "faktor": "Mother Nature",
            "penyebab": "Lokasi resor berada di area terbuka dekat vegetasi alami",
            "rekomendasi": "Pasang penghalang fisik (kasa nyamuk, penutup celah) pada unit kamar",
        },
        {
            "faktor": "Material",
            "penyebab": "Celah pada material bangunan (bilik bambu/kayu) memudahkan serangga masuk",
            "rekomendasi": "Tutup celah struktural pada dinding bilik bambu/kayu secara berkala",
        },
    ],
    "Variasi dan rasa makanan kurang": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada kontrol kualitas rasa dan rotasi menu berkala",
            "rekomendasi": "Terapkan uji rasa (taste test) rutin dan evaluasi menu berkala",
        },
        {
            "faktor": "Material",
            "penyebab": "Variasi bahan baku terbatas",
            "rekomendasi": "Evaluasi pemasok dan tambah variasi bahan baku musiman",
        },
        {
            "faktor": "Man",
            "penyebab": "Keterbatasan keterampilan juru masak dalam variasi resep",
            "rekomendasi": "Adakan pelatihan kuliner/upskilling bagi staf dapur secara berkala",
        },
    ],
    "Kamar mandi/toilet kurang bersih": [
        {
            "faktor": "Method",
            "penyebab": "Lemahnya prosedur deep cleaning & cross-check supervisor",
            "rekomendasi": "Perbarui SOP deep cleaning & wajibkan cross-check kebersihan",
        },
        {
            "faktor": "Man",
            "penyebab": "Kurangnya supervisi pada titik yang sering terlewat (sudut, celah)",
            "rekomendasi": "Latih staf pada titik kritis kebersihan, spot-check berkala",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Peralatan pembersih saluran air tidak memadai",
            "rekomendasi": "Sediakan alat pembersih saluran (drain snake/vacuum saluran) khusus",
        },
    ],
    "Kebersihan kamar kurang": [
        {
            "faktor": "Man",
            "penyebab": "Staf housekeeping terburu-buru saat jam sibuk",
            "rekomendasi": "Evaluasi beban kerja staf, tambah personel saat peak hours",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada SOP inspeksi silang sebelum status kamar \"Ready\"",
            "rekomendasi": "Terapkan cross-check wajib oleh supervisor sebelum kamar dijual",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Update status kamar hanya via radio (HT), tanpa verifikasi digital",
            "rekomendasi": "Bangun sistem checklist digital terhubung status kamar",
        },
    ],
    "Sanitasi kolam ikan kurang terjaga": [
        {
            "faktor": "Method",
            "penyebab": "Tidak ada checklist & jadwal rutin pembersihan area air",
            "rekomendasi": "Terapkan checklist inspeksi harian area air sebelum jam operasional",
        },
        {
            "faktor": "Man",
            "penyebab": "Kurang jelasnya PIC kebersihan area kolam",
            "rekomendasi": "Tetapkan PIC (Gardening/Public Area) dengan jadwal kerja jelas",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Tidak ada sistem filter/sirkulasi air otomatis",
            "rekomendasi": "Pasang sistem filtrasi/sirkulasi air untuk menjaga kualitas air secara berkelanjutan",
        },
    ],
    "Kualitas pelayanan staf kurang": [
        {
            "faktor": "Man",
            "penyebab": "Standar pelayanan belum konsisten antarstaf",
            "rekomendasi": "Pelatihan ulang SOP pelayanan dan roleplay penanganan tamu",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada evaluasi kinerja pelayanan berkala",
            "rekomendasi": "Terapkan evaluasi kinerja pelayanan secara rutin",
        },
        {
            "faktor": "Measurement",
            "penyebab": "Belum ada indikator/KPI kinerja layanan yang terukur",
            "rekomendasi": "Susun KPI pelayanan (mis. skor kepuasan per staf) sebagai dasar evaluasi",
        },
    ],
    "Kebersihan lingkungan resort kurang": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada jadwal kebersihan area luar kamar yang terjadwal jelas",
            "rekomendasi": "Susun jadwal kebersihan area publik dengan PIC yang jelas",
        },
        {
            "faktor": "Man",
            "penyebab": "Jumlah tenaga kebersihan area publik tidak memadai",
            "rekomendasi": "Evaluasi rasio staf kebersihan terhadap luas area publik, tambah personel bila perlu",
        },
    ],
    "Penerangan kamar dan lingkungan kurang": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Titik lampu belum memadai di beberapa area",
            "rekomendasi": "Audit titik penerangan dan tambah lampu di area minim cahaya",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada jadwal penggantian lampu berkala",
            "rekomendasi": "Terapkan jadwal pemeriksaan & penggantian lampu rutin",
        },
        {
            "faktor": "Man",
            "penyebab": "Tidak ada petugas patroli rutin yang mengecek lampu mati",
            "rekomendasi": "Tugaskan petugas maintenance untuk patroli & pelaporan lampu mati harian",
        },
    ],
    "Gangguan lingkungan": [
        {
            "faktor": "Material",
            "penyebab": "Material bangunan (bilik bambu/kayu) tidak kedap suara tinggi",
            "rekomendasi": "Pertimbangkan peredam suara tambahan pada unit bungalow",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada kebijakan jam tenang (quiet hours) yang dikomunikasikan",
            "rekomendasi": "Tetapkan dan komunikasikan aturan quiet hours saat check-in",
        },
        {
            "faktor": "Mother Nature",
            "penyebab": "Lokasi terbuka dekat vegetasi memungkinkan gangguan alami",
            "rekomendasi": "Pasang jaring/pelindung atap pada titik rawan gangguan alam",
        },
        {
            "faktor": "Man",
            "penyebab": "Kurangnya pengawasan aktif petugas keamanan pada malam hari",
            "rekomendasi": "Tingkatkan intensitas patroli keamanan malam di area bungalow",
        },
    ],
    "Koneksi WiFi tidak stabil": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Kapasitas bandwidth/titik akses tidak memadai",
            "rekomendasi": "Evaluasi kapasitas dan tambah access point di titik lemah sinyal",
        },
        {
            "faktor": "Method",
            "penyebab": "Tidak ada monitoring rutin kualitas jaringan",
            "rekomendasi": "Terapkan pemantauan kualitas sinyal berkala sebelum tamu mengeluh",
        },
    ],
    "Kolam rendam kurang panas": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Sistem pemanas air kolam tidak optimal",
            "rekomendasi": "Evaluasi kapasitas pemanas dan lakukan perawatan berkala",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada pengecekan suhu rutin sebelum jam operasional",
            "rekomendasi": "Terapkan pengecekan suhu kolam terjadwal setiap pagi",
        },
    ],
    "Lantai kamar berbunyi saat dipijak": [
        {
            "faktor": "Material",
            "penyebab": "Struktur lantai kayu/panggung sudah mulai longgar",
            "rekomendasi": "Lakukan pemeriksaan dan perbaikan struktur lantai secara berkala",
        },
        {
            "faktor": "Method",
            "penyebab": "Tidak ada jadwal inspeksi struktur bangunan berkala",
            "rekomendasi": "Masukkan pemeriksaan struktur lantai ke jadwal preventive maintenance bangunan",
        },
    ],
    "Kamar berbau tidak sedap": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada prosedur pengeringan/ventilasi kamar setelah dibersihkan sebelum ditempati tamu berikutnya",
            "rekomendasi": "Terapkan SOP membuka jendela/ventilasi kamar minimal 30 menit sebelum status \"Ready\"",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Sirkulasi udara kamar kurang baik sehingga bau lembap terperangkap",
            "rekomendasi": "Sediakan air purifier/pengharum ruangan otomatis pada kamar yang jarang terpakai",
        },
        {
            "faktor": "Material",
            "penyebab": "Material kasur/karpet/gorden menyerap kelembapan dan menimbulkan bau seiring waktu",
            "rekomendasi": "Lakukan pembersihan/penjemuran berkala pada material penyerap (kasur, gorden, karpet)",
        },
    ],
    "Desain kamar kurang ergonomis": [
        {
            "faktor": "Method",
            "penyebab": "Tata letak furnitur belum mempertimbangkan kenyamanan pengguna",
            "rekomendasi": "Evaluasi ulang tata letak furnitur kamar berdasarkan masukan tamu",
        },
        {
            "faktor": "Measurement",
            "penyebab": "Belum ada survei ergonomi/kenyamanan tamu terhadap tata letak furnitur",
            "rekomendasi": "Lakukan survei kenyamanan ergonomis sebagai dasar evaluasi ulang",
        },
    ],
    "Kenyamanan kasur/tempat tidur kurang": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada jadwal peremajaan kasur berkala",
            "rekomendasi": "Susun jadwal penggantian/peremajaan kasur berdasarkan usia pakai",
        },
        {
            "faktor": "Material",
            "penyebab": "Kualitas material kasur/bantal menurun seiring waktu pemakaian",
            "rekomendasi": "Evaluasi dan ganti material kasur/bantal yang sudah aus",
        },
        {
            "faktor": "Measurement",
            "penyebab": "Belum ada standar kenyamanan kasur yang diukur berkala",
            "rekomendasi": "Lakukan survei kenyamanan kasur berkala sebagai dasar peremajaan",
        },
    ],
    "Keamanan jalan menuju unit kurang": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada pembatas/pagar pengaman di sepanjang jalan yang berdekatan dengan kolam teratai",
            "rekomendasi": "Pasang pagar/pembatas fisik di sepanjang jalan setapak dekat kolam",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Penerangan jalan menuju unit kurang memadai pada malam hari",
            "rekomendasi": "Tambah titik lampu penerangan di sepanjang jalur rawan",
        },
        {
            "faktor": "Man",
            "penyebab": "Tidak ada rambu peringatan bahaya di titik rawan",
            "rekomendasi": "Pasang rambu peringatan \"hati-hati kolam\" di titik rawan",
        },
    ],
    "Kebersihan tempat makan/restoran kurang": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada checklist kebersihan area makan",
            "rekomendasi": "Terapkan checklist kebersihan restoran sebelum jam operasional",
        },
        {
            "faktor": "Man",
            "penyebab": "Kurangnya pengawasan konsisten terhadap kebersihan area makan",
            "rekomendasi": "Tugaskan PIC kebersihan restoran dengan jadwal spot-check rutin",
        },
    ],
    "Waktu penyajian makanan lama": [
        {
            "faktor": "Method",
            "penyebab": "Alur kerja dapur belum efisien saat pesanan menumpuk",
            "rekomendasi": "Optimalkan alur kerja dapur dan pembagian tugas saat jam sibuk",
        },
        {
            "faktor": "Man",
            "penyebab": "Jumlah staf dapur tidak memadai saat jam makan ramai",
            "rekomendasi": "Sesuaikan jumlah staf dapur dengan proyeksi jam makan sibuk",
        },
        {
            "faktor": "Method",
            "penyebab": "Tidak ada estimasi waktu penyajian yang dikomunikasikan ke tamu",
            "rekomendasi": "Sampaikan estimasi waktu tunggu saat pemesanan",
        },
    ],
    "Parkir kurang memadai": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Kapasitas lahan parkir terbatas",
            "rekomendasi": "Evaluasi tata letak parkir dan pertimbangkan kerja sama lahan tambahan",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada sistem pengaturan/pengarahan parkir saat ramai",
            "rekomendasi": "Tugaskan petugas pengatur parkir pada jam kunjungan tinggi",
        },
    ],
    "Informasi fasilitas kurang jelas": [
        {
            "faktor": "Method",
            "penyebab": "Informasi fasilitas tidak disampaikan saat check-in",
            "rekomendasi": "Sampaikan info fasilitas secara lisan & tercetak di welcome card",
        },
        {
            "faktor": "Man",
            "penyebab": "Staf tidak proaktif menyampaikan informasi fasilitas ke tamu",
            "rekomendasi": "Latih staf Front Office untuk selalu menyampaikan info fasilitas saat registrasi",
        },
    ],
    "Perlengkapan kamar (toiletries) kurang lengkap": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada standar baku kelengkapan toiletries per kamar",
            "rekomendasi": "Tetapkan checklist kelengkapan toiletries standar per kamar",
        },
        {
            "faktor": "Man",
            "penyebab": "Staf housekeeping tidak mengecek kelengkapan sebelum kamar dijual",
            "rekomendasi": "Integrasikan pengecekan toiletries ke dalam checklist cross-check kamar (terkait Temuan #6)",
        },
    ],
    "Ketersediaan stop kontak/colokan listrik terbatas di kamar": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Jumlah titik stop kontak di kamar tidak memadai untuk kebutuhan tamu modern",
            "rekomendasi": "Tambah titik stop kontak di lokasi strategis kamar (dekat tempat tidur, meja kerja)",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada evaluasi kebutuhan kelistrikan kamar sesuai standar terkini",
            "rekomendasi": "Lakukan audit kelistrikan kamar dan sesuaikan dengan kebutuhan tamu masa kini",
        },
    ],
    "Kamar panas": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada target kuantitatif & timeline pemerataan instalasi AC",
            "rekomendasi": "Prioritaskan kamar dengan keluhan \"panas\" pada tahap awal pengadaan AC",
        },
        {
            "faktor": "Material",
            "penyebab": "Insulasi atap/dinding kamar kurang optimal menahan panas",
            "rekomendasi": "Evaluasi material atap/dinding untuk kamar dengan keluhan berulang",
        },
    ],
}



# ============================================================
# HALAMAN ADMIN: DASHBOARD MONITORING
# ============================================================

def page_dashboard_monitoring():
    """Render halaman dashboard monitoring (KPI, grafik, tabel)."""

    # --- Judul Dashboard ---
    st.markdown('<p class="dash-title">📊 Dashboard Monitoring Ulasan</p>', unsafe_allow_html=True)
    st.markdown('<p class="dash-subtitle">Kampung Sumber Alam — Analisis Real-time Feedback Tamu</p>',
                unsafe_allow_html=True)
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # Muat data
    df = load_all_feedback()

    if df.empty:
        st.info("📭 Belum ada data ulasan. Silakan isi form ulasan atau upload data OTA terlebih dahulu.")
        return

    # Pastikan kolom tanggal bertipe datetime untuk filtering
    # Normalisasi ke date-only (tanpa waktu) agar perbandingan konsisten
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")
    df["tanggal"] = df["tanggal"].dt.normalize()  # Set waktu ke 00:00:00

    # Normalisasi kolom jenis_reservasi (backward-compatible jika NULL)
    if "jenis_reservasi" not in df.columns:
        df["jenis_reservasi"] = "Tidak Diketahui"
    else:
        df["jenis_reservasi"] = df["jenis_reservasi"].fillna("Tidak Diketahui")

    # ----------------------------------------------------------------
    # SIDEBAR: FILTER (ditambahkan ke sidebar yang sudah ada)
    # ----------------------------------------------------------------
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🔍 Filter Data")

        # Filter Rentang Waktu — radio agar semua opsi terlihat tanpa dropdown
        filter_terbaru = st.radio(
            "🕐 Rentang Waktu",
            ["Semua Waktu", "Hari Ini", "7 Hari Terakhir", "30 Hari Terakhir", "90 Hari Terakhir"],
            key="filter_terbaru",
        )

        # Filter Sentimen
        sentimen_options = ["Semua"] + sorted(df["sentimen_akhir"].dropna().unique().tolist())
        filter_sentimen = st.selectbox("Sentimen", sentimen_options, key="filter_sentimen")

        # Filter Dimensi
        all_dimensions = set()
        for dims in df["dimensi_terdeteksi"].dropna():
            for d in dims.split(", "):
                if d.strip() and d.strip() != "Tidak Terdeteksi":
                    all_dimensions.add(d.strip())
        dimensi_options = ["Semua"] + sorted(all_dimensions)
        filter_dimensi = st.selectbox("Dimensi", dimensi_options, key="filter_dimensi")

        # Filter Jenis Reservasi (FITUR 3)
        filter_reservasi = st.selectbox(
            "🏷️ Jenis Reservasi",
            ["Semua", "Aplikasi Online (OTA)", "Walk-in"],
            key="filter_reservasi",
        )

    # Terapkan filter
    df_filtered = df.copy()

    if filter_sentimen != "Semua":
        df_filtered = df_filtered[df_filtered["sentimen_akhir"] == filter_sentimen]
    if filter_dimensi != "Semua":
        df_filtered = df_filtered[
            df_filtered["dimensi_terdeteksi"].str.contains(filter_dimensi, na=False)
        ]
    if filter_reservasi != "Semua":
        df_filtered = df_filtered[df_filtered["jenis_reservasi"] == filter_reservasi]

    # Filter berdasarkan waktu — gunakan WIB (UTC+7) dan batasi sampai hari ini
    today = pd.Timestamp(datetime.now(_WIB).date())
    if filter_terbaru == "Hari Ini":
        df_filtered = df_filtered[df_filtered["tanggal"] == today]
    elif filter_terbaru == "7 Hari Terakhir":
        start = today - timedelta(days=7)
        df_filtered = df_filtered[(df_filtered["tanggal"] >= start) & (df_filtered["tanggal"] <= today)]
    elif filter_terbaru == "30 Hari Terakhir":
        start = today - timedelta(days=30)
        df_filtered = df_filtered[(df_filtered["tanggal"] >= start) & (df_filtered["tanggal"] <= today)]
    elif filter_terbaru == "90 Hari Terakhir":
        start = today - timedelta(days=90)
        df_filtered = df_filtered[(df_filtered["tanggal"] >= start) & (df_filtered["tanggal"] <= today)]

    # ----------------------------------------------------------------
    # KPI CARDS — menggunakan data yang sudah difilter
    # ----------------------------------------------------------------
    st.markdown('<p class="section-header">📈 Key Performance Indicators</p>', unsafe_allow_html=True)

    total_ulasan = len(df_filtered)
    pct_negatif = (
        (df_filtered["sentimen_akhir"] == "Negatif").sum() / total_ulasan * 100
        if total_ulasan > 0 else 0
    )
    avg_rating = df_filtered["rating_bintang"].mean() if total_ulasan > 0 else 0
    avg_servperf = (
        df_filtered[["q1_reliability", "q2_assurance", "q3_tangibles",
            "q4_empathy", "q5_responsiveness"]].mean().mean()
        if total_ulasan > 0 else 0
    )

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.markdown(f"""
        <div class="kpi-card kpi-emerald">
            <div class="kpi-icon">📝</div>
            <div class="kpi-value">{total_ulasan}</div>
            <div class="kpi-label">Total Ulasan</div>
        </div>
        """, unsafe_allow_html=True)

    with k2:
        st.markdown(f"""
        <div class="kpi-card kpi-rose">
            <div class="kpi-icon">⚠️</div>
            <div class="kpi-value">{pct_negatif:.1f}%</div>
            <div class="kpi-label">Sentimen Negatif</div>
        </div>
        """, unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
        <div class="kpi-card kpi-amber">
            <div class="kpi-icon">⭐</div>
            <div class="kpi-value">{avg_rating:.2f}</div>
            <div class="kpi-label">Rata-rata Rating</div>
        </div>
        """, unsafe_allow_html=True)

    with k4:
        st.markdown(f"""
        <div class="kpi-card kpi-violet">
            <div class="kpi-icon">📊</div>
            <div class="kpi-value">{avg_servperf:.2f}</div>
            <div class="kpi-label">Rata-rata SERVPERF</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ----------------------------------------------------------------
    # GRAFIK — berdampingan [2.4, 1.3, 1.3] agar bar chart lebih lebar
    # ----------------------------------------------------------------
    with st.container(border=True):
        chart_col1, chart_col2, chart_col3 = st.columns([2.4, 1.3, 1.3], gap="medium")

        # --- Bar Chart: Rata-rata Skor Dimensi (FITUR 2 — label manajerial) ---
        with chart_col1:
            st.markdown('<p class="section-header">📊 Rata-rata Skor per Dimensi SERVPERF</p>',
                        unsafe_allow_html=True)

            # Variabel backend tetap q1_reliability dst, label diganti
            dim_means = pd.DataFrame({
                "Dimensi": [
                    DIMENSION_LABEL_MAP["Reliability"],
                    DIMENSION_LABEL_MAP["Assurance"],
                    DIMENSION_LABEL_MAP["Tangibles"],
                    DIMENSION_LABEL_MAP["Empathy"],
                    DIMENSION_LABEL_MAP["Responsiveness"],
                ],
                "Rata-rata": [
                    df_filtered["q1_reliability"].mean(),
                    df_filtered["q2_assurance"].mean(),
                    df_filtered["q3_tangibles"].mean(),
                    df_filtered["q4_empathy"].mean(),
                    df_filtered["q5_responsiveness"].mean(),
                ]
            })

            colors = ["#10b981", "#34d399", "#6ee7b7", "#a7f3d0", "#059669"]
            fig_bar = px.bar(
                dim_means,
                x="Dimensi",
                y="Rata-rata",
                color="Dimensi",
                color_discrete_sequence=colors,
                text_auto=".2f",
            )
            fig_bar.update_layout(
                height=350,
                yaxis_range=[0, 5.5],
                yaxis_title="Skor Rata-rata (1–5)",
                xaxis_title="",
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", size=11, color="#94a3b8"),
                margin=dict(t=30, b=50, l=40, r=20),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # --- Donut Chart: Distribusi Sentimen ---
        with chart_col2:
            st.markdown('<p class="section-header">🎯 Distribusi Sentimen</p>', unsafe_allow_html=True)

            sentimen_counts = df_filtered["sentimen_akhir"].value_counts().reset_index()
            sentimen_counts.columns = ["Sentimen", "Jumlah"]

            color_map = {"Positif": "#10b981", "Netral": "#f59e0b", "Negatif": "#f43f5e"}
            fig_donut = px.pie(
                sentimen_counts,
                names="Sentimen",
                values="Jumlah",
                hole=0.55,
                color="Sentimen",
                color_discrete_map=color_map,
            )
            fig_donut.update_traces(
                textinfo="label+percent",
                textposition="outside",
                textfont_size=11,
                pull=[0.03] * len(sentimen_counts),
            )
            fig_donut.update_layout(
                height=350,
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", size=11, color="#94a3b8"),
                margin=dict(t=30, b=30, l=10, r=10),
                annotations=[
                    dict(
                        text=f"<b>{total_ulasan}</b><br>Ulasan",
                        x=0.5, y=0.5,
                        font_size=12,
                        showarrow=False,
                        font=dict(family="Inter", color="#e2e8f0"),
                    )
                ],
            )
            st.plotly_chart(fig_donut, use_container_width=True)

        # --- Donut Chart: Proporsi Metode Reservasi (FITUR 3) ---
        with chart_col3:
            st.markdown('<p class="section-header">🏷️ Metode Reservasi</p>', unsafe_allow_html=True)

            reservasi_counts = df_filtered["jenis_reservasi"].value_counts().reset_index()
            reservasi_counts.columns = ["Metode", "Jumlah"]

            reservasi_color_map = {
                "Aplikasi Online (OTA)": "#3b82f6",
                "Walk-in": "#f59e0b",
                "Tidak Diketahui": "#6b7280",
            }
            fig_reservasi = px.pie(
                reservasi_counts,
                names="Metode",
                values="Jumlah",
                hole=0.55,
                color="Metode",
                color_discrete_map=reservasi_color_map,
            )
            fig_reservasi.update_traces(
                textinfo="label+percent",
                textposition="outside",
                textfont_size=11,
                pull=[0.03] * len(reservasi_counts),
            )
            fig_reservasi.update_layout(
                height=350,
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", size=11, color="#94a3b8"),
                margin=dict(t=30, b=30, l=10, r=10),
                annotations=[
                    dict(
                        text=f"<b>{total_ulasan}</b><br>Tamu",
                        x=0.5, y=0.5,
                        font_size=12,
                        showarrow=False,
                        font=dict(family="Inter", color="#e2e8f0"),
                    )
                ],
            )
            st.plotly_chart(fig_reservasi, use_container_width=True)

    # ----------------------------------------------------------------
    # ANALISIS DSS BERBASIS DIMENSI SERVPERF (FITUR BARU)
    # ----------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<p class="section-header">🔬 Analisis DSS Berbasis Dimensi SERVPERF</p>',
                    unsafe_allow_html=True)
        st.caption(
            "Analisis penyebab & rekomendasi berdasarkan skor skala per dimensi, "
            "dipetakan ke kategori keluhan yang relevan dengan setiap dimensi."
        )

        # Hitung rata-rata skor per dimensi
        dim_scores = {
            "Tangibles": df_filtered["q3_tangibles"].mean() if total_ulasan > 0 else 0,
            "Reliability": df_filtered["q1_reliability"].mean() if total_ulasan > 0 else 0,
            "Responsiveness": df_filtered["q5_responsiveness"].mean() if total_ulasan > 0 else 0,
            "Assurance": df_filtered["q2_assurance"].mean() if total_ulasan > 0 else 0,
            "Empathy": df_filtered["q4_empathy"].mean() if total_ulasan > 0 else 0,
        }

        if total_ulasan > 0:
            # Urutkan dimensi dari skor terendah ke tertinggi
            sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1])
            lowest_dim = sorted_dims[0][0]

            # Selectbox — semua dimensi, default ke dimensi terendah
            dim_options = [f"{DIMENSION_LABEL_MAP[d]} ({d}) — Skor: {s:.2f}" for d, s in sorted_dims]
            dim_keys = [d for d, s in sorted_dims]

            selected_dim_option = st.selectbox(
                "Pilih Dimensi untuk Analisis:",
                dim_options,
                index=0,  # Default ke dimensi terendah
                key="dim_dss_selectbox",
            )
            selected_dim_idx = dim_options.index(selected_dim_option)
            selected_dim = dim_keys[selected_dim_idx]
            selected_score = dim_scores[selected_dim]
            selected_label = DIMENSION_LABEL_MAP[selected_dim]

            # Badge: terendah atau bukan
            is_lowest = (selected_dim == lowest_dim)
            dim_badge_text = "📉 DIMENSI SKOR TERENDAH" if is_lowest else "📊 ANALISIS DIMENSI"
            dim_badge_class = "dss-dim-badge-low" if is_lowest else "dss-dim-badge-normal"

            # --- Cari kategori ABSA terkait yang DITEMUKAN di data ---
            absa_categories_for_dim = DIMENSION_ABSA_MAP.get(selected_dim, [])

            # Hitung frekuensi ABSA dari ulasan negatif terfilter
            df_neg_dim = df_filtered[df_filtered["sentimen_akhir"] == "Negatif"]
            ulasan_neg_dim = df_neg_dim["teks_ulasan"].dropna().tolist()

            found_absa_in_dim = []  # Kategori ABSA yang ditemukan DAN relevan dgn dimensi ini
            if ulasan_neg_dim:
                all_findings = extract_negative_findings(ulasan_neg_dim, top_n=25)
                for finding in all_findings:
                    if finding["frasa"] in absa_categories_for_dim:
                        found_absa_in_dim.append(finding)

            # --- Build Fishbone Table (dari knowledge base per dimensi) ---
            dim_kb = DIMENSION_DSS_KB.get(selected_dim, [])

            # Fishbone dari knowledge base dimensi
            dim_table_html = (
                "<table style='width:100%; border-collapse:collapse; margin-top:10px; font-size:13px;'>"
                "<thead>"
                "<tr style='border-bottom:1px solid rgba(255,255,255,0.1); text-align:left;'>"
                "<th style='padding:8px 4px; color:#94a3b8; font-weight:600;'>Faktor (6M)</th>"
                "<th style='padding:8px 4px; color:#94a3b8; font-weight:600;'>Kemungkinan Penyebab</th>"
                "<th style='padding:8px 4px; color:#94a3b8; font-weight:600;'>Rekomendasi Tindakan</th>"
                "</tr>"
                "</thead>"
                "<tbody>"
            )
            for entry in dim_kb:
                dim_table_html += (
                    f"<tr style='border-bottom:1px solid rgba(255,255,255,0.05);'>"
                    f"<td style='padding:8px 4px; color:#38bdf8; font-weight:500; vertical-align:top;'>{entry['faktor']}</td>"
                    f"<td style='padding:8px 4px; color:#e2e8f0; vertical-align:top;'>{entry['penyebab']}</td>"
                    f"<td style='padding:8px 4px; color:#34d399; vertical-align:top;'>{entry['rekomendasi']}</td>"
                    f"</tr>"
                )
            dim_table_html += "</tbody></table>"

            # --- Build ABSA temuan terkait (jika ada) ---
            absa_list_html = ""
            if found_absa_in_dim:
                absa_list_html = (
                    "<div style='margin-top:14px;'>"
                    "<div style='font-size:0.78rem; font-weight:700; color:#38bdf8; "
                    "text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;'>"
                    "📋 Temuan Keluhan Spesifik (ABSA) Terkait Dimensi Ini:</div>"
                    "<table style='width:100%; border-collapse:collapse; font-size:13px;'>"
                    "<thead>"
                    "<tr style='border-bottom:1px solid rgba(255,255,255,0.1); text-align:left;'>"
                    "<th style='padding:6px 4px; color:#94a3b8; font-weight:600;'>No</th>"
                    "<th style='padding:6px 4px; color:#94a3b8; font-weight:600;'>Kategori Keluhan</th>"
                    "<th style='padding:6px 4px; color:#94a3b8; font-weight:600;'>Frekuensi</th>"
                    "<th style='padding:6px 4px; color:#94a3b8; font-weight:600;'>Proporsi</th>"
                    "</tr>"
                    "</thead>"
                    "<tbody>"
                )
                for idx, f in enumerate(found_absa_in_dim, 1):
                    ulasan_asli_html = ""
                    if "ulasan" in f and f["ulasan"]:
                        list_li = "".join([f"<li style='margin-bottom:4px; padding-left:4px;'>{html.escape(u)}</li>" for u in f["ulasan"]])
                        ulasan_asli_html = (
                            f"<details style='margin-top:6px;'>"
                            f"<summary style='font-size:0.75rem; color:#38bdf8; cursor:pointer;'>Lihat Ulasan Asli</summary>"
                            f"<ul style='font-size:0.75rem; color:#cbd5e1; margin-top:4px; padding-left:16px; font-style:italic; list-style-type:disc;'>"
                            f"{list_li}"
                            f"</ul>"
                            f"</details>"
                        )

                    absa_list_html += (
                        f"<tr style='border-bottom:1px solid rgba(255,255,255,0.05);'>"
                        f"<td style='padding:6px 4px; color:#94a3b8; vertical-align:top;'>{idx}</td>"
                        f"<td style='padding:6px 4px; color:#e2e8f0; vertical-align:top;'>"
                        f"<strong>{f['frasa']}</strong>"
                        f"{ulasan_asli_html}"
                        f"</td>"
                        f"<td style='padding:6px 4px; color:#fbbf24; font-weight:600; vertical-align:top;'>{f['frekuensi']}x</td>"
                        f"<td style='padding:6px 4px; color:#94a3b8; vertical-align:top;'>{f['persentase']}%</td>"
                        f"</tr>"
                    )
                absa_list_html += "</tbody></table></div>"
            else:
                absa_list_html = (
                    "<div style='margin-top:14px; padding:12px 16px; "
                    "background:rgba(56,189,248,0.06); border-radius:10px; "
                    "border:1px solid rgba(56,189,248,0.1);'>"
                    "<span style='color:#7dd3fc; font-size:0.85rem;'>ℹ️ "
                    "Tidak ditemukan keluhan spesifik dari teks ulasan untuk dimensi ini. "
                    "Skor rendah kemungkinan berasal dari penilaian skala Likert saja — "
                    "rekomendasi umum di atas tetap berlaku sebagai panduan perbaikan.</span>"
                    "</div>"
                )

            # --- Render Card ---
            dim_card_html = (
                f"<div class='dss-dim-analysis-card'>"
                f"<span class='{dim_badge_class}'>{dim_badge_text}</span>"
                f"<div class='dss-dim-analysis-name'>📐 {selected_label} ({selected_dim})</div>"
                f"<div class='dss-dim-analysis-score'>Skor Rata-rata: <strong>{selected_score:.2f}</strong> / 5.00</div>"
                f"<div class='dss-separator' style='border-color:rgba(56,189,248,0.15);'></div>"
                f"<div style='font-size:0.78rem; font-weight:700; color:#38bdf8; "
                f"text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px; margin-top:10px;'>"
                f"🔍 Analisis Fishbone 6M — Penyebab & Rekomendasi (Level Dimensi):</div>"
                f"{dim_table_html}"
                f"{absa_list_html}"
                f"</div>"
            )
            st.markdown(dim_card_html, unsafe_allow_html=True)
        else:
            st.info("📭 Belum ada data untuk analisis dimensi.")

    # ----------------------------------------------------------------
    # BARIS BARU: Rekomendasi DSS (FITUR 4)
    # ----------------------------------------------------------------
    with st.container(border=True):
        if True:
            st.markdown('<p class="section-header">💡 Rekomendasi Prioritas (DSS)</p>',
                        unsafe_allow_html=True)

            # Ambil ulasan bersentimen Negatif dari data terfilter
            df_neg_dss = df_filtered[df_filtered["sentimen_akhir"] == "Negatif"]
            ulasan_neg_dss = df_neg_dss["teks_ulasan"].dropna().tolist()

            if ulasan_neg_dss:
                # Hitung Top 3 kategori keluhan ABSA
                top_findings = extract_negative_findings(ulasan_neg_dss, top_n=3)

                if top_findings:
                    # Pilihan temuan untuk dilihat rekomendasinya
                    options = [f"{item['frasa']} ({item['frekuensi']} keluhan)" for item in top_findings]
                    selected_option = st.selectbox("Pilih Temuan untuk Rekomendasi:", options, key="dss_selectbox")
                    
                    selected_index = options.index(selected_option)
                    top = top_findings[selected_index]
                    
                    top_kategori = top["frasa"]          # nama kategori ABSA
                    top_freq = top["frekuensi"]

                    # Lookup Knowledge Base (case-insensitive key matching)
                    kb_entries = DSS_KNOWLEDGE_BASE.get(top_kategori)
                    if not kb_entries:
                        # Coba case-insensitive fallback
                        kb_lower = {k.lower(): v for k, v in DSS_KNOWLEDGE_BASE.items()}
                        kb_entries = kb_lower.get(top_kategori.lower(), [
                            {
                                "faktor": "Unknown",
                                "penyebab": "Belum tersedia analisis akar masalah untuk kategori ini.",
                                "rekomendasi": "Lakukan investigasi lanjutan terhadap keluhan ini."
                            }
                        ])

                    # Build table HTML for Fishbone
                    table_html = (
                        "<table style='width:100%; border-collapse:collapse; margin-top:10px; font-size:13px;'>"
                        "<thead>"
                        "<tr style='border-bottom:1px solid rgba(255,255,255,0.1); text-align:left;'>"
                        "<th style='padding:8px 4px; color:#94a3b8; font-weight:600;'>Faktor (6M)</th>"
                        "<th style='padding:8px 4px; color:#94a3b8; font-weight:600;'>Kemungkinan Penyebab</th>"
                        "<th style='padding:8px 4px; color:#94a3b8; font-weight:600;'>Rekomendasi Tindakan</th>"
                        "</tr>"
                        "</thead>"
                        "<tbody>"
                    )
                    for entry in kb_entries:
                        table_html += (
                            f"<tr style='border-bottom:1px solid rgba(255,255,255,0.05);'>"
                            f"<td style='padding:8px 4px; color:#38bdf8; font-weight:500; vertical-align:top;'>{entry['faktor']}</td>"
                            f"<td style='padding:8px 4px; color:#e2e8f0; vertical-align:top;'>{entry['penyebab']}</td>"
                            f"<td style='padding:8px 4px; color:#34d399; vertical-align:top;'>{entry['rekomendasi']}</td>"
                            f"</tr>"
                        )
                    table_html += "</tbody></table>"

                    # DSS Recommendation Card — premium styling
                    badge_text = "⚡ PRIORITAS UTAMA" if selected_index == 0 else "⚡ ALTERNATIF PRIORITAS"
                    html_card = (
                        f"<div class='dss-card'>"
                        f"<span class='dss-badge'>{badge_text}</span>"
                        f"<div class='dss-dim-name'>📌 {top_kategori}</div>"
                        f"<div class='dss-score'>Jumlah Keluhan: <strong>{top_freq}</strong> keluhan</div>"
                        f"<div class='dss-separator'></div>"
                        f"<div class='dss-label'>🔍 Analisis Fishbone & Rekomendasi Tindakan (DSS):</div>"
                        f"{table_html}"
                        f"</div>"
                    )
                    st.markdown(html_card, unsafe_allow_html=True)
                else:
                    st.success(
                        "✅ Tidak ada temuan kritis pada periode ini. "
                        "Pertahankan kualitas pelayanan!"
                    )
            else:
                st.success(
                    "✅ Tidak ada temuan kritis pada periode ini. "
                    "Pertahankan kualitas pelayanan!"
                )

    # ----------------------------------------------------------------
    # LOG TEMUAN KRITIS — EKSTRAKSI FRASA NEGATIF ASPECT-BASED (FITUR 5)
    # ----------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<p class="section-header">⚠️ Log Temuan Kritis (Aspect-Based)</p>',
                    unsafe_allow_html=True)

        # Ambil ulasan yang bersentimen Negatif dari data terfilter
        df_negatif = df_filtered[df_filtered["sentimen_akhir"] == "Negatif"]
        ulasan_negatif_list = df_negatif["teks_ulasan"].dropna().tolist()

        if ulasan_negatif_list:
            findings = extract_negative_findings(ulasan_negatif_list, top_n=3)

            if findings:
                # --- Horizontal Bar Chart: Top frasa temuan negatif ---
                df_findings = pd.DataFrame(findings)
                # Capitalize frasa untuk tampilan
                df_findings["frasa"] = df_findings["frasa"].str.capitalize()
                # Urutkan ascending agar bar terbesar di atas
                df_findings = df_findings.sort_values("frekuensi", ascending=True)

                fig_findings = px.bar(
                    df_findings,
                    x="frekuensi",
                    y="frasa",
                    orientation="h",
                    text=df_findings.apply(
                        lambda row: f"{row['frekuensi']}x ({row['persentase']}%)", axis=1
                    ),
                    color_discrete_sequence=["#34d399"],
                )
                fig_findings.update_layout(
                    height=max(300, len(df_findings) * 50),
                    xaxis_title="Frekuensi Kemunculan",
                    yaxis_title="",
                    showlegend=False,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter", size=13, color="#94a3b8"),
                    margin=dict(t=20, b=40, l=250, r=30),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                )
                fig_findings.update_traces(
                    textposition="outside",
                    textfont=dict(color="#e2e8f0"),
                    marker_line_width=0,
                    marker_cornerradius=8,
                )
                st.plotly_chart(fig_findings, use_container_width=True)

                st.caption(
                    f"Berdasarkan **{len(ulasan_negatif_list)}** ulasan bersentimen Negatif "
                    f"(dari {total_ulasan} ulasan terfilter). "
                    f"Frasa diekstrak secara otomatis dari konteks kalimat (kata benda + kata sifat negatif)."
                )

                # --- Detail ulasan asli per kategori ---
                for finding in findings:
                    kategori_nama = finding["frasa"].capitalize()
                    daftar_ulasan = finding.get("ulasan", [])
                    jumlah = finding["frekuensi"]

                    with st.expander(
                        f"📋 {kategori_nama} — {jumlah} ulasan",
                        expanded=False,
                    ):
                        if daftar_ulasan:
                            for idx, ulasan_teks in enumerate(daftar_ulasan, 1):
                                st.markdown(
                                    f"**{idx}.** {ulasan_teks}",
                                )
                            st.caption(f"Menampilkan {len(daftar_ulasan)} ulasan asli tamu.")
                        else:
                            st.info("Tidak ada data ulasan asli yang tersedia.")
            else:
                st.info("Tidak ditemukan frasa temuan negatif yang cocok dengan kamus leksikon.")
        else:
            st.success("🎉 Tidak ada ulasan bersentimen Negatif pada data yang terfilter.")

    # ----------------------------------------------------------------
    # TABEL DATA — termasuk kolom X1–X5 dan Jenis Reservasi
    # ----------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<p class="section-header">📋 Data Ulasan Tamu</p>', unsafe_allow_html=True)

        active_filters = []
        if filter_sentimen != "Semua":
            active_filters.append(f"Sentimen={filter_sentimen}")
        if filter_dimensi != "Semua":
            active_filters.append(f"Dimensi={filter_dimensi}")
        if filter_terbaru != "Semua Waktu":
            active_filters.append(f"Waktu={filter_terbaru}")
        if filter_reservasi != "Semua":
            active_filters.append(f"Reservasi={filter_reservasi}")

        total_semua = len(df)
        if active_filters:
            st.caption(
                f"🔎 Menampilkan {len(df_filtered)} dari {total_semua} ulasan "
                f"(Filter: {', '.join(active_filters)})"
            )
        else:
            st.caption(f"Menampilkan seluruh {total_semua} ulasan")

        # Pilih & rename kolom untuk tampilan
        display_cols = {
            "tanggal": "Tanggal",
            "nama_tamu": "Nama Tamu",
            "jenis_reservasi": "Jenis Reservasi",
            "rating_bintang": "Rating Bintang",
            "q1_reliability": "Q1 Reliability",
            "q2_assurance": "Q2 Assurance",
            "q3_tangibles": "Q3 Tangibles",
            "q4_empathy": "Q4 Empathy",
            "q5_responsiveness": "Q5 Responsiveness",
            "dimensi_terdeteksi": "Dimensi Terdeteksi",
            "sentimen_akhir": "Sentimen",
            "teks_ulasan": "Teks Ulasan",
        }
        df_display = df_filtered[list(display_cols.keys())].rename(columns=display_cols)

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "Tanggal": st.column_config.DateColumn(format="DD MMM YYYY"),
                "Rating Bintang": st.column_config.NumberColumn(format="%d ⭐"),
                "Q1 Reliability": st.column_config.NumberColumn(format="%d"),
                "Q2 Assurance": st.column_config.NumberColumn(format="%d"),
                "Q3 Tangibles": st.column_config.NumberColumn(format="%d"),
                "Q4 Empathy": st.column_config.NumberColumn(format="%d"),
                "Q5 Responsiveness": st.column_config.NumberColumn(format="%d"),
                "Sentimen": st.column_config.TextColumn(width="small"),
                "Jenis Reservasi": st.column_config.TextColumn(width="medium"),
            },
        )

        # --- Tombol Ekspor ke Excel ---
        import os
        import tempfile

        df_export = df_display.copy()
        # Konversi kolom Tanggal ke string
        if "Tanggal" in df_export.columns:
            df_export["Tanggal"] = pd.to_datetime(
                df_export["Tanggal"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")

        # Simpan ke file sementara di disk (cara yang terbukti berhasil)
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, "_feedback_export_temp.xlsx")
        df_export.to_excel(tmp_path, index=False, engine="openpyxl", sheet_name="Feedback")

        # Baca bytes dari file yang sudah tersimpan
        with open(tmp_path, "rb") as f:
            excel_bytes = f.read()

        # Hapus file sementara
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        timestamp_file = datetime.now(_WIB).strftime("%Y%m%d_%H%M%S")
        filename = f"feedback_data_{timestamp_file}.xlsx"

        st.download_button(
            label="📥 Ekspor ke Excel",
            data=excel_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_export_excel",
            use_container_width=True,
        )
