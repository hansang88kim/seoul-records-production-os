"""
services/thumbnail/country_presets.py — Country visual presets for citypop thumbnails.

Each country affects city background, lighting, signage mood, and color tone
while keeping the Japanese nostalgic citypop / Seoul Records brand identity.
Not tourism posters — premium citypop playlist visuals.
"""
from __future__ import annotations


COUNTRY_PRESETS: dict[str, dict] = {
    "korea": {
        "label": "한국 (Korea)",
        "city": "Seoul",
        "scene": "Seoul rainy night, apartment windows, taxi reflections, neon alleys, Han River glow",
        "lighting": "soft neon reflections on wet asphalt, warm window glow",
        "signage": "subtle Korean neon signs, convenience store glow",
        "color_tone": "cool blue night with warm magenta and amber accents",
        "palette": ["#1a2238", "#ff4d6d", "#ffb347", "#2d3a5f"],
        "accent": "#ff4d6d",
    },
    "japan": {
        "label": "일본 (Japan)",
        "city": "Tokyo",
        "scene": "Tokyo/Yokohama night streets, Showa-Heisei nostalgia, vending machine glow, train station lights",
        "lighting": "vending machine glow, station fluorescent light, wet pavement reflections",
        "signage": "vintage Japanese neon, retro storefront signs",
        "color_tone": "deep indigo night with cyan and warm red neon",
        "palette": ["#15203a", "#00d4ff", "#ff3860", "#1f2d4d"],
        "accent": "#00d4ff",
    },
    "vietnam": {
        "label": "베트남 (Vietnam)",
        "city": "Ho Chi Minh City",
        "scene": "Ho Chi Minh City or Hanoi humid neon night, scooters, warm rain, narrow streets, balcony lights",
        "lighting": "warm humid haze, scooter headlights, balcony string lights",
        "signage": "warm Vietnamese neon, street vendor glow",
        "color_tone": "warm amber night with teal and coral accents",
        "palette": ["#1e2a2a", "#ff9e64", "#2ec4b6", "#3a2e2e"],
        "accent": "#ff9e64",
    },
    "thailand": {
        "label": "태국 (Thailand)",
        "city": "Bangkok",
        "scene": "Bangkok humid night, elevated rail, neon markets, taxi lights, tropical city glow",
        "lighting": "tropical neon haze, elevated rail glow, market light spill",
        "signage": "vibrant Thai neon, night market signs",
        "color_tone": "warm tropical night with pink and gold neon",
        "palette": ["#241a2e", "#ff5da2", "#ffd166", "#3a2a40"],
        "accent": "#ff5da2",
    },
    "taiwan": {
        "label": "대만 (Taiwan)",
        "city": "Taipei",
        "scene": "Taipei night market glow, wet asphalt, warm signs, scooter reflections",
        "lighting": "night market warm glow, wet asphalt reflections",
        "signage": "Taiwanese night market neon, warm storefront signs",
        "color_tone": "warm amber and red night with soft cyan",
        "palette": ["#2a1f1a", "#ffae57", "#e63946", "#1f3a3a"],
        "accent": "#ffae57",
    },
    "hongkong": {
        "label": "홍콩 (Hong Kong)",
        "city": "Hong Kong",
        "scene": "dense vertical city, harbor glow, tram mood, rain-soaked streets, cinematic neon",
        "lighting": "dense vertical neon, harbor reflections, rain-soaked cinematic light",
        "signage": "iconic dense Hong Kong neon signs stacked vertically",
        "color_tone": "saturated cyan and magenta cinematic neon",
        "palette": ["#0f1a2e", "#00e5ff", "#ff2e88", "#1a2d4a"],
        "accent": "#ff2e88",
    },
    "china": {
        "label": "중국 (China)",
        "city": "Shanghai",
        "scene": "Shanghai/Shenzhen skyline, neon boulevard, modern night city, reflective roads",
        "lighting": "modern skyline glow, neon boulevard, reflective wet roads",
        "signage": "sleek modern Chinese neon, LED facade glow",
        "color_tone": "electric blue and red modern night",
        "palette": ["#101a2e", "#2e7dff", "#ff3b3b", "#1a2540"],
        "accent": "#2e7dff",
    },
    "indonesia": {
        "label": "인도네시아 (Indonesia)",
        "city": "Jakarta",
        "scene": "Jakarta night traffic, tropical rain, apartment towers, warm city glow",
        "lighting": "warm tropical city glow, rain haze, apartment tower lights",
        "signage": "warm Indonesian street neon, roadside glow",
        "color_tone": "warm orange night with soft teal",
        "palette": ["#241e1a", "#ff8c42", "#2ec4b6", "#332a24"],
        "accent": "#ff8c42",
    },
    "malaysia": {
        "label": "말레이시아 (Malaysia)",
        "city": "Kuala Lumpur",
        "scene": "Kuala Lumpur skyline, monorail, humid neon evening, soft rain",
        "lighting": "skyline glow, monorail light trails, humid soft rain",
        "signage": "modern KL neon, soft tower glow",
        "color_tone": "deep teal night with warm gold",
        "palette": ["#15242a", "#ffd166", "#06b6d4", "#1f3540"],
        "accent": "#ffd166",
    },
    "singapore": {
        "label": "싱가포르 (Singapore)",
        "city": "Singapore",
        "scene": "sleek clean night city, futuristic neon, Marina district mood, polished urban atmosphere",
        "lighting": "polished futuristic glow, Marina light show, clean reflections",
        "signage": "minimal sleek neon, futuristic LED accents",
        "color_tone": "cool futuristic teal and violet",
        "palette": ["#101a2e", "#00e5cc", "#a855f7", "#1a2540"],
        "accent": "#00e5cc",
    },
    "philippines": {
        "label": "필리핀 (Philippines)",
        "city": "Manila",
        "scene": "Manila night streets, jeepney-inspired color accents, city rain, warm neon",
        "lighting": "warm street neon, jeepney color glow, city rain haze",
        "signage": "vibrant Filipino street signs, jeepney-inspired color",
        "color_tone": "warm multicolor night with vibrant accents",
        "palette": ["#241a2e", "#ff6b35", "#ffd23f", "#2a2440"],
        "accent": "#ff6b35",
    },
    "india": {
        "label": "인도 (India)",
        "city": "Mumbai",
        "scene": "Mumbai monsoon night, dense urban lights, taxi reflections, cinematic rainy road",
        "lighting": "monsoon haze, dense urban light, cinematic taxi reflections",
        "signage": "warm dense Indian street signage, glowing storefronts",
        "color_tone": "warm amber monsoon night with deep teal",
        "palette": ["#1e2424", "#ffb347", "#1ca7a0", "#2a3030"],
        "accent": "#ffb347",
    },
}

