"""
providers/ai/languages.py — Language + city configuration for multilingual city pop.

The musical STYLE stays the same (1980s-90s Japanese city pop sound).
Only the LYRICS LANGUAGE and the CITY/LOCALE emotion change per language.
Each language targets a major city whose night-time, nostalgic, bittersweet
mood the lyrics should evoke.
"""
from __future__ import annotations


# Each entry defines how to write lyrics for that language/market.
LANGUAGES: dict[str, dict] = {
    "korean": {
        "label": "한국어 (서울)",
        "lyric_language": "Korean",
        "native_name": "한국어",
        "city": "Seoul",
        "city_native": "서울",
        "locations": [
            "명동", "종로", "을지로", "청계천", "뚝섬", "삼각지", "마포",
            "한강", "남산", "성수", "압구정", "신촌", "홍대", "이태원",
        ],
        "title_examples": ["명동에서 종로까지", "을지로 밤길에서", "서울의 밤", "청계천 거리"],
        "char_target": "280-340 Korean characters",
        "line_chars": "8-17 Korean characters",
        "vibe": (
            "neon-lit Seoul nights, rainy alleys, the glow of Myeongdong and "
            "Euljiro, the Han river at night, the loneliness of a fast-moving city"
        ),
    },
    "japanese": {
        "label": "일본어 (도쿄/시부야)",
        "lyric_language": "Japanese",
        "native_name": "日本語",
        "city": "Tokyo (Shibuya, Shinjuku)",
        "city_native": "東京・渋谷",
        "locations": [
            "渋谷", "新宿", "原宿", "六本木", "表参道", "下北沢", "中目黒",
            "お台場", "銀座", "代官山", "恵比寿", "池袋",
        ],
        "title_examples": ["渋谷の夜", "新宿レイン", "夜明けの六本木", "恵比寿の灯り"],
        "char_target": "150-220 Japanese characters",
        "line_chars": "8-16 Japanese characters",
        "vibe": (
            "the neon glow of Shibuya crossing, late-night Shinjuku, rain on "
            "Tokyo streets, city lights reflecting on wet asphalt, the elegant "
            "melancholy of 1980s Tokyo — the true home of city pop"
        ),
    },
    "thai": {
        "label": "태국어 (방콕)",
        "lyric_language": "Thai",
        "native_name": "ภาษาไทย",
        "city": "Bangkok",
        "city_native": "กรุงเทพ",
        "locations": [
            "สุขุมวิท", "สีลม", "ทองหล่อ", "เยาวราช", "อโศก", "พระราม 9",
            "เจริญกรุง", "อารีย์", "เอกมัย", "ราชเทวี",
        ],
        "title_examples": ["ค่ำคืนสุขุมวิท", "ฝนกรุงเทพ", "แสงไฟสีลม", "คืนเหงาทองหล่อ"],
        "char_target": "appropriate length for ~3:30 (concise lines)",
        "line_chars": "short singable phrases",
        "vibe": (
            "Bangkok at night, neon signs over Sukhumvit, the buzz of Silom and "
            "Thonglor, warm tropical city nights, riverside lights on the Chao "
            "Phraya, the bittersweet loneliness amid a lively, humid metropolis"
        ),
    },
    "indonesian": {
        "label": "인도네시아어 (자카르타)",
        "lyric_language": "Indonesian (Bahasa Indonesia)",
        "native_name": "Bahasa Indonesia",
        "city": "Jakarta",
        "city_native": "Jakarta",
        "locations": [
            "Sudirman", "Kemang", "Senopati", "Blok M", "Menteng", "Kota Tua",
            "Thamrin", "SCBD", "Kuningan", "Senayan",
        ],
        "title_examples": ["Malam di Sudirman", "Hujan Jakarta", "Lampu Kemang", "Senja Menteng"],
        "char_target": "appropriate length for ~3:30 (concise lines)",
        "line_chars": "short singable phrases",
        "vibe": (
            "Jakarta city nights, neon and rain over Sudirman, the warmth of "
            "Kemang and Senopati cafes, traffic lights blurring in the rain, the "
            "quiet loneliness inside a huge, restless tropical city"
        ),
    },
    "vietnamese": {
        "label": "베트남어 (호치민)",
        "lyric_language": "Vietnamese",
        "native_name": "Tiếng Việt",
        "city": "Ho Chi Minh City (Saigon)",
        "city_native": "Sài Gòn",
        "locations": [
            "Quận 1", "Bùi Viện", "Đồng Khởi", "Thảo Điền", "Phú Mỹ Hưng",
            "Bến Thành", "Nguyễn Huệ", "Quận 3", "Bình Thạnh",
        ],
        "title_examples": ["Đêm Sài Gòn", "Mưa quận 1", "Ánh đèn Đồng Khởi", "Sài Gòn vắng em"],
        "char_target": "appropriate length for ~3:30 (concise lines)",
        "line_chars": "short singable phrases",
        "vibe": (
            "Saigon nights, neon over Bui Vien and Dong Khoi, motorbikes in the "
            "rain, warm humid city air, lights along the Saigon river, the tender "
            "loneliness of a fast-changing, vibrant city"
        ),
    },
    "english": {
        "label": "영어 (뉴욕)",
        "lyric_language": "English",
        "native_name": "English",
        "city": "New York",
        "city_native": "New York",
        "locations": [
            "Brooklyn", "Manhattan", "Hudson", "Queens", "Chelsea", "SoHo",
            "the Village", "Astoria", "Harlem", "Coney Island",
        ],
        "title_examples": [
            "After the Rain", "Late Reply", "Somewhere Uptown", "Nothing Happened Tonight",
        ],
        "char_target": "1000-1400 characters (Latin script needs ~3x Korean)",
        "line_chars": "6-10 syllables per line (roughly 30-45 characters)",
        "char_range": (1000, 1400),
        "vibe": (
            "late-90s New York evenings, warm light on brownstone steps, a subway "
            "car crossing the bridge at dusk, rain on a yellow cab window, rooftops "
            "in early summer, the tender restlessness of a city that never settles"
        ),
    },
    "spanish": {
        "label": "스페인어 (바르셀로나)",
        "lyric_language": "Spanish",
        "native_name": "Español",
        "city": "Barcelona",
        "city_native": "Barcelona",
        "locations": [
            "Barceloneta", "Gràcia", "Eixample", "Montjuïc", "El Born",
            "Poblenou", "Raval", "Gòtic", "Sant Antoni",
        ],
        "title_examples": [
            "Después de la lluvia", "Tarde de verano", "No dije nada", "Luz de agosto",
        ],
        "char_target": "1000-1400 characters (Latin script needs ~3x Korean)",
        "line_chars": "6-10 syllables per line (roughly 30-45 characters)",
        "char_range": (1000, 1400),
        "vibe": (
            "late-90s Barcelona summers, Mediterranean light on the seafront, warm "
            "evening air along the Barceloneta boardwalk, palm shadows on tiled "
            "pavements, a balcony at dusk, the gentle melancholy of a season ending"
        ),
    },
}

# Lyric character band per language (min, max), used by build_system_prompt.
# Korean/Japanese/Thai and the existing entries keep the original 320-400 band;
# Latin-script languages need far more characters for the same syllable count.
DEFAULT_CHAR_RANGE = (320, 400)

DEFAULT_LANGUAGE = "korean"


def get_language(key: str) -> dict:
    """Get a language config by key, falling back to Korean."""
    return LANGUAGES.get((key or "").lower(), LANGUAGES[DEFAULT_LANGUAGE])


def language_choices() -> list[tuple[str, str]]:
    """Return [(key, label), ...] for UI selectors."""
    return [(k, v["label"]) for k, v in LANGUAGES.items()]


def char_range(key: str) -> tuple[int, int]:
    """(min, max) lyric characters for a language. Defaults to the Korean band."""
    return get_language(key).get("char_range", DEFAULT_CHAR_RANGE)
