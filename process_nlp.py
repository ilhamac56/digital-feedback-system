"""
PROCESS — Modul Pemrosesan NLP & Analisis Sentimen
===================================================
Berisi logika analisis teks ulasan:
- Preprocessing teks (case folding, cleansing, tokenization, stopword removal)
- Klasifikasi dimensi SERVPERF (keyword matching)
- Klasifikasi sentimen (lexicon-based + rating override)
"""

import re
from collections import Counter


# ============================================================
# KAMUS KATA KUNCI
# ============================================================

DIMENSION_KEYWORDS = {
    "Tangibles": [
        # Kamar & tempat tidur
        "kamar", "bed", "kasur", "tempat tidur", "ranjang", "bantal", "selimut", "sprei",
        # Kebersihan
        "bersih", "kotor", "jorok", "kumuh", "dekil", "debu", "berdebu", "noda",
        # Fasilitas kamar
        "fasilitas", "ac", "air", "handuk", "sabun", "sampo", "shampoo", "shower",
        "toilet", "wc", "wastafel", "cermin", "lemari", "tv", "televisi", "wifi",
        "internet", "remote", "kulkas", "minibar", "hairdryer", "sandal",
        # Bangunan & area
        "bau", "luas", "sempit", "gedung", "bangunan", "lobby", "lobi", "parkir",
        "taman", "kolam", "pool", "renang", "restoran", "restaurant", "cafe", "kafe",
        "mushola", "masjid", "playground", "gazebo", "balkon", "teras",
        # Kondisi fisik
        "terawat", "rusak", "bocor", "lecek", "kusam", "lusuh", "usang", "tua",
        "baru", "modern", "renovasi", "cat", "dinding", "lantai", "atap", "plafon",
        "jendela", "pintu", "kunci", "lampu", "penerangan", "gelap", "terang",
        # Pemandangan & estetika
        "pemandangan", "view", "indah", "asri", "hijau", "alam", "sawah", "gunung",
        "sungai", "danau", "dekorasi", "desain", "interior", "estetik", "instagramable",
        # Amenities
        "hot spring", "pemandian", "spa", "sauna", "jacuzzi", "waterpark", "waterboom",
        "playground", "outbound", "meeting room", "ruang rapat", "ballroom",
    ],
    "Reliability": [
        # Kesesuaian janji
        "janji", "sesuai", "tidak sesuai", "ekspektasi", "harapan",
        "deskripsi", "foto", "gambar", "iklan", "promosi", "promo",
        # Harga & nilai
        "nilai", "harga", "tarif", "rate", "murah", "mahal", "worth", "worthit",
        "value", "sebanding", "sepadan", "wajar", "overpriced", "terjangkau",
        # Reservasi & booking
        "pesan", "booking", "reservasi", "konfirmasi", "voucher", "tiket",
        "check in", "checkin", "check out", "checkout",
        # Jadwal & konsistensi
        "jadwal", "waktu", "tepat", "telat", "terlambat", "on time", "konsisten",
        "standar", "kualitas", "mutu", "jaminan", "garansi",
        # Keandalan umum
        "andal", "handal", "terpercaya", "profesional", "akurat",
        "kesalahan", "salah", "keliru", "error", "sistem",
    ],
    "Responsiveness": [
        # Kecepatan
        "cepat", "lambat", "sigap", "respon", "responsif", "tanggap", "gesit", "gerak",
        # Waktu tunggu
        "lama", "tunggu", "antri", "antre", "jam", "menit", "menunggu", "nunggu",
        "instan", "segera", "langsung",
        # Pelayanan
        "layani", "melayani", "pelayanan", "servis", "service", "layanin",
        "room service", "housekeeping", "cleaning", "maintenance",
        # Ketanggapan
        "tanggap", "proaktif", "inisiatif", "spontan", "siap", "siaga",
        "follow up", "tindak lanjut", "ditindak", "diproses",
        # Keluhan
        "komplain", "aduan", "lapor", "request", "permintaan", "minta",
        "diabaikan", "diacuhkan", "cuek", "masa bodoh",
    ],
    "Assurance": [
        # Keamanan
        "aman", "keamanan", "security", "satpam", "kunci", "brankas", "safe",
        "cctv", "pencurian", "hilang", "kehilangan",
        # Kenyamanan
        "nyaman", "kenyamanan", "tenang", "damai", "tenteram", "betah",
        "rileks", "relax", "santai",
        # Keramahan & kesopanan
        "ramah", "sopan", "ketus", "jutek", "judes", "galak", "kasar",
        "hormat", "menghormati", "hangat", "welcome", "sambut", "menyambut",
        "sapa", "menyapa", "salam",
        # Kompetensi staf
        "kompeten", "terlatih", "berpengalaman", "ahli", "mahir",
        "terampil", "pintar", "cerdas", "capable",
        # Kepercayaan
        "percaya", "terpercaya", "trust", "jujur", "transparan",
        "kredibel", "reputasi", "bintang",
    ],
    "Empathy": [
        # Perhatian personal
        "perhatian", "peduli", "empati", "care", "caring", "pengertian",
        "memahami", "paham", "mengerti", "sensitif",
        # Bantuan
        "bantu", "membantu", "dibantu", "bantuin", "tolong", "menolong",
        "ditolong", "assist",
        # Keramahan personal
        "personal", "senyum", "tersenyum", "tulus", "ikhlas", "sabar",
        "lembut", "halus", "bijak",
        # Kebutuhan khusus
        "spesial", "special", "khusus", "custom", "request",
        "disabilitas", "difabel", "anak", "bayi", "lansia",
        "alergi", "vegetarian", "vegan", "halal",
        # Komunikasi
        "komunikasi", "jelaskan", "informasi", "info", "arahan", "panduan",
        "guide", "sarankan", "rekomendasi", "suggest",
        "dengar", "mendengar", "dengarkan", "keluh",
    ],
}

