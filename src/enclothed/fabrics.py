"""Fabrics by how they are made, not what they are made of: fibers belong in materials.
This list is long, so it lives apart from models.py and is checked in code rather than in the
LLM's output schema. Display names are in locales/."""

FABRIC_GROUPS: dict[str, list[str]] = {
    "plain and fine wovens": [
        "poplin", "broadcloth", "oxford cloth", "pinpoint oxford", "royal oxford", "end-on-end",
        "chambray", "voile", "lawn", "batiste", "cambric", "muslin", "gauze", "double gauze",
        "cheesecloth", "calico", "percale", "seersucker", "plisse", "dobby", "madras",
        "gingham", "typewriter cloth", "flannel", "organdy",
    ],
    "twills and denim": [
        "twill", "chino cloth", "gabardine", "drill", "cavalry twill", "herringbone twill",
        "serge", "whipcord", "westpoint", "kersey", "denim", "selvedge denim", "raw denim",
        "stretch denim", "hickory stripe", "wabash",
    ],
    "heavy and work cloths": [
        "canvas", "duck canvas", "sailcloth", "moleskin", "bull denim", "ticking", "back satin",
        "ripstop", "ventile", "waxed cotton", "oilcloth", "tarpaulin", "burlap", "sack cloth",
    ],
    "linen, hemp and open weaves": [
        "linen cloth", "slub linen", "butcher linen", "hemp cloth", "ramie cloth", "crash",
        "basketweave", "panama", "hopsack", "leno", "open weave", "waffle weave", "honeycomb",
    ],
    "pile and napped": [
        "corduroy", "wide-wale corduroy", "fine-wale corduroy", "velvet", "velveteen",
        "crushed velvet", "chenille", "terry cloth", "sherpa", "faux fur", "peached cotton",
        "brushed cotton",
    ],
    "knits": [
        "jersey", "slub jersey", "stretch jersey", "interlock", "rib knit", "waffle knit",
        "thermal knit", "pique", "pointelle", "french terry", "brushed fleece", "polar fleece",
        "sweater fleece", "grid fleece", "loopwheel", "ponte", "fine-gauge knit",
        "mid-gauge knit", "chunky knit", "cable knit", "fisherman rib", "aran knit",
        "jacquard knit", "fair isle knit", "intarsia knit", "boucle knit", "mohair knit",
        "velour", "scuba knit", "tricot", "power mesh", "mesh", "crochet",
    ],
    "wool suitings and coatings": [
        "tweed", "harris tweed", "donegal tweed", "shetland tweed", "wool flannel", "worsted",
        "tropical wool", "fresco", "sharkskin", "birdseye", "nailhead", "barathea", "saxony",
        "cheviot", "melton", "loden", "boiled wool", "felt", "beaver cloth", "doeskin",
        "mackinaw", "bedford cord", "pendleton wool", "blanket wool", "camel hair cloth",
        "cashmere cloth", "alpaca cloth", "boucle",
    ],
    "silks and fluid fabrics": [
        "satin", "sateen", "charmeuse", "crepe", "crepe de chine", "georgette", "chiffon",
        "organza", "taffeta", "habotai", "dupioni", "shantung", "faille", "grosgrain",
        "ottoman", "moire", "peau de soie", "mikado", "gazar", "challis", "sand-washed silk",
        "silk noil", "pongee", "tussah", "tulle", "net", "lace", "eyelet", "broderie anglaise",
    ],
    "jacquards and patterned weaves": [
        "jacquard", "brocade", "damask", "matelasse", "cloque", "tapestry", "lame",
        "metallic cloth", "sequined fabric", "beaded fabric", "embroidered fabric",
        "appliqued fabric", "patchwork",
    ],
    "Japanese and traditional textiles": [
        "sashiko", "boro", "sakiori", "kasuri", "shijira", "chirimen", "tsumugi",
        "oshima tsumugi", "ro", "sha", "chijimi", "nishijin brocade", "kurume kasuri",
        "aizome cloth", "shibori", "kendo cloth", "ikat", "batik", "khadi", "kente",
        "tartan cloth",
    ],
    "technical and synthetic": [
        "nylon taffeta", "nylon oxford", "nylon twill", "ripstop nylon", "ballistic nylon",
        "cordura", "taslan", "supplex", "gore-tex", "softshell", "hardshell", "coated nylon",
        "coated cotton", "microfiber", "performance stretch", "neoprene", "tyvek", "pvc",
        "quilted fabric", "down-filled nylon",
    ],
    "leather and alternatives": [
        "full-grain leather", "smooth leather", "pebbled leather", "nappa leather", "lambskin",
        "calfskin", "cowhide", "goatskin", "deerskin", "horsehide", "shell cordovan",
        "vegetable-tanned leather", "bridle leather", "suede", "nubuck", "roughout leather",
        "patent leather", "shearling", "pony hair", "faux leather", "faux suede",
    ],
    "footwear and accessory materials": [
        "rubber", "cork", "straw", "raffia", "jute", "woven leather", "webbing", "wood",
        "metal", "acetate",
    ],
}

FABRIC_TYPES = {fabric for fabrics in FABRIC_GROUPS.values() for fabric in fabrics} | {"other"}
