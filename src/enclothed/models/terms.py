"""The fixed vocabulary, stored in English, and its English labels: languages, colors, categories and
subcategories, the attribute choices, tiers and shapes, layers and color traits. Translations are in locales/."""
import colorsys
from typing import Literal, get_args

Language = Literal["en-US", "zh-TW", "ja-JP"]
DEFAULT_LANGUAGE: Language = "en-US"
LANGUAGE_NAMES: dict[Language, str] = {"en-US": "English", "zh-TW": "繁體中文", "ja-JP": "日本語"}

Color = Literal[
    # neutrals
    "black", "charcoal", "gray", "light gray", "white", "cream",
    "beige", "khaki", "tan", "camel", "brown", "dark brown", "navy",
    # colors
    "light blue", "slate blue", "blue", "indigo", "teal", "green", "olive",
    "forest green", "burgundy", "red", "pink", "orange", "rust",
    "mustard", "yellow", "purple", "eggplant", "lavender", "cognac",
    # metallics
    "silver", "gold", "brass", "copper", "gunmetal"
]
COLOR_HEX: dict[Color, str] = {
    "black": "#151515", "charcoal": "#3b3d42", "gray": "#8a8c90", "light gray": "#c9cacd",
    "white": "#f7f7f5", "cream": "#efe6cf", "beige": "#d9c8a6", "khaki": "#b9a777",
    "tan": "#c19a6b", "camel": "#b5844f", "brown": "#7a4e2d", "dark brown": "#4a2f1d",
    "navy": "#1f2a4a", "light blue": "#a9c4e4", "slate blue": "#5f7391", "blue": "#2f5fb3",
    "indigo": "#1a159a", "teal": "#1f7a7a", "green": "#3c8a4a", "olive": "#6b6a2f",
    "forest green": "#24452e", "burgundy": "#6b1f2e", "red": "#b8322a", "pink": "#e7a1b4",
    "orange": "#e07a2e", "rust": "#a4482a", "mustard": "#c9a227", "yellow": "#eccb3a",
    "purple": "#5e3b8a", "eggplant": "#4b2c45", "lavender": "#b9a7da", "cognac": "#9a5527",
    "silver": "#c0c3c8", "gold": "#c6a14a", "brass": "#b5933f", "copper": "#b06a3b",
    "gunmetal": "#53565c",
}
FORMALITY_LABELS = {1: "casual", 2: "smart casual", 3: "business", 4: "formalwear"}
WARMTH_LABELS = {
    1: "summer-weight, 25°C+", 2: "light, 18–25°C", 3: "mid-layer, 10–18°C",
    4: "warm, 0–10°C", 5: "heavy winter, below 0°C",
}

Fit = Literal["slim", "regular", "relaxed", "oversized"]
Sheen = Literal["matte", "low", "high"]
FIT_LABELS: dict[Fit, str] = {
    "slim": "slim (close to the body)",
    "regular": "regular (standard cut)",
    "relaxed": "relaxed (roomy)",
    "oversized": "oversized (deliberately large)",
}
SHEEN_LABELS: dict[Sheen, str] = {
    "matte": "matte (no shine)",
    "low": "low (soft luster)",
    "high": "high (shiny, like satin or patent leather)",
}
Shape = Literal["straight", "tapered", "wide", "flared", "boxy", "a-line", "balloon"]
Hem = Literal["waist", "hip", "thigh", "knee", "calf", "ankle", "floor"]
FabricWeight = Literal["light", "mid", "heavy"]
Sleeve = Literal["sleeveless", "short", "three-quarter", "long"]
Statement = Literal["basic", "feature", "statement"]
SHAPE_LABELS: dict[Shape, str] = {
    "straight": "straight",
    "tapered": "tapered (narrows toward the hem)",
    "wide": "wide (full throughout)",
    "flared": "flared (widens toward the hem)",
    "boxy": "boxy (wide and short)",
    "a-line": "A-line (wider at the hem)",
    "balloon": "balloon (full through the middle, gathered at the end)",
}
HEM_LABELS: dict[Hem, str] = {
    "waist": "at the waist",
    "hip": "at the hip",
    "thigh": "mid-thigh",
    "knee": "at the knee",
    "calf": "mid-calf",
    "ankle": "at the ankle",
    "floor": "to the floor",
}
FABRIC_WEIGHT_LABELS: dict[FabricWeight, str] = {
    "light": "light",
    "mid": "mid",
    "heavy": "heavy",
}
SLEEVE_LABELS: dict[Sleeve, str] = {
    "sleeveless": "sleeveless",
    "short": "short",
    "three-quarter": "three-quarter",
    "long": "long",
}
STATEMENT_LABELS: dict[Statement, str] = {
    "basic": "basic (quiet, goes with anything)",
    "feature": "feature (some interest of its own)",
    "statement": "statement (the piece people notice)",
}
RiskTier = Literal["safe", "stretch", "bold"]
RISK_TIER_LABELS: dict[RiskTier, str] = {"safe": "Safe", "stretch": "Stretch", "bold": "Bold"}
# The letter shapes an outfit can be asked to form (prompts.SILHOUETTE_SECTION says what each means). None: any shape.
Silhouette = Literal["I", "H", "A", "Y", "O", "X"]
Recommendation = Literal["worth_it", "maybe", "pass"]
RECOMMENDATION_LABELS: dict[Recommendation, str] = {"worth_it": "Worth it", "maybe": "Maybe", "pass": "Pass"}

Category = Literal["top", "bottom", "one-piece", "outerwear", "shoes", "accessory"]
CATEGORY_ORDER = {category: position for position, category in enumerate(get_args(Category))}