POSITIVE_KEYWORDS = [
    # Kebersihan & kondisi
    "bersih", "terawat", "rapi", "higienis", "steril", "wangi", "harum",
    "mulus", "baru", "segar",
    # Keramahan & pelayanan
    "ramah", "sopan", "hangat", "welcome", "menyambut", "senyum",
    "tulus", "ikhlas", "sabar", "lembut",
    # Kecepatan & tanggap
    "cepat", "sigap", "responsif", "tanggap", "gesit", "proaktif",
    "inisiatif", "siap", "siaga",
    # Kenyamanan
    "nyaman", "tenang", "damai", "betah", "rileks", "santai",
    "sejuk", "adem", "dingin",
    # Kualitas
    "bagus", "baik", "mantap", "oke", "ok", "top", "hebat", "keren",
    "istimewa", "luar biasa", "fantastis", "sempurna", "prima",
    "excellent", "amazing", "wonderful", "great", "good", "nice", "perfect",
    # Pengalaman
    "enak", "puas", "memuaskan", "senang", "suka", "bahagia", "gembira",
    "menyenangkan", "berkesan", "memorable", "unforgettable",
    # Estetika
    "indah", "cantik", "asri", "hijau", "eksotis", "estetik",
    "instagramable", "fotogenik", "menawan", "mempesona", "memukau",
    # Makanan
    "lezat", "enak", "nikmat", "sedap", "gurih", "segar", "fresh",
    "variatif", "lengkap", "melimpah", "porsi besar",
    # Rekomendasi
    "terbaik", "recommended", "rekomen", "rekomendasi", "worth",
    "worthit", "sepadan", "sebanding", "terjangkau", "murah",
    # Ukuran & ruang
    "luas", "lapang", "spacious", "besar", "megah",
    # Bantuan
    "membantu", "dibantu", "menolong", "helpful",
    # Fasilitas
    "lengkap", "komplit", "modern", "canggih", "update",
    # Umum positif
    "terima kasih", "makasih", "thanks", "thank you",
    "kembali", "balik", "lagi", "repeat",
    "aman", "terpercaya", "profesional", "kompeten",
]

