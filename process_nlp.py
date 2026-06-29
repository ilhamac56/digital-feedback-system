"""
PROCESS — Modul Pemrosesan NLP & Analisis Sentimen
===================================================
Berisi logika analisis teks ulasan:
- Preprocessing teks (case folding, cleansing, tokenization, stopword removal)
- Klasifikasi dimensi SERVPERF (keyword matching)
- Klasifikasi sentimen (lexicon-based + rating override)
"""

import re


# ============================================================
# KAMUS KATA KUNCI
# ============================================================

DIMENSION_KEYWORDS = {
    "Tangibles": ["kamar", "bersih", "kotor", "fasilitas", "ac", "air", "handuk", "bau", "luas"],
    "Reliability": ["janji", "sesuai", "nilai", "harga", "pesan", "jadwal"],
    "Responsiveness": ["cepat", "lambat", "sigap", "respon", "lama", "tunggu", "jam"],
    "Assurance": ["aman", "nyaman", "ramah", "sopan", "ketus", "satpam"],
    "Empathy": ["perhatian", "peduli", "bantu", "personal", "senyum"],
}

POSITIVE_KEYWORDS = [
    "bersih", "ramah", "cepat", "nyaman", "bagus", "enak", "sigap", "sopan",
    "puas", "memuaskan", "mantap", "indah", "asri", "sejuk", "tenang",
    "menyenangkan", "terbaik", "recommended", "rekomen", "suka", "senang",
    "lezat", "wangi", "terawat", "rapi", "luas", "membantu", "responsif",
]
NEGATIVE_KEYWORDS = [
    "kotor", "lambat", "bau", "lama", "ketus", "buruk", "mahal", "mati", "keras",
    "kurang", "kecewa", "mengecewakan", "jelek", "rusak", "bocor", "sempit",
    "berisik", "ribut", "bising", "jorok", "lecek", "kusam", "lusuh",
    "gelap", "pengap", "lembab", "apek", "payah", "parah",
    "komplain", "keluhan", "ganggu", "terganggu", "susah", "sulit", "ribet",
    "kumuh", "dekil", "buluk", "ancur", "hancur", "sampah",
    "kecil", "semrawut", "berantakan", "tua", "usang",
    "mengecewakan", "rugi", "menyesal", "protes",
    "tidak", "tdk", "gak", "nggak",
]

STOPWORDS_ID = {"di", "ke", "dari", "yang", "dan", "atau", "tapi"}


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