SUBCATEGORIES: dict[Category, set[str]] = {
    "top": {
        "t-shirt", "long-sleeve t-shirt", "tank top", "polo", "rugby shirt",
        "henley", "oxford shirt", "dress shirt", "casual shirt",
        "camp-collar shirt", "band-collar shirt", "western shirt",
        "flannel shirt", "blouse", "tunic", "smock", "pullover", "no-collar shirt",
        "sweatshirt", "hoodie", "crewneck sweater", "v-neck sweater", "sweater",
        "turtleneck", "mock neck", "cardigan", "sweater vest",
        # womenswear
        "camisole", "bodysuit", "wrap top", "crop top", "peplum top",
        "other",
    },
    "bottom": {
        "jeans", "chinos", "dress trousers", "pleated trousers",
        "wide trousers", "easy pants", "balloon pants", "sarouel pants",
        "hakama pants", "work pants", "painter pants", "fatigue pants",
        "cargo pants", "track pants", "joggers", "sweatpants",
        "culottes", "shorts", "skirt", "leggings", "five-pocket pants",
        # womenswear
        "pleated skirt", "slip skirt", "wrap skirt",
        "other",
    },
    "one-piece": {
        "overalls", "jumpsuit", "coveralls", "dress",
        # womenswear
        "slip dress", "shirt dress", "wrap dress", "sweater dress", "pinafore dress", "romper",
        "other",
    },
    "outerwear": {
        # tailored / coats
        "blazer", "sport coat", "overcoat", "trench coat", "pea coat",
        "duffle coat", "suit jacket",
        # jackets
        "trucker jacket", "shirt jacket", "chore coat", "work jacket",
        "field jacket", "safari jacket", "coach jacket", "harrington jacket",
        "bomber jacket", "varsity jacket", "track jacket", "leather jacket",
        "quilted jacket", "liner jacket", "blouson", "no-collar jacket",
        "baseball jacket",
        # Japanese / wrap
        "noragi", "haori", "kimono jacket",
        # technical / weather
        "parka", "puffer jacket", "anorak", "windbreaker", "shell jacket",
        "rain jacket", "fleece",
        # sleeveless / draped
        "vest", "poncho", "cape",
        # womenswear
        "wrap coat", "cocoon coat", "bolero",
        "other",
    },
    "shoes": {
        "low-top sneakers", "high-top sneakers", "running shoes",
        "loafers", "oxfords", "derbies", "monk straps", "boat shoes",
        "moccasins", "chelsea boots", "chukka boots", "desert boots",
        "lace-up boots", "engineer boots", "work boots", "hiking boots",
        "sandals", "slides", "clogs", "mules", "espadrilles",
        "tabi", "geta",
        # womenswear
        "pumps", "slingbacks", "kitten heels", "heeled sandals", "ballet flats", "mary janes", "ankle boots", "knee-high boots",
        "other",
    },
    "accessory": {
        "belt", "suspenders", "cap", "bucket hat", "beanie", "flat cap",
        "fedora", "scarf", "stole", "bandana", "tie", "bow tie",
        "pocket square", "socks", "gloves", "tote bag", "backpack",
        "messenger bag", "crossbody bag", "waist bag", "wallet",
        "watch", "glasses", "sunglasses", "jewelry",
        # womenswear
        "handbag", "clutch", "shoulder bag", "tights", "hair accessory",
        "other",
    },
}

ALL_SUBCATEGORIES = set().union(*SUBCATEGORIES.values())
LIST_FILTER_CHOICES = sorted(set(CATEGORY_ORDER) | ALL_SUBCATEGORIES)

Layer = Literal["base", "mid", "outer"]
MID_LAYERS = {
    "sweatshirt", "hoodie", "crewneck sweater", "v-neck sweater", "sweater", "cardigan",
    "sweater vest", "pullover", "vest", "fleece", "liner jacket",
}

def layer_for(category: Category, subcategory: str) -> Layer | None:
    """Where a piece sits when worn in layers. None for what isn't worn in layers on the torso."""
    if category not in ("top", "outerwear"):
        return None
    if subcategory in MID_LAYERS:
        return "mid"
    return "base" if category == "top" else "outer"

NEUTRAL_COLORS = {
    "black", "charcoal", "gray", "light gray", "white", "cream",
    "beige", "khaki", "tan", "camel", "brown", "dark brown", "navy",
}
METALLIC_COLORS = {"silver", "gold", "brass", "copper", "gunmetal"}

def color_traits(color: Color) -> dict[str, str]:
    """How a stylist would describe a color, worked out from its hex value."""
    red, green, blue = (int(COLOR_HEX[color][i:i + 2], 16) / 255 for i in (1, 3, 5))
    hue, lightness, _ = colorsys.rgb_to_hls(red, green, blue)
    chroma = max(red, green, blue) - min(red, green, blue)   # how far from gray, even in very dark colors
    degrees = hue * 360

    if chroma < 0.05:
        temperature = "neutral"
    elif degrees < 90 or degrees >= 330:
        temperature = "warm"
    else:
        temperature = "cool"

    return {
        "family": "metallic" if color in METALLIC_COLORS else "neutral" if color in NEUTRAL_COLORS else "color",
        "temperature": temperature,
        "lightness": "dark" if lightness < 0.33 else "light" if lightness > 0.66 else "medium",
        "saturation": "muted" if chroma < 0.2 else "vivid" if chroma > 0.45 else "medium",
    }


Closeness = Literal["exact", "close", "loose", "none"]
CLOSENESS_LABELS: dict[Closeness, str] = {"exact": "Exact", "close": "Close", "loose": "Loose", "none": "Not owned"}

OutfitSource = Literal["ai", "own"]   # suggested by the AI (weigh included) or put together by the user
