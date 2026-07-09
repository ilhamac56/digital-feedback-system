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
    if rating <= 2:
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

# Kamus kata benda (subjek/objek) umum dalam konteks ulasan hotel
NOUN_KEYWORDS = {
    # Kamar & tempat tidur
    "kamar", "kamar mandi", "bed", "kasur", "tempat tidur", "ranjang",
    "bantal", "selimut", "sprei", "handuk",
    # Fasilitas
    "ac", "air", "air panas", "air hangat", "shower", "toilet", "wc",
    "wastafel", "tv", "televisi", "wifi", "internet", "kulkas", "minibar",
    "remote", "lampu", "kunci", "pintu", "jendela", "cermin", "lemari",
    # Bangunan & area
    "lobby", "lobi", "parkir", "taman", "kolam", "kolam renang",
    "restoran", "restaurant", "cafe", "kafe", "mushola", "playground",
    "gazebo", "balkon", "teras", "lantai", "dinding", "atap", "plafon",
    # Staf & pelayanan
    "staf", "staff", "karyawan", "resepsionis", "pelayan", "petugas",
    "pelayanan", "layanan", "servis", "service",
    "room service", "housekeeping", "cleaning", "front office",
    # Makanan
    "makanan", "sarapan", "breakfast", "makan", "menu", "masakan",
    "minuman", "kopi", "nasi", "roti", "buah",
    # Fasilitas rekreasi
    "spa", "sauna", "pemandian", "hot spring", "waterpark", "waterboom",
    # Umum
    "harga", "tarif", "biaya", "fasilitas", "lingkungan", "area",
    "suasana", "pemandangan", "view", "kebersihan", "keamanan",
    "lokasi", "akses", "jalan",
}

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


def _extract_phrase_from_fragment(fragment: str) -> str | None:
    """
    Dari satu fragmen kalimat, ekstrak frasa 'kata benda + kata sifat negatif'.
    Mengembalikan frasa kontekstual atau None jika tidak cocok.

    Logika:
    1. Cek apakah fragmen mengandung kata sifat negatif.
    2. Jika ya, cari kata benda yang ada dalam fragmen.
    3. Gabungkan kata benda + kata sifat negatif menjadi frasa.
    """
    # Bersihkan fragmen — hanya alfabet dan spasi
    clean = re.sub(r"[^a-z\s]", "", fragment)
    tokens = clean.split()

    if not tokens:
        return None

    # Cari kata negatif dalam fragmen
    negative_set = set(NEGATIVE_KEYWORDS)
    found_negatives = [t for t in tokens if t in negative_set]

    if not found_negatives:
        return None

    # Cari kata benda (frasa) dalam fragmen — cek frasa multi-kata dulu
    found_noun = None
    # Coba frasa 3-kata, lalu 2-kata, lalu 1-kata
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            candidate = " ".join(tokens[i:i + n])
            if candidate in NOUN_KEYWORDS:
                found_noun = candidate
                break
        if found_noun:
            break

    # Ambil kata negatif utama (yang pertama ditemukan dalam fragmen)
    primary_negative = found_negatives[0]

    if found_noun:
        # Gabungkan: "kamar mandi" + "kotor" → "kamar mandi kotor"
        phrase = f"{found_noun} {primary_negative}"
    else:
        # Tidak ada kata benda eksplisit — gunakan konteks sekitar kata negatif
        # Ambil 1-2 kata sebelum kata negatif sebagai konteks
        neg_idx = None
        for i, t in enumerate(tokens):
            if t == primary_negative:
                neg_idx = i
                break

        if neg_idx is not None and neg_idx > 0:
            # Ambil hingga 2 kata sebelumnya sebagai konteks
            start = max(0, neg_idx - 2)
            context_tokens = tokens[start:neg_idx + 1]
            phrase = " ".join(context_tokens)
        else:
            phrase = primary_negative

    return phrase


def extract_negative_findings(ulasan_negatif: list[str], top_n: int = 10) -> list[dict]:
    """
    Mengekstrak frasa temuan negatif (aspect-based) dari seluruh ulasan
    yang terdeteksi bersentimen Negatif.

    Logika:
    1. Pecah setiap ulasan menjadi fragmen kalimat.
    2. Dari setiap fragmen yang mengandung kata sifat negatif,
       ekstrak frasa kontekstual (kata benda + kata sifat negatif).
    3. Hitung frekuensi kemunculan frasa tersebut.

    Args:
        ulasan_negatif: List teks ulasan bersentimen Negatif.
        top_n: Jumlah frasa teratas yang dikembalikan.

    Returns:
        List of dict [{"frasa": str, "frekuensi": int, "persentase": float}]
        diurutkan dari frekuensi tertinggi.
    """
    phrase_counter = Counter()

    for teks in ulasan_negatif:
        fragments = _split_into_fragments(teks)
        seen_in_review = set()  # Hindari duplikasi dari satu ulasan

        for fragment in fragments:
            phrase = _extract_phrase_from_fragment(fragment)
            if phrase and phrase not in seen_in_review:
                phrase_counter[phrase] += 1
                seen_in_review.add(phrase)

    total_findings = sum(phrase_counter.values())
    if total_findings == 0:
        return []

    results = []
    for frasa, freq in phrase_counter.most_common(top_n):
        results.append({
            "frasa": frasa,
            "frekuensi": freq,
            "persentase": round(freq / total_findings * 100, 1),
        })

    return results