NEGATIVE_KEYWORDS = [
    # Kebersihan
    "kotor", "jorok", "kumuh", "dekil", "buluk", "bau", "apek", "pengap",
    "lembab", "jamur", "berjamur", "berdebu", "debu", "noda", "bernoda",
    "sampah", "berantakan", "semrawut", "acak-acakan",
    # Kerusakan
    "rusak", "bocor", "pecah", "retak", "patah", "copot", "lepas",
    "macet", "error", "mati", "jebol", "robek",
    "ancur", "hancur", "rontok",
    # Kondisi buruk
    "lecek", "kusam", "lusuh", "usang", "tua", "lapuk", "karatan",
    "gelap", "remang", "suram", "pudar", "luntur",
    # Ukuran & ruang
    "sempit", "kecil", "sesak", "sumpek", "penuh", "padat",
    # Kecepatan
    "lambat", "lama", "lemot", "molor", "telat", "terlambat",
    # Sikap staf
    "ketus", "jutek", "judes", "galak", "kasar", "sombong", "angkuh",
    "cuek", "acuh", "masa bodoh", "malas", "ogah",
    "tidak ramah", "gak ramah",
    # Kebisingan
    "berisik", "ribut", "bising", "gaduh", "ramai", "keras",
    # Harga
    "mahal", "kemahalan", "overpriced", "overprice", "rugi", "merugikan",
    # Kekecewaan
    "kurang", "kecewa", "mengecewakan", "menyesal", "kapok",
    "jelek", "buruk", "payah", "parah", "ampun", "astaga",
    "terrible", "worst", "bad", "horrible", "awful", "poor", "dirty",
    # Keluhan & komplain
    "komplain", "keluhan", "keluh", "protes", "aduan",
    "ganggu", "terganggu", "mengganggu",
    # Kesulitan
    "susah", "sulit", "ribet", "repot", "rumit",
    # Ketidaksesuaian
    "tidak sesuai", "gak sesuai", "beda", "berbeda", "zonk", "bohong", "tipu", "menipu",
    "palsu", "abal", "hoax",
    # Negasi umum (pembobot)
    "tidak", "tdk", "gak", "nggak", "nga", "ga", "ngga", "enggak",
    "belum", "blm", "bukan", "jangan",
    "tanpa", "tak", "kagak",
    # Keamanan
    "hilang", "kehilangan", "dicuri", "pencurian", "bahaya", "berbahaya",
    # Makanan
    "hambar", "basi", "tengik", "mentah", "gosong", "asin", "kecut",
    # Kondisi umum
    "biasa", "standar", "so so", "lumayan",
]

STOPWORDS_ID = {
    # Kata hubung
    "di", "ke", "dari", "yang", "dan", "atau", "tapi", "tetapi", "namun",
    # Kata depan & partikel
    "ini", "itu", "nya", "lah", "kah", "pun", "pula", "juga",
    "dengan", "untuk", "pada", "oleh", "akan", "telah", "sudah",
    "sedang", "masih", "bisa", "dapat", "harus", "perlu",
    # Kata ganti
    "saya", "aku", "kita", "kami", "mereka", "dia", "ia", "beliau",
    "kamu", "anda", "kalian",
    # Kata bantu
    "adalah", "ialah", "yaitu", "yakni", "merupakan",
    "ada", "saat", "ketika", "serta", "maupun", "ataupun",
    "begitu", "jadi", "maka", "karena", "sebab", "agar", "supaya",
    "jika", "kalau", "bila", "apabila", "walau", "meski", "walaupun",
    "seperti", "bagai", "seolah", "selain", "hanya", "saja", "sih",
    "dong", "deh", "kok", "kan", "banget", "sangat", "sekali",
}


# ============================================================
# FUNGSI PREPROCESSING
# ============================================================