# Title-safe composition variations for batch diversity
SCENE_VARIATIONS = [
    "rainy crosswalk at night",
    "taxi window view of passing neon",
    "rooftop skyline overlooking the city",
    "convenience store glow on an empty street",
    "last train platform under fluorescent light",
    "apartment window with city lights beyond",
    "riverside road with reflections",
    "night market street with warm signs",
    "neon underpass with wet pavement",
    "hotel room window view of the skyline",
]

# Title-safe area options (where to leave negative space)
TITLE_SAFE_AREAS = [
    "left third clean for title overlay",
    "right third clean for title overlay",
    "top third clean for title overlay",
    "lower third clean for title overlay",
    "center-left clean band for title overlay",
]


def list_countries() -> list[tuple[str, str]]:
    """Return [(key, label)] for the country selector."""
    return [(k, v["label"]) for k, v in COUNTRY_PRESETS.items()]


def get_country_preset(country_key: str) -> dict:
    """Get a country preset, defaulting to Korea."""
    return COUNTRY_PRESETS.get(country_key, COUNTRY_PRESETS["korea"])


# ── Thumbnail title defaults (TOKYO / 夜の音楽 style) ──────────────────────────
# For each country: a punchy display name for the MAIN title (city, uppercased
# by the renderer) + the local-language "night music" line that sits just under
# it. Both are only DEFAULTS — the user can overwrite either in the UI.
TITLE_DEFAULTS = {
    "korea":       {"city": "SEOUL",        "night_local": "밤의 음악"},
    "japan":       {"city": "TOKYO",        "night_local": "夜の音楽"},
    "vietnam":     {"city": "SAIGON",       "night_local": "Nhạc Đêm"},
    "thailand":    {"city": "BANGKOK",      "night_local": "ดนตรียามค่ำคืน"},
    "taiwan":      {"city": "TAIPEI",       "night_local": "夜的音樂"},
    "hongkong":    {"city": "HONG KONG",    "night_local": "夜的音樂"},
    "china":       {"city": "SHANGHAI",     "night_local": "夜的音乐"},
    "indonesia":   {"city": "JAKARTA",      "night_local": "Musik Malam"},
    "malaysia":    {"city": "KUALA LUMPUR", "night_local": "Muzik Malam"},
    "singapore":   {"city": "SINGAPORE",    "night_local": "夜的音乐"},
    "philippines": {"city": "MANILA",       "night_local": "Musika ng Gabi"},
    "india":       {"city": "MUMBAI",       "night_local": "रात का संगीत"},
}


def get_title_defaults(country_key: str) -> dict:
    """Default main-title city + local 'night music' line for a country."""
    return TITLE_DEFAULTS.get(country_key, TITLE_DEFAULTS["korea"])


# ── Culture/nationality adjective for the IMAGE prompt ────────────────────────
# The thumbnail background should depict the SELECTED country, not always Japan.
# (The music keeps its Japanese city-pop core elsewhere; this only drives images.)
CULTURE = {
    "korea": "Korean", "japan": "Japanese", "vietnam": "Vietnamese",
    "thailand": "Thai", "taiwan": "Taiwanese", "hongkong": "Hong Kong",
    "china": "Chinese", "indonesia": "Indonesian", "malaysia": "Malaysian",
    "singapore": "Singaporean", "philippines": "Filipino", "india": "Indian",
}


def get_culture(country_key: str) -> str:
    """Nationality/culture adjective for the selected country's image prompt."""
    return CULTURE.get(country_key, "Korean")
