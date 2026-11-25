"""Every model and fixed term, in five files by what they're for, from the bottom layer up:

    terms     the fixed vocabulary and its labels
    garment   a garment, its photos, and the fields mend can fill
    ai        what the AI calls are asked for and send back
    records   what the database holds (db.py)
    api       what the API takes in and sends back

Each file imports only from the ones above it. Everything is re-exported here, so `from enclothed.models import X`
works for any of them; import from a file directly only to make a dependency plain."""
from enclothed.models.terms import *     # noqa: F401,F403
from enclothed.models.garment import *   # noqa: F401,F403
from enclothed.models.ai import *        # noqa: F401,F403
from enclothed.models.records import *   # noqa: F401,F403
from enclothed.models.api import *       # noqa: F401,F403