def _preprocess_text(text: str) -> list[str]:
    """
    Pra-pemrosesan teks ulasan:
    1. Case folding (lowercase)
    2. Cleansing (hapus tanda baca & angka)
    3. Tokenization (split by space)
    4. Stopword removal (kata hubung dasar Bahasa Indonesia)
    Tanpa stemming.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return []

    # 1. Case Folding
    text = text.lower()

    # 2. Cleansing — hanya sisakan alfabet dan spasi
    text = re.sub(r"[^a-z\s]", "", text)

    # 3. Tokenization
    tokens = text.split()

    # 4. Stopword Removal
    tokens = [t for t in tokens if t not in STOPWORDS_ID]

    return tokens


# ============================================================
# FUNGSI KLASIFIKASI
# ============================================================

def _classify_dimensions(tokens: list[str]) -> list[str]:
    """Deteksi dimensi SERVPERF berdasarkan keyword matching."""
    detected = []
    for dimension, keywords in DIMENSION_KEYWORDS.items():
        if any(token in keywords for token in tokens):
            detected.append(dimension)
    return detected


def _classify_sentiment(tokens: list[str], rating: int) -> str:
    """
    Klasifikasi sentimen berdasarkan heuristik kata kunci
    dan rating override rule.
    """
    pos_count = sum(1 for t in tokens if t in POSITIVE_KEYWORDS)
    neg_count = sum(1 for t in tokens if t in NEGATIVE_KEYWORDS)

    # Jika ada kata negatif → langsung Negatif
    if neg_count > 0:
        sentiment = "Negatif"
    elif pos_count > 0:
        sentiment = "Positif"
    else:
        sentiment = "Netral"

    # RATING OVERRIDE RULE
    if rating >= 4:
        sentiment = "Positif"
    elif rating <= 2:
        sentiment = "Negatif"
    elif rating == 3 and sentiment == "Positif":
        sentiment = "Netral"

    return sentiment


# ============================================================
# FUNGSI UTAMA ANALISIS
# ============================================================

def analyze_feedback(teks: str, rating_bintang: int) -> tuple[str, str]:
    """
    Fungsi modular utama untuk analisis feedback.
    Digunakan oleh form tamu (manual) maupun upload Excel (batch).

    Args:
        teks: Teks ulasan dari tamu.
        rating_bintang: Rating bintang (1-5).

    Returns:
        Tuple (dimensi_terdeteksi, sentimen_akhir)
    """
    tokens = _preprocess_text(teks)
    dimensions = _classify_dimensions(tokens)
    sentiment = _classify_sentiment(tokens, rating_bintang)

    dim_str = ", ".join(dimensions) if dimensions else "Tidak Terdeteksi"
    return dim_str, sentiment


# ============================================================
# FUNGSI EKSTRAKSI FRASA TEMUAN NEGATIF — ASPECT-BASED (FITUR 5)
# ============================================================

# Kata penghubung untuk memecah kalimat menjadi fragmen
_SPLIT_CONJUNCTIONS = [
    "tetapi", "namun", "tapi", "akan tetapi", "meskipun",
    "walaupun", "sedangkan", "sementara", "padahal",
]


def _split_into_fragments(text: str) -> list[str]:
    """
    Memecah teks ulasan menjadi fragmen-fragmen kalimat berdasarkan
    tanda baca (. , ; !) dan konjungsi (tetapi, namun, tapi, dll).
    """
    if not text or not isinstance(text, str):
        return []

    text = text.lower().strip()

    # Ganti konjungsi dengan delimiter khusus sebelum split
    for conj in _SPLIT_CONJUNCTIONS:
        text = text.replace(conj, " |SPLIT| ")

    # Ganti tanda baca pemisah dengan delimiter
    text = re.sub(r"[.,;!?]+", " |SPLIT| ", text)

    # Split dan bersihkan
    fragments = [f.strip() for f in text.split("|SPLIT|") if f.strip()]
    return fragments


# Kategori Temuan Baku — 25 Kategori Final (Tanpa Label Dimensi)
# Berdasarkan temuan magang & terhubung ke temuan DFS
ABSA_CATEGORIES = [
    {
        "name": "Tidak ada AC",
        "nouns": ["ac", "pendingin", "pendingin ruangan", "air conditioner"],
        "negatives": ["tidak ada", "belum ada", "tidak tersedia", "tidak disediakan", "tidak dipasang", "ga ada", "gak ada", "tanpa"]
    },
    {
        "name": "Fasilitas kamar tidak memadai",
        "nouns": ["fasilitas", "tv", "kulkas", "lemari", "cermin", "remote", "remot", "stop kontak", "gorden",
                  "kasur", "bantal", "selimut", "sprei", "ranjang", "tempat tidur", "bed", "flush", "kunci", "pintu", "chanel tv"],
        "negatives": ["rusak", "tidak memadai", "kurang", "jelek", "tidak fungsi", "tidak nyala", "jebol", "copot",
                      "lepas", "pecah", "retak", "macet", "error", "mati", "bocor", "tidak berfungsi", "kurang lengkap",
                      "tidak layak", "buruk", "usang", "tua", "kusam", "lecek", "keras"]
    },
    {
        "name": "Serangga dan hewan pengganggu",
        "nouns": ["serangga", "nyamuk", "kecoa", "kecoak", "semut", "lalat", "laba laba", "laba-laba", "tikus",
                  "cicak", "tokek", "kutu", "rayap", "ulat", "hewan", "binatang", "bug", "kutu busuk"],
        "negatives": ["banyak", "ada", "masuk", "mengganggu", "terganggu", "berkeliaran", "muncul", "ditemukan",
                      "gigit", "digigit", "bertebaran", "sarang", "kotor"]
    },
    {
        "name": "Variasi dan rasa makanan kurang",
        "nouns": ["makanan", "sarapan", "menu", "rasa", "makan", "breakfast", "buffet", "masakan", "lauk",
                  "hidangan", "nasi", "roti", "kopi", "teh", "snack"],
        "negatives": ["hambar", "kurang variasi", "kurang enak", "tidak enak", "sedikit", "monoton", "itu-itu saja",
                      "sama", "kurang", "basi", "dingin", "asin", "keras", "standar", "biasa", "habis", "kurang rasa",
                      "tidak variatif", "membosankan", "kurang bumbu"]
    },
    {
        "name": "Kamar mandi/toilet kurang bersih",
        "nouns": ["toilet", "wc", "kamar mandi", "wastafel", "shower", "closet", "kloset", "bathub", "bathtub",
                  "kran", "lantai kamar mandi", "saluran air"],
        "negatives": ["kotor", "bau", "jorok", "apek", "noda", "bercak", "lembab", "jamur", "kusam", "licin",
                      "buluk", "mampet", "tersumbat", "kurang bersih", "tidak bersih", "berkerak", "lumut"]
    },
    {
        "name": "Kebersihan kamar kurang",
        "nouns": ["kamar", "lantai", "kaca", "dinding", "karpet", "meja", "debu"],
        "negatives": ["kotor", "bau", "jorok", "debu", "berdebu", "apek", "noda", "bercak", "lembab", "jamur",
                      "kusam", "berantakan", "buluk", "kurang bersih", "tidak bersih", "dekil", "lengket", "belum dipel"]
    },
    {
        "name": "Sanitasi kolam ikan kurang terjaga",
        "nouns": ["kolam ikan", "ikan", "air kolam"],
        "negatives": ["kotor", "keruh", "bau", "jorok", "lumut", "tidak terawat", "kurang terawat", "hijau",
                      "berlumut", "mati", "sampah", "kurang terjaga", "tidak terjaga"]
    },
    {
        "name": "Kualitas pelayanan staf kurang",
        "nouns": ["staf", "staff", "pelayanan", "resepsionis", "layanan", "karyawan", "petugas", "security",
                  "satpam", "receptionist", "pegawai", "servis", "service"],
        "negatives": ["lambat", "lama", "ketus", "jutek", "kurang ramah", "tidak ramah", "kasar", "judes",
                      "sombong", "buruk", "mengecewakan", "lelet", "cuek", "tidak peduli", "mengabaikan",
                      "masa bodoh", "tidak membantu", "abai", "acuh", "tidak tanggap", "kurang", "galak"]
    },
    {
        "name": "Kebersihan lingkungan resort kurang",
        "nouns": ["lingkungan", "halaman", "taman", "area", "jalan", "lorong", "koridor", "lobby", "lobi",
                  "resort", "outdoor"],
        "negatives": ["kotor", "sampah", "bau", "jorok", "kusam", "becek", "kurang bersih", "tidak bersih",
                      "tidak terawat", "kurang terawat", "berantakan", "kumuh", "berserakan"]
    },
    {
        "name": "Penerangan kamar dan lingkungan kurang",
        "nouns": ["lampu", "penerangan", "cahaya", "teras", "balkon"],
        "negatives": ["gelap", "remang", "redup", "kurang", "mati", "rusak", "tidak nyala", "suram",
                      "kurang terang", "tidak terang", "temaram"]
    },
    {
        "name": "Gangguan lingkungan",
        "nouns": ["suasana", "suara", "malam", "tetangga", "musik", "konstruksi", "ayam", "hewan"],
        "negatives": ["berisik", "bising", "ribut", "gaduh", "ramai", "tidak nyaman", "kurang nyaman",
                      "terganggu", "kedengaran", "tembus", "keras", "mengganggu", "gangguan"]
    },
    {
        "name": "Koneksi WiFi tidak stabil",
        "nouns": ["wifi", "internet", "koneksi", "sinyal", "jaringan", "wi-fi", "wi fi"],
        "negatives": ["lemot", "lambat", "putus", "hilang", "susah", "jelek", "kurang", "tidak konek",
                      "mati", "error", "tidak stabil", "sering putus", "tidak ada", "sulit"]
    },
    {
        "name": "Kolam rendam kurang panas",
        "nouns": ["kolam rendam", "kolam air panas", "pemandian", "air panas", "air hangat", "hot spring",
                  "water heater", "kolam panas", "rendam"],
        "negatives": ["kurang panas", "tidak panas", "dingin", "kurang hangat", "tidak hangat", "suam",
                      "suam-suam", "biasa saja", "kurang", "tidak terasa"]
    },
    {
        "name": "Lantai kamar berbunyi saat dipijak",
        "nouns": ["lantai kayu", "papan", "kayu"],
        "negatives": ["bunyi", "berbunyi", "berderit", "derit", "goyang", "gerak", "bergoyang",
                      "tidak kokoh", "keropos", "lapuk", "berisik", "berdecit", "bersuara"]
    },
    {
        "name": "Jarak akses pintu masuk ke unit jauh",
        "nouns": ["akses", "pintu masuk", "jalan masuk", "gerbang", "pintu", "jarak", "unit",
                  "lokasi", "area"],
        "negatives": ["jauh", "terlalu jauh", "susah", "sulit", "panjang", "capek", "capai", "lelah",
                      "tidak mudah", "ribet", "memutar", "jalan kaki"]
    },
    {
        "name": "Desain kamar kurang ergonomis",
        "nouns": ["desain", "layout", "tata letak", "interior", "ukuran"],
        "negatives": ["sempit", "kecil", "sesak", "sumpek", "tidak ergonomis", "kurang ergonomis",
                      "tidak nyaman", "aneh", "kurang pas", "tidak praktis", "kurang luas"]
    },
    {
        "name": "Sirkulasi udara kamar kurang",
        "nouns": ["sirkulasi", "ventilasi", "jendela", "angin"],
        "negatives": ["pengap", "sumpek", "tidak ada", "kurang", "sesak", "panas", "gerah", "lembab",
                      "tertutup", "tidak ada ventilasi", "kurang sirkulasi", "душно"]
    },
    {
        "name": "Keamanan kolam kurang terjamin",
        "nouns": ["kolam renang", "pool", "renang", "kolam anak", "pengawas", "pagar"],
        "negatives": ["bahaya", "berbahaya", "tidak aman", "kurang aman", "licin", "dalam", "terlalu dalam",
                      "tidak ada pagar", "tidak ada pengawas", "rawan", "khawatir", "takut"]
    },
    {
        "name": "Kebersihan tempat makan/restoran kurang",
        "nouns": ["restoran", "restaurant", "resto", "tempat makan", "meja makan", "ruang makan", "cafe",
                  "kafe", "kantin", "dining"],
        "negatives": ["kotor", "bau", "jorok", "kurang bersih", "tidak bersih", "berantakan", "kumuh",
                      "berserakan", "lengket", "noda", "debu", "lalat"]
    },
    {
        "name": "Restoran terlalu kecil",
        "nouns": ["restoran", "restaurant", "resto", "tempat makan", "ruang makan", "cafe", "kafe",
                  "dining", "area makan"],
        "negatives": ["kecil", "sempit", "sesak", "penuh", "padat", "tidak cukup", "kurang luas",
                      "terbatas", "tidak muat", "antri", "antre"]
    },
    {
        "name": "Parkir kurang memadai",
        "nouns": ["parkir", "lahan parkir", "tempat parkir", "garasi", "kendaraan", "area parkir"],
        "negatives": ["sempit", "kurang", "penuh", "susah", "sulit", "jauh", "tidak ada", "terbatas",
                      "panas", "tidak memadai", "kurang luas", "kurang memadai"]
    },
    {
        "name": "Informasi fasilitas kurang jelas",
        "nouns": ["informasi", "info", "komunikasi", "penjelasan", "arahan", "panduan", "petunjuk",
                  "aturan", "prosedur", "pemberitahuan", "fasilitas", "jam", "jadwal", "operasional"],
        "negatives": ["kurang jelas", "tidak jelas", "bingung", "membingungkan", "salah informasi",
                      "tidak ada", "tidak diberitahu", "tidak dikasih tahu", "misinformasi", "kurang",
                      "tidak ada info", "tidak ada informasi"]
    },
    {
        "name": "Perlengkapan kamar (toiletries) kurang lengkap",
        "nouns": ["toiletries", "perlengkapan", "amenities", "handuk", "sabun", "sampo", "shampoo",
                  "sikat gigi", "pasta gigi", "sandal", "tisu", "tissue", "hairdryer", "hair dryer"],
        "negatives": ["kurang", "tidak ada", "habis", "tidak lengkap", "kurang lengkap", "tidak disediakan",
                      "tidak tersedia", "sedikit", "kosong", "belum diisi"]
    },
    {
        "name": "Fasilitas belanja sekitar resort tidak tersedia",
        "nouns": ["belanja", "toko", "warung", "minimarket", "indomaret", "alfamart", "oleh oleh",
                  "oleh-oleh", "souvenir", "jajanan"],
        "negatives": ["tidak ada", "tidak tersedia", "jauh", "susah", "sulit", "tidak ditemukan", "kosong",
                      "sepi", "tutup", "kurang", "terbatas"]
    },
    {
        "name": "Kamar panas",
        "nouns": ["suhu", "temperatur"],
        "negatives": ["panas", "gerah", "sumuk", "kepanasan", "tidak sejuk", "kurang sejuk",
                      "tidak dingin", "душно", "terik", "menyengat"]
    },
]

def _extract_categories_from_fragment(fragment: str) -> list[str]:
    """
    Memetakan fragmen kalimat ke dalam Kategori Keluhan Baku (ABSA_CATEGORIES).
    Dapat mengembalikan lebih dari 1 kategori jika terdapat keluhan ganda (misal: "wifi dan tv rusak").
    """
    clean = fragment.lower()
    # Hapus suffix "-nya" agar kata seperti "mandinya" cocok dengan "mandi"
    clean = re.sub(r"nya\b", "", clean)
    clean = re.sub(r"[^a-z\s]", "", clean)
    tokens = clean.split()
    if not tokens:
        return []

    # Bi-grams dan Tri-grams untuk pencocokan multi-kata
    token_phrases = tokens.copy()
    for i in range(len(tokens) - 1):
        token_phrases.append(f"{tokens[i]} {tokens[i+1]}")
    for i in range(len(tokens) - 2):
        token_phrases.append(f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}")

    results = set()

    # Prioritaskan Kategori Spesifik
    for category in ABSA_CATEGORIES:
        has_noun = any(noun in token_phrases for noun in category["nouns"])
        has_negative = any(neg in token_phrases for neg in category["negatives"])
        
        # Jika ketemu kombinasi kata benda dan keluhan yang cocok
        if has_noun and has_negative:
            results.add(category["name"])

    # Resolusi Konflik Konteks (Mencegah overlapping kata "kamar" dan "kamar mandi")
    if "Kamar mandi/toilet kurang bersih" in results:
        results.discard("Kebersihan kamar kurang")
        results.discard("Fasilitas kamar tidak memadai")
        
    if "Kebersihan tempat makan/restoran kurang" in results or "Variasi dan rasa makanan kurang" in results:
        results.discard("Fasilitas kamar tidak memadai")
        
    if "Sanitasi kolam ikan kurang terjaga" in results or "Keamanan kolam kurang terjamin" in results or "Kolam rendam kurang panas" in results:
        results.discard("Kebersihan kamar kurang")

    if results:
        return list(results)

    # Fallback: Jika tidak ada noun, tapi ada negative yang sangat spesifik
    # Contoh: "Kotor banget", "Resepsionisnya jutek"
    for category in ABSA_CATEGORIES:
        has_negative = any(neg in token_phrases for neg in category["negatives"])
        if has_negative:
            # Jika keluhannya "hambar", "basi", pasti tentang makanan
            if any(neg in ["hambar", "basi", "asin", "kurang bumbu", "kurang rasa"] for neg in token_phrases):
                return ["Variasi dan rasa makanan kurang"]
            # Jika keluhannya "bocor", "rusak", "macet", pasti fasilitas kamar
            if any(neg in ["bocor", "rusak", "macet", "jebol", "copot"] for neg in token_phrases):
                return ["Fasilitas kamar tidak memadai"]
            # Jika keluhannya "panas", "gerah" + konteks kamar
            if any(neg in ["panas", "gerah", "sumuk", "kepanasan"] for neg in token_phrases):
                if any(noun in token_phrases for noun in ["ac", "pendingin"]):
                    return ["Tidak ada AC"]
                return ["Kamar panas"]
            # Jika keluhannya "ketus", "jutek", pasti staf
            if any(neg in ["ketus", "jutek", "judes", "tidak ramah", "kasar", "sombong", "galak"] for neg in token_phrases):
                return ["Kualitas pelayanan staf kurang"]
            # Jika keluhannya "berisik", "bising", pasti gangguan lingkungan
            if any(neg in ["berisik", "bising", "gaduh", "ribut", "mengganggu"] for neg in token_phrases):
                return ["Gangguan lingkungan"]
            # Jika keluhannya "kotor", "bau", "jorok" + cek konteks
            if any(neg in ["kotor", "bau", "jorok", "apek", "buluk", "mampet"] for neg in token_phrases):
                if any(noun in token_phrases for noun in ["toilet", "wc", "kamar mandi", "wastafel", "closet", "kloset"]):
                    return ["Kamar mandi/toilet kurang bersih"]
                if any(noun in token_phrases for noun in ["restoran", "resto", "tempat makan", "meja makan"]):
                    return ["Kebersihan tempat makan/restoran kurang"]
                if any(noun in token_phrases for noun in ["kolam", "pool", "taman", "lobby", "lingkungan"]):
                    return ["Kebersihan lingkungan resort kurang"]
                return ["Kebersihan kamar kurang"]
            # Jika keluhannya "lemot", "putus", pasti wifi
            if any(neg in ["lemot", "putus", "tidak konek", "tidak stabil", "sering putus"] for neg in token_phrases):
                return ["Koneksi WiFi tidak stabil"]
            # Jika keluhannya "cuek", "tidak peduli", pasti staf
            if any(neg in ["cuek", "tidak peduli", "mengabaikan", "acuh", "abai"] for neg in token_phrases):
                return ["Kualitas pelayanan staf kurang"]
            # Jika keluhannya "gelap", "remang", pasti penerangan
            if any(neg in ["gelap", "remang", "redup", "suram", "temaram"] for neg in token_phrases):
                return ["Penerangan kamar dan lingkungan kurang"]
            # Jika keluhannya "nyamuk", "kecoa", pasti serangga
            if any(neg in ["nyamuk", "kecoa", "kecoak", "semut", "lalat", "tikus"] for neg in token_phrases):
                return ["Serangga dan hewan pengganggu"]
            # Jika keluhannya "pengap", "sumpek", pasti sirkulasi
            if any(neg in ["pengap", "sumpek"] for neg in token_phrases):
                return ["Sirkulasi udara kamar kurang"]
            # Jika keluhannya "bunyi", "berderit", pasti lantai
            if any(neg in ["bunyi", "berbunyi", "berderit", "berdecit"] for neg in token_phrases):
                return ["Lantai kamar berbunyi saat dipijak"]
            # Jika keluhannya "tidak jelas", "bingung" + konteks info
            if any(neg in ["tidak jelas", "membingungkan", "salah informasi", "misinformasi"] for neg in token_phrases):
                return ["Informasi fasilitas kurang jelas"]
            # Jika keluhannya "sempit" + konteks kamar
            if any(neg in ["sempit", "kecil", "sesak", "sumpek"] for neg in token_phrases):
                if any(noun in token_phrases for noun in ["restoran", "resto", "tempat makan"]):
                    return ["Restoran terlalu kecil"]
                if any(noun in token_phrases for noun in ["parkir", "lahan parkir"]):
                    return ["Parkir kurang memadai"]
                return ["Desain kamar kurang ergonomis"]

    # Jika tidak cocok dengan kategori mana pun, abaikan
    return []


def extract_negative_findings(ulasan_negatif: list[str], top_n: int = 10) -> list[dict]:
    """
    Mengekstrak Kategori Temuan Negatif baku dari seluruh ulasan bersentimen Negatif.

    Returns:
        List of dict [{"frasa": str, "frekuensi": int, "persentase": float, "ulasan": list[str]}]
    """
    category_counter = Counter()
    category_reviews: dict[str, list[str]] = {}  # Menyimpan ulasan asli per kategori

    for teks in ulasan_negatif:
        fragments = _split_into_fragments(teks)
        seen_in_review = set()

        for fragment in fragments:
            categories = _extract_categories_from_fragment(fragment)
            for category in categories:
                if category not in seen_in_review:
                    category_counter[category] += 1
                    seen_in_review.add(category)

                # Simpan ulasan asli (hindari duplikat teks yang sama)
                if category not in category_reviews:
                    category_reviews[category] = []
                if teks not in category_reviews[category]:
                    category_reviews[category].append(teks)

    total_findings = sum(category_counter.values())
    if total_findings == 0:
        return []

    results = []
    for kategori, freq in category_counter.most_common(top_n):
        results.append({
            "frasa": kategori,  # Tetap pakai key "frasa" agar tidak perlu ubah dashboard UI
            "frekuensi": freq,
            "persentase": round(freq / total_findings * 100, 1),
            "ulasan": category_reviews.get(kategori, []),
        })

    return results



