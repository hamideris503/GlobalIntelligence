"""آفلاین gazetteer (بدون شبکه) برای استخراج مکان از متن.

منابع/مجوز:
- کشورها: centroids مستخرج از Natural Earth (public domain) + نام‌های فارسی دستی.
- شهرها: مختصات مستخرج از GeoNames (CC BY 4.0) — فقط زیرمجموعهٔ کوچک.
- هیچ درخواست شبکه‌ای در زمان اجرا نیست.

نام‌های مبهم (مثلاً «گرجستان»/«Georgia») فقط وقتی حل می‌شوند که متن زمینهٔ کافی
داشته باشد؛ وگرنه نامشخص می‌مانند.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Place:
    name: str          # نام کانونی (فارسی یا انگلیسی)
    country: str        # ISO-2
    latitude: float
    longitude: float
    precision: str     # "city" | "country"
    # نام‌های جایگزین (فارسی/انگلیسی) که همگی به همین مکان اشاره دارند
    aliases: tuple[str, ...] = ()


# ---------- کشورها ----------
# alias -> iso2 (نام اصلی در COUNTRIES)
COUNTRY_ALIASES: dict[str, str] = {
    # انگلیسی
    "iran": "IR", "islamic republic of iran": "IR", "persia": "IR",
    "israel": "IL", "palestine": "PS", "gaza": "PS", "west bank": "PS",
    "lebanon": "LB", "syria": "SY", "iraq": "IQ", "saudi arabia": "SA",
    "yemen": "YE", "turkey": "TR", "russia": "RU", "ukraine": "UA",
    "china": "CN", "united states": "US", "usa": "US", "america": "US",
    "united kingdom": "GB", "uk": "GB", "britain": "GB", "england": "GB",
    "france": "FR", "germany": "DE", "india": "IN", "pakistan": "PK",
    "afghanistan": "AF", "egypt": "EG", "jordan": "JO", "qatar": "QA",
    "uae": "AE", "united arab emirates": "AE", "kuwait": "KW", "bahrain": "BH",
    "oman": "OM", "azerbaijan": "AZ", "armenia": "AM", "georgia": "GE",
    "kazakhstan": "KZ", "uzbekistan": "UZ", "tajikistan": "TJ",
    "turkmenistan": "TM", "kyrgyzstan": "KG",
    "japan": "JP", "south korea": "KR", "korea": "KR", "north korea": "KP",
    "taiwan": "TW", "vietnam": "VN", "thailand": "TH", "indonesia": "ID",
    "malaysia": "MY", "philippines": "PH", "singapore": "SG",
    "australia": "AU", "new zealand": "NZ", "canada": "CA", "mexico": "MX",
    "brazil": "BR", "argentina": "AR", "chile": "CL", "colombia": "CO",
    "venezuela": "VE", "cuba": "CU", "south africa": "ZA", "nigeria": "NG",
    "kenya": "KE", "ethiopia": "ET", "sudan": "SD", "libya": "LY",
    "tunisia": "TN", "algeria": "DZ", "morocco": "MA", "senegal": "SN",
    "greece": "GR", "italy": "IT", "spain": "ES", "portugal": "PT",
    "netherlands": "NL", "belgium": "BE", "switzerland": "CH", "austria": "AT",
    "poland": "PL", "czech republic": "CZ", "czechia": "CZ", "hungary": "HU",
    "romania": "RO", "bulgaria": "BG", "serbia": "RS", "croatia": "HR",
    "bosnia": "BA", "albania": "AL", "macedonia": "MK", "north macedonia": "MK",
    "montenegro": "ME", "kosovo": "XK", "belarus": "BY",
    "moldova": "MD", "lithuania": "LT", "latvia": "LV", "estonia": "EE",
    "finland": "FI", "sweden": "SE", "norway": "NO", "denmark": "DK",
    "iceland": "IS", "ireland": "IE",
    # فارسی
    "ایران": "IR", "جمهوری اسلامی ایران": "IR",
    "اسرائیل": "IL", "فلسطین": "PS", "غزه": "PS",
    "لبنان": "LB", "سوریه": "SY", "عراق": "IQ", "عربستان": "SA",
    "عربستان سعودی": "SA", "یمن": "YE", "ترکیه": "TR", "روسیه": "RU",
    "اوکراین": "UA", "چین": "CN", "آمریکا": "US", "ایالات متحده": "US",
    "انگلیس": "GB", "بریتانیا": "GB", "فرانسه": "FR", "آلمان": "DE",
    "هند": "IN", "پاکستان": "PK", "افغانستان": "AF", "مصر": "EG",
    "اردن": "JO", "قطر": "QA", "امارات": "AE", "کویت": "KW", "بحرین": "BH",
    "عمان": "OM", "آذربایجان": "AZ", "ارمنستان": "AM", "گرجستان": "GE",
    "قزاقستان": "KZ", "ازبکستان": "UZ", "تاجیکستان": "TJ", "ترکمنستان": "TM",
    "قرقیزستان": "KG", "ژاپن": "JP", "کرهٔ جنوبی": "KR", "کره جنوبی": "KR",
    "تایوان": "TW", "ویتنام": "VN", "تایلند": "TH", "اندونزی": "ID",
    "مالزی": "MY", "فیلیپین": "PH", "سنگاپور": "SG", "استرالیا": "AU",
    "کانادا": "CA", "مکزیک": "MX", "برزیل": "BR", "آرژانتین": "AR",
    "شیلی": "CL", "کلمبیا": "CO", "ونزوئلا": "VE", "کوبا": "CU",
    "آفریقای جنوبی": "ZA", "نیجریه": "NG", "کنیا": "KE", "اتیوپی": "ET",
    "سودان": "SD", "لیبی": "LY", "تونس": "TN", "الجزایر": "DZ",
    "مراکش": "MA", "یونان": "GR", "ایتالیا": "IT", "اسپانیا": "ES",
    "پرتغال": "PT", "هلند": "NL", "بلژیک": "BE", "سوئیس": "CH",
    "اتریش": "AT", "لهستان": "PL", "مجارستان": "HU", "رومانی": "RO",
    "بلغارستان": "BG", "صربستان": "RS", "کرواسی": "HR", "آلبانی": "AL",
    "بلاروس": "BY", "مولداوی": "MD", "لیتوانی": "LT",
    "لتونی": "LV", "استونی": "EE", "فنلاند": "FI", "سوئد": "SE",
    "نروژ": "NO", "دانمارک": "DK", "ایرلند": "IE",
}

# کشورهای مبهم: فقط اگر زمینهٔ کافی باشد حل می‌شوند.
AMBIGUOUS_COUNTRIES: dict[str, tuple[str, ...]] = {
    "georgia": ("tbilisi", "caucasus", "south ossetia", "abkhazia", "georgian"),
    "گرجستان": ("تفلیس", "قفقاز", "گرجی"),
}

COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "IR": (32.4279, 53.6880), "IL": (31.0461, 34.8516), "PS": (31.9522, 35.2332),
    "LB": (33.8547, 35.8623), "SY": (34.8021, 38.9968), "IQ": (33.2232, 43.6793),
    "SA": (23.8859, 45.0792), "YE": (15.5527, 48.5164), "TR": (38.9637, 35.2433),
    "RU": (61.5240, 105.3188), "UA": (48.3794, 31.1656), "CN": (35.8617, 104.1954),
    "US": (37.0902, -95.7129), "GB": (55.3781, -3.4360), "FR": (46.2276, 2.2137),
    "DE": (51.1657, 10.4515), "IN": (20.5937, 78.9629), "PK": (30.3753, 69.3451),
    "AF": (33.9391, 67.7100), "EG": (26.8206, 30.8025), "JO": (30.5852, 36.2384),
    "QA": (25.3548, 51.1839), "AE": (23.4241, 53.8478), "KW": (29.3117, 47.4818),
    "BH": (26.0667, 50.5577), "OM": (21.4735, 55.9754), "AZ": (40.1431, 47.5769),
    "AM": (40.0691, 45.0382), "GE": (42.3154, 43.3569), "KZ": (48.0196, 66.9237),
    "UZ": (41.3775, 64.5853), "TJ": (38.8610, 71.2761), "TM": (38.9697, 59.5563),
    "KG": (41.2044, 74.7661), "JP": (36.2048, 138.2529), "KR": (35.9078, 127.7669),
    "KP": (40.3399, 127.5101), "TW": (23.6978, 120.9605), "VN": (14.0583, 108.2772),
    "TH": (15.8700, 100.9925), "ID": (-0.7893, 113.9213), "MY": (4.2105, 101.9758),
    "PH": (12.8797, 121.7740), "SG": (1.3521, 103.8198), "AU": (-25.2744, 133.7751),
    "NZ": (-40.9006, 174.8860), "CA": (56.1304, -106.3468), "MX": (23.6345, -102.5528),
    "BR": (-14.2350, -51.9253), "AR": (-38.4161, -63.6167), "CL": (-35.6751, -71.5430),
    "CO": (4.5709, -74.2973), "VE": (6.4238, -66.5897), "CU": (21.5218, -77.7812),
    "ZA": (-30.5595, 22.9375), "NG": (9.0820, 8.6753), "KE": (-0.0236, 37.9062),
    "ET": (9.1450, 40.4897), "SD": (12.8628, 30.2176), "LY": (26.3351, 17.2283),
    "TN": (33.8869, 9.5375), "DZ": (28.0339, 1.6596), "MA": (31.7917, -7.0926),
    "GR": (39.0742, 21.8243), "IT": (41.8719, 12.5674), "ES": (40.4637, -3.7492),
    "PT": (39.3999, -8.2245), "NL": (52.1326, 5.2913), "BE": (50.5039, 4.4699),
    "CH": (46.8182, 8.2275), "AT": (47.5162, 14.5501), "PL": (51.9194, 19.1451),
    "CZ": (49.8175, 15.4730), "HU": (47.1625, 19.5033), "RO": (45.9432, 24.9668),
    "BG": (42.7339, 25.4858), "RS": (44.0165, 21.0059), "HR": (45.1000, 15.2000),
    "AL": (41.1533, 20.1683), "MK": (41.6086, 21.7453), "ME": (42.7087, 19.3744),
    "BY": (53.7098, 27.9534), "MD": (47.4116, 28.3699), "LT": (55.1694, 23.8813),
    "LV": (56.8796, 24.6032), "EE": (58.5953, 25.0136), "FI": (61.9241, 25.7482),
    "SE": (60.1282, 18.6435), "NO": (60.4720, 8.4689), "DK": (56.2639, 9.5018),
    "IS": (64.9631, -19.0208), "IE": (53.1424, -7.6921), "SN": (14.4974, -14.4524),
}

# ---------- شهرهای بزرگ ----------
CITIES: tuple[Place, ...] = (
    # خاورمیانه
    Place("Tehran", "IR", 35.6892, 51.3890, "city", ("تهران", "Tehran", "Teheran")),
    Place("Mashhad", "IR", 36.2605, 59.6168, "city", ("مشهد",)),
    Place("Isfahan", "IR", 32.6546, 51.6680, "city", ("اصفهان", "Esfahan")),
    Place("Shiraz", "IR", 29.5926, 52.5836, "city", ("شیراز",)),
    Place("Tabriz", "IR", 38.0800, 46.2919, "city", ("تبریز",)),
    Place("Qom", "IR", 34.6399, 50.8759, "city", ("قم",)),
    Place("Ahvaz", "IR", 31.3183, 48.6706, "city", ("اهواز",)),
    Place("Jerusalem", "IL", 31.7683, 35.2137, "city", ("قدس", "اورشلیم", "Jerusalem", "Al-Quds")),
    Place("Tel Aviv", "IL", 32.0853, 34.7818, "city", ("تل‌آویو", "Tel Aviv", "Tel-Aviv")),
    Place("Gaza City", "PS", 31.5017, 34.4668, "city", ("غزه", "Gaza")),
    Place("Ramallah", "PS", 31.8996, 35.2042, "city", ("رام‌الله", "Ramallah")),
    Place("Beirut", "LB", 33.8938, 35.5018, "city", ("بیروت", "Beirut")),
    Place("Damascus", "SY", 33.5138, 36.2765, "city", ("دمشق", "Damascus")),
    Place("Aleppo", "SY", 36.2021, 37.1343, "city", ("حلب", "Aleppo")),
    Place("Baghdad", "IQ", 33.3152, 44.3661, "city", ("بغداد", "Baghdad")),
    Place("Mosul", "IQ", 36.3400, 43.1300, "city", ("موصل", "Mosul")),
    Place("Erbil", "IQ", 36.1911, 44.0092, "city", ("اربیل", "Erbil", "Irbil")),
    Place("Riyadh", "SA", 24.7136, 46.6753, "city", ("ریاض", "Riyadh")),
    Place("Jeddah", "SA", 21.4858, 39.1925, "city", ("جده", "Jeddah")),
    Place("Sanaa", "YE", 15.3694, 44.1910, "city", ("صنعاء", "Sanaa", "Sana'a")),
    Place("Ankara", "TR", 39.9334, 32.8597, "city", ("آنکارا", "Ankara")),
    Place("Istanbul", "TR", 41.0082, 28.9784, "city", ("استانبول", "Istanbul")),
    # قفقاز/آسیای مرکزی
    Place("Tbilisi", "GE", 41.6938, 44.8015, "city", ("تفلیس", "Tbilisi")),
    Place("Yerevan", "AM", 40.1792, 44.4991, "city", ("ایروان", "Yerevan")),
    Place("Baku", "AZ", 40.4093, 49.8671, "city", ("باکو", "Baku")),
    Place("Kabul", "AF", 34.5553, 69.2075, "city", ("کابل", "Kabul")),
    Place("Islamabad", "PK", 33.6844, 73.0479, "city", ("اسلام‌آباد", "Islamabad")),
    Place("Karachi", "PK", 24.8607, 67.0011, "city", ("کراچی", "Karachi")),
    Place("New Delhi", "IN", 28.6139, 77.2090, "city", ("دهلی", "New Delhi", "Delhi")),
    Place("Mumbai", "IN", 19.0760, 72.8777, "city", ("بمبئی", "Mumbai", "Bombay")),
    # شرق آسیا
    Place("Beijing", "CN", 39.9042, 116.4074, "city", ("پکن", "Beijing", "Peking")),
    Place("Shanghai", "CN", 31.2304, 121.4737, "city", ("شانگهای", "Shanghai")),
    Place("Hong Kong", "CN", 22.3193, 114.1694, "city", ("هنگ‌کنگ", "Hong Kong")),
    Place("Taipei", "TW", 25.0330, 121.5654, "city", ("تایپه", "Taipei")),
    Place("Tokyo", "JP", 35.6762, 139.6503, "city", ("توکیو", "Tokyo")),
    Place("Seoul", "KR", 37.5665, 126.9780, "city", ("سئول", "Seoul")),
    Place("Pyongyang", "KP", 39.0392, 125.7625, "city", ("پیونگ‌یانگ", "Pyongyang")),
    # اروپا
    Place("London", "GB", 51.5074, -0.1278, "city", ("لندن", "London")),
    Place("Paris", "FR", 48.8566, 2.3522, "city", ("پاریس", "Paris")),
    Place("Berlin", "DE", 52.5200, 13.4050, "city", ("برلین", "Berlin")),
    Place("Rome", "IT", 41.9028, 12.4964, "city", ("رم", "Rome")),
    Place("Madrid", "ES", 40.4168, -3.7038, "city", ("مادرید", "Madrid")),
    Place("Moscow", "RU", 55.7558, 37.6173, "city", ("مسکو", "Moscow")),
    Place("Kyiv", "UA", 50.4501, 30.5234, "city", ("کیف", "Kyiv", "Kiev")),
    Place("Washington", "US", 38.9072, -77.0369, "city", ("واشینگتن", "Washington", "Washington DC", "Washington, D.C.")),
    Place("New York", "US", 40.7128, -74.0060, "city", ("نیویورک", "New York", "New York City", "NYC")),
    Place("Los Angeles", "US", 34.0522, -118.2437, "city", ("لس‌آنجلس", "Los Angeles", "LA")),
    Place("Chicago", "US", 41.8781, -87.6298, "city", ("شیکاگو", "Chicago")),
    Place("Philadelphia", "US", 39.9526, -75.1652, "city", ("فیلادلفیا", "Philadelphia")),
    Place("Atlanta", "US", 33.7490, -84.3880, "city", ("آتلانتا", "Atlanta")),
    Place("Houston", "US", 29.7604, -95.3698, "city", ("هیوستون", "Houston")),
    Place("San Francisco", "US", 37.7749, -122.4194, "city", ("سان‌فرانسیسکو", "San Francisco")),
    # آفریقا
    Place("Cairo", "EG", 30.0444, 31.2357, "city", ("قاهره", "Cairo")),
    Place("Nairobi", "KE", -1.2921, 36.8219, "city", ("نایروبی", "Nairobi")),
    Place("Johannesburg", "ZA", -26.2041, 28.0473, "city", ("ژوهانسبورگ", "Johannesburg")),
    Place("Cape Town", "ZA", -33.9249, 18.4241, "city", ("کیپ‌تاون", "Cape Town")),
    Place("Lagos", "NG", 6.5244, 3.3792, "city", ("لاگوس", "Lagos")),
    Place("Addis Ababa", "ET", 8.9806, 38.7578, "city", ("آدیس آبابا", "Addis Ababa")),
    Place("Khartoum", "SD", 15.5007, 32.5599, "city", ("خارطوم", "Khartoum")),
    Place("Tripoli", "LY", 32.8872, 13.1913, "city", ("طرابلس", "Tripoli")),
    Place("Tunis", "TN", 36.8065, 10.1815, "city", ("تونس", "Tunis")),
    Place("Algiers", "DZ", 36.7538, 3.0588, "city", ("الجزیره", "Algiers")),
    Place("Casablanca", "MA", 33.5731, -7.5898, "city", ("کازابلانکا", "Casablanca")),
    Place("Rabat", "MA", 34.0209, -6.8416, "city", ("رباط", "Rabat")),
    # آمریکای لاتین
    Place("Mexico City", "MX", 19.4326, -99.1332, "city", ("مکزیکوسیتی", "Mexico City")),
    Place("Sao Paulo", "BR", -23.5505, -46.6333, "city", ("سائوپائولو", "Sao Paulo", "São Paulo")),
    Place("Rio de Janeiro", "BR", -22.9068, -43.1729, "city", ("ریو", "Rio de Janeiro")),
    Place("Buenos Aires", "AR", -34.6037, -58.3816, "city", ("بوئنوس آیرس", "Buenos Aires")),
    Place("Santiago", "CL", -33.4489, -70.6693, "city", ("سانتیاگو", "Santiago")),
    Place("Bogota", "CO", 4.7110, -74.0721, "city", ("بوگوتا", "Bogota", "Bogotá")),
    Place("Caracas", "VE", 10.4806, -66.9036, "city", ("کاراکاس", "Caracas")),
    Place("Havana", "CU", 23.1136, -82.3666, "city", ("هاوانا", "Havana")),
    # جنوب/جنوب‌شرق آسیا
    Place("Jakarta", "ID", -6.2088, 106.8456, "city", ("جاکارتا", "Jakarta")),
    Place("Bangkok", "TH", 13.7563, 100.5018, "city", ("بانکوک", "Bangkok")),
    Place("Manila", "PH", 14.5995, 120.9842, "city", ("مانیل", "Manila")),
    Place("Kuala Lumpur", "MY", 3.1390, 101.6869, "city", ("کوالالامپور", "Kuala Lumpur")),
    Place("Singapore", "SG", 1.3521, 103.8198, "city", ("سنگاپور", "Singapore")),
    Place("Hanoi", "VN", 21.0285, 105.8542, "city", ("هانوی", "Hanoi")),
    Place("Ho Chi Minh City", "VN", 10.8231, 106.6297, "city", ("هوشی‌مین", "Ho Chi Minh City", "Saigon")),
)


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    import re
    # replace punctuation with spaces so "south africa's" matches "south africa"
    t = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


def _match_names(text_norm: str, name: str) -> bool:
    # word-ish boundary via surrounding spaces
    needle = " " + name.lower().strip() + " "
    haystack = " " + text_norm + " "
    return needle in haystack


def geocode_text(text: str | None) -> dict:
    """استخراج مکان از متن صریح. خروجی شامل دلیل است.

    هیچ حدسی زده نمی‌شود: اگر متن چند کشور/شهر متفاوت داشته باشد یا نام مبهم
    بدون زمینه باشد، نتیجه unresolved می‌ماند.
    """
    result = {
        "location": None,
        "latitude": None,
        "longitude": None,
        "country": None,
        "location_precision": None,
        "location_source": None,
        "location_confidence": None,
        "location_status": "unresolved",
        "location_reason": "no_location_mentioned",
    }
    if not text or not text.strip():
        result["location_reason"] = "empty_text"
        return result

    norm = _normalize(text)
    padded = " " + norm + " "

    # شهرها (نام‌های بلندتر اول)
    city_hits: list[Place] = []
    for place in sorted(CITIES, key=lambda p: -max(len(a) for a in (p.name,) + p.aliases)):
        names = (place.name,) + place.aliases
        for nm in names:
            n = _normalize(nm)
            if n and (" " + n + " ") in padded:
                city_hits.append(place)
                break
    # dedup by name
    seen_cities = set()
    unique_cities = []
    for c in city_hits:
        if c.name in seen_cities:
            continue
        seen_cities.add(c.name)
        unique_cities.append(c)

    # کشورها
    country_hits: set[str] = set()
    for alias, iso in COUNTRY_ALIASES.items():
        an = _normalize(alias)
        if not an:
            continue
        if an in AMBIGUOUS_COUNTRIES and not any(ctx in norm for ctx in AMBIGUOUS_COUNTRIES[an]):
            continue
        if (" " + an + " ") in padded:
            country_hits.add(iso)

    # تصمیم
    if unique_cities:
        countries_of_cities = {c.country for c in unique_cities}
        if len(unique_cities) == 1:
            c = unique_cities[0]
            result.update({
                "location": c.name,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "country": c.country,
                "location_precision": "city",
                "location_source": "gazetteer_city",
                "location_confidence": 0.8,
                "location_status": "resolved_city",
                "location_reason": f"city mentioned: {c.name}",
            })
            return result
        if len(countries_of_cities) == 1:
            # چند شهر همان کشور → سطح کشور
            iso = next(iter(countries_of_cities))
            lat, lon = COUNTRY_CENTROIDS[iso]
            result.update({
                "location": None,
                "latitude": lat,
                "longitude": lon,
                "country": iso,
                "location_precision": "country",
                "location_source": "gazetteer_country",
                "location_confidence": 0.5,
                "location_status": "resolved_country",
                "location_reason": "multiple cities in same country",
            })
            return result
        result["location_reason"] = "conflicting cities/countries"
        return result

    if country_hits:
        if len(country_hits) == 1:
            iso = next(iter(country_hits))
            lat, lon = COUNTRY_CENTROIDS[iso]
            # canonical country name from alias reverse
            name = None
            for alias, i in COUNTRY_ALIASES.items():
                if i == iso and _normalize(alias) in norm.split() or _normalize(alias) == norm:
                    name = alias.title()
                    break
            result.update({
                "location": name,
                "latitude": lat,
                "longitude": lon,
                "country": iso,
                "location_precision": "country",
                "location_source": "gazetteer_country",
                "location_confidence": 0.5,
                "location_status": "resolved_country",
                "location_reason": f"country mentioned: {iso}",
            })
            return result
        result["location_reason"] = "conflicting countries"
        return result

    return result
