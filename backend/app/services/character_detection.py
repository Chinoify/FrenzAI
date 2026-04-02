"""
Character and dialogue detection service for VoxNovel-style multi-voice audiobook generation.
Uses regex-based patterns (no BookNLP dependency) to identify dialogue, attribute speakers,
and auto-assign Kokoro TTS voices.
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Gender dictionary (200+ common English first names)
# ---------------------------------------------------------------------------
FEMALE_NAMES: set[str] = {
    "abigail", "addison", "adeline", "agnes", "alexandra", "alexis", "alice",
    "alicia", "allison", "amanda", "amber", "amelia", "amy", "andrea", "angela",
    "angelina", "ann", "anna", "anne", "annette", "aria", "ariana", "ashley",
    "audrey", "aurora", "autumn", "ava", "barbara", "beatrice", "bella",
    "bernice", "beth", "betty", "beverly", "bianca", "bonnie", "brenda",
    "bridget", "brittany", "brooke", "camila", "carol", "caroline", "catherine",
    "charlotte", "chloe", "christina", "christine", "cindy", "claire", "clara",
    "claudia", "colleen", "constance", "cora", "courtney", "cynthia", "daisy",
    "dana", "danielle", "daphne", "dawn", "deborah", "debra", "delilah",
    "diana", "diane", "donna", "dorothy", "edith", "eileen", "elaine", "elena",
    "eleanor", "elise", "elizabeth", "ella", "ellen", "eloise", "emily", "emma",
    "erica", "erin", "esther", "eva", "evelyn", "faith", "felicia", "fiona",
    "florence", "frances", "gabriella", "gail", "gemma", "georgia", "gertrude",
    "gina", "gloria", "grace", "gwendolyn", "haley", "hannah", "harper",
    "harriet", "hazel", "heather", "heidi", "helen", "holly", "ida", "imogen",
    "ingrid", "irene", "iris", "isabella", "ivy", "jacqueline", "jade", "jane",
    "janet", "janice", "jasmine", "jean", "jenna", "jennifer", "jessica",
    "jill", "joan", "joanna", "jocelyn", "josephine", "joy", "joyce", "judith",
    "judy", "julia", "juliana", "julie", "june", "karen", "kate", "katherine",
    "kathleen", "kathryn", "katie", "kayla", "kelly", "kendra", "kimberly",
    "layla", "leah", "lillian", "lily", "linda", "lisa", "lois", "lorraine",
    "louise", "lucia", "lucy", "lydia", "lynn", "mabel", "mackenzie", "madeline",
    "madison", "mae", "maggie", "maisie", "margaret", "maria", "marian",
    "marie", "marilyn", "marjorie", "marlene", "martha", "mary", "maureen",
    "megan", "melanie", "melissa", "meredith", "mia", "michelle", "mildred",
    "miranda", "molly", "monica", "morgan", "myrtle", "nadia", "nancy",
    "naomi", "natalie", "natasha", "nellie", "nicole", "nora", "norma",
    "olivia", "opal", "paige", "pamela", "patricia", "paula", "pauline",
    "pearl", "penelope", "phoebe", "phyllis", "piper", "priscilla", "rachel",
    "rebecca", "regina", "renee", "riley", "rita", "roberta", "rosa", "rose",
    "rosemary", "ruby", "ruth", "sabrina", "sally", "samantha", "sandra",
    "sarah", "savannah", "scarlett", "shannon", "sharon", "sheila", "shirley",
    "sierra", "silvia", "sofia", "sophia", "stella", "stephanie", "susan",
    "suzanne", "sylvia", "tamara", "tanya", "tara", "teresa", "tiffany",
    "tina", "tracy", "ursula", "valerie", "vanessa", "vera", "veronica",
    "victoria", "violet", "virginia", "vivian", "wendy", "willow", "wanda",
    "yolanda", "yvonne", "zoe",
}

MALE_NAMES: set[str] = {
    "aaron", "adam", "adrian", "aiden", "alan", "albert", "alec", "alexander",
    "alfred", "andrew", "anthony", "antonio", "archer", "arthur", "asher",
    "austin", "barry", "benjamin", "bennett", "bernard", "blake", "brad",
    "bradley", "brandon", "brian", "bruce", "bryan", "caleb", "cameron",
    "carl", "carlos", "carter", "charles", "chase", "chester", "chris",
    "christian", "christopher", "clarence", "clark", "clifford", "clyde",
    "cole", "colin", "connor", "cooper", "craig", "dale", "damian", "daniel",
    "darren", "david", "dean", "dennis", "derek", "desmond", "dominic",
    "donald", "douglas", "drew", "duncan", "dustin", "dylan", "earl", "edgar",
    "edward", "edwin", "eli", "elias", "elijah", "elliot", "emmet", "eric",
    "ernest", "ethan", "eugene", "evan", "felix", "floyd", "francis", "frank",
    "franklin", "fred", "frederick", "gabriel", "garrett", "gary", "gavin",
    "george", "gerald", "gilbert", "glen", "gordon", "graham", "grant", "greg",
    "gregory", "harold", "harry", "harvey", "hector", "henry", "herbert",
    "herman", "howard", "hudson", "hugh", "hugo", "hunter", "ian", "isaac",
    "ivan", "jack", "jackson", "jacob", "jake", "james", "jason", "jasper",
    "jay", "jeff", "jeffrey", "jeremy", "jerome", "jesse", "jim", "joel",
    "john", "jonathan", "jordan", "jose", "joseph", "joshua", "julian",
    "justin", "karl", "keith", "kenneth", "kevin", "kurt", "kyle", "lance",
    "larry", "lawrence", "leo", "leon", "leonard", "levi", "lewis", "liam",
    "lincoln", "logan", "louis", "luca", "lucas", "luke", "malcolm", "marcus",
    "mark", "marshall", "martin", "mason", "mathew", "matthew", "max",
    "maxwell", "michael", "miles", "mitchell", "nathan", "nathaniel",
    "neil", "nelson", "nicholas", "noah", "nolan", "norman", "oliver",
    "oscar", "otto", "owen", "parker", "patrick", "paul", "percy", "peter",
    "philip", "phillip", "pierce", "preston", "quentin", "ralph", "ramon",
    "randall", "raymond", "reed", "reginald", "rex", "richard", "robert",
    "rodney", "roger", "roland", "roman", "ronald", "ross", "roy", "ruben",
    "russell", "ryan", "sam", "samuel", "scott", "sean", "sebastian", "seth",
    "shane", "simon", "spencer", "stanley", "stephen", "steve", "steven",
    "stuart", "ted", "terry", "theodore", "thomas", "timothy", "todd", "tony",
    "travis", "trevor", "troy", "tyler", "victor", "vincent", "wade", "walker",
    "wallace", "walter", "warren", "wayne", "wesley", "william", "wyatt",
    "xavier", "zachary",
}

# ---------------------------------------------------------------------------
# Kokoro voice pools
# ---------------------------------------------------------------------------
FEMALE_VOICES = [
    "af_heart", "af_bella", "af_jessica", "af_nova", "af_sarah",
    "bf_emma", "bf_lily",
]
MALE_VOICES = [
    "am_adam", "am_eric", "am_liam", "am_michael",
    "bm_daniel", "bm_george",
]

DEFAULT_FEMALE_NARRATOR_VOICE = "af_heart"
DEFAULT_MALE_NARRATOR_VOICE = "am_adam"

# ---------------------------------------------------------------------------
# Speech / attribution verbs recognised in regex patterns
# ---------------------------------------------------------------------------
SPEECH_VERBS = (
    r"said|says|say|replied|reply|replies|whispered|whispers|whisper|"
    r"asked|asks|ask|exclaimed|exclaims|exclaim|cried|cries|cry|"
    r"shouted|shouts|shout|muttered|mutters|mutter|murmured|murmurs|murmur|"
    r"answered|answers|answer|called|calls|call|declared|declares|declare|"
    r"demanded|demands|demand|gasped|gasps|gasp|groaned|groans|groan|"
    r"hissed|hisses|hiss|laughed|laughs|laugh|moaned|moans|moan|"
    r"mumbled|mumbles|mumble|pleaded|pleads|plead|promised|promises|promise|"
    r"protested|protests|protest|remarked|remarks|remark|repeated|repeats|repeat|"
    r"responded|responds|respond|roared|roars|roar|sang|sings|sing|"
    r"screamed|screams|scream|sighed|sighs|sigh|snapped|snaps|snap|"
    r"sobbed|sobs|sob|spoke|speaks|speak|stammered|stammers|stammer|"
    r"stated|states|state|stuttered|stutters|stutter|suggested|suggests|suggest|"
    r"told|tells|tell|urged|urges|urge|wailed|wails|wail|"
    r"warned|warns|warn|wept|weeps|weep|yelled|yells|yell|"
    r"added|adds|add|began|begins|begin|continued|continues|continue|"
    r"interrupted|interrupts|interrupt|noted|notes|note|observed|observes|observe|"
    r"offered|offers|offer|ordered|orders|order|questioned|questions|question|"
    r"recalled|recalls|recall|acknowledged|acknowledges|acknowledge"
)

# A "name" is 1-3 capitalised words (e.g. "Elizabeth", "Mr. Darcy", "Old Tom")
_NAME_PAT = r"(?:[A-Z][a-z]+(?:\.\s?)?(?:\s[A-Z][a-z]+){0,2})"

# ---------------------------------------------------------------------------
# Compiled regex patterns for dialogue attribution
# ---------------------------------------------------------------------------

# Pattern 1: "...", said/replied/whispered CharacterName
#   e.g.  "I shall return," said Elizabeth
_PAT_DIALOGUE_THEN_VERB_NAME = re.compile(
    r'["\u201c]([^"\u201d]+)["\u201d]\s*,?\s*'
    rf'(?:{SPEECH_VERBS})\s+'
    rf'({_NAME_PAT})',
    re.IGNORECASE,
)

# Pattern 2: CharacterName said/replied/asked, "..."
#   e.g.  Elizabeth said, "I shall return."
_PAT_NAME_VERB_THEN_DIALOGUE = re.compile(
    rf'({_NAME_PAT})\s+'
    rf'(?:{SPEECH_VERBS})\s*,?\s*'
    r'["\u201c]([^"\u201d]+)["\u201d]',
    re.IGNORECASE,
)

# Pattern 3: "..." CharacterName verbed  (no comma before name)
#   e.g.  "Run!" Elizabeth shouted
_PAT_DIALOGUE_NAME_VERB = re.compile(
    r'["\u201c]([^"\u201d]+)["\u201d]\s+'
    rf'({_NAME_PAT})\s+'
    rf'(?:{SPEECH_VERBS})',
    re.IGNORECASE,
)

# Generic quoted text (for unattributed dialogue)
_PAT_QUOTED = re.compile(r'["\u201c]([^"\u201d]+)["\u201d]')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def infer_gender(name: str) -> str:
    """Return 'female', 'male', or 'unknown' based on first name lookup."""
    first = name.strip().split()[0].lower().rstrip(".")
    if first in FEMALE_NAMES:
        return "female"
    if first in MALE_NAMES:
        return "male"
    return "unknown"


def detect_characters_and_dialogue(text: str) -> dict:
    """
    Analyse *text* and return a dict with:
      - characters: list of detected characters with dialogue counts and gender
      - segments:   ordered list of text segments labelled by speaker

    Everything outside quotation marks is attributed to "Narrator".
    """
    # ------------------------------------------------------------------
    # Step 1 -- find all attributed dialogue spans
    # ------------------------------------------------------------------
    attributed: list[dict] = []  # {start, end, speaker, text}

    for pattern, dialogue_group, name_group in [
        (_PAT_DIALOGUE_THEN_VERB_NAME, 1, 2),
        (_PAT_NAME_VERB_THEN_DIALOGUE, 2, 1),
        (_PAT_DIALOGUE_NAME_VERB, 1, 2),
    ]:
        for m in pattern.finditer(text):
            speaker = m.group(name_group).strip()
            dialogue_text = m.group(dialogue_group).strip()
            attributed.append({
                "start": m.start(),
                "end": m.end(),
                "speaker": speaker,
                "text": dialogue_text,
                "is_dialogue": True,
            })

    # Deduplicate overlapping matches (keep longest)
    attributed.sort(key=lambda s: (s["start"], -(s["end"] - s["start"])))
    deduped: list[dict] = []
    last_end = -1
    for seg in attributed:
        if seg["start"] >= last_end:
            deduped.append(seg)
            last_end = seg["end"]
    attributed = deduped

    # ------------------------------------------------------------------
    # Step 2 -- find unattributed quoted text
    # ------------------------------------------------------------------
    attributed_ranges = {(s["start"], s["end"]) for s in attributed}

    for m in _PAT_QUOTED.finditer(text):
        # Skip if this quote is already covered by an attributed match
        overlaps = any(
            not (m.end() <= s["start"] or m.start() >= s["end"])
            for s in attributed
        )
        if not overlaps:
            attributed.append({
                "start": m.start(),
                "end": m.end(),
                "speaker": "Unknown",
                "text": m.group(1).strip(),
                "is_dialogue": True,
            })

    attributed.sort(key=lambda s: s["start"])

    # ------------------------------------------------------------------
    # Step 3 -- build full segment list (fill narrator between dialogue)
    # ------------------------------------------------------------------
    segments: list[dict] = []
    cursor = 0

    for seg in attributed:
        # Narrator text before this dialogue
        if seg["start"] > cursor:
            narrator_text = text[cursor:seg["start"]].strip()
            if narrator_text:
                segments.append({
                    "start": cursor,
                    "end": seg["start"],
                    "speaker": "Narrator",
                    "text": narrator_text,
                    "is_dialogue": False,
                })
        segments.append(seg)
        cursor = seg["end"]

    # Trailing narrator text
    if cursor < len(text):
        narrator_text = text[cursor:].strip()
        if narrator_text:
            segments.append({
                "start": cursor,
                "end": len(text),
                "speaker": "Narrator",
                "text": narrator_text,
                "is_dialogue": False,
            })

    # ------------------------------------------------------------------
    # Step 4 -- tally characters
    # ------------------------------------------------------------------
    char_counts: dict[str, int] = {}
    for seg in segments:
        if seg["is_dialogue"] and seg["speaker"] != "Unknown":
            char_counts[seg["speaker"]] = char_counts.get(seg["speaker"], 0) + 1

    characters: list[dict] = []
    for name, count in sorted(char_counts.items(), key=lambda kv: -kv[1]):
        characters.append({
            "name": name,
            "gender": infer_gender(name),
            "dialogue_count": count,
        })

    # Always include Narrator
    narrator_present = any(s["speaker"] == "Narrator" for s in segments)
    characters.insert(0, {
        "name": "Narrator",
        "gender": "unknown",
        "dialogue_count": 0,
        "is_narrator": True,
    })

    # Try to resolve "Unknown" speakers via proximity heuristic:
    # attribute to the last known speaker within 500 chars
    _resolve_unknown_speakers(segments, characters)

    return {
        "characters": characters,
        "segments": segments,
    }


def _resolve_unknown_speakers(
    segments: list[dict], characters: list[dict]
) -> None:
    """
    Replace "Unknown" speaker labels with the most-recent known speaker
    if one exists within 500 characters. This handles dialogue that lacks
    explicit attribution tags (common in fast-paced exchanges).
    """
    last_known: Optional[str] = None
    last_known_end: int = 0

    for seg in segments:
        if seg["is_dialogue"] and seg["speaker"] != "Unknown":
            last_known = seg["speaker"]
            last_known_end = seg["end"]
        elif seg["speaker"] == "Unknown" and last_known is not None:
            if seg["start"] - last_known_end < 500:
                seg["speaker"] = last_known


def auto_assign_voices(characters: list[dict]) -> list[dict]:
    """
    Assign Kokoro voice codes to each character dict *in-place* and return
    the list.  Voice assignment rules:
      - Narrator: af_heart (default) or am_adam if narrator gender is male
      - Female characters rotate through FEMALE_VOICES
      - Male characters rotate through MALE_VOICES
      - Unknown-gender characters alternate female/male pools
    """
    female_idx = 0
    male_idx = 0
    unknown_idx = 0  # alternates between pools

    for char in characters:
        if char.get("is_narrator"):
            if char.get("gender") == "male":
                char["voice"] = DEFAULT_MALE_NARRATOR_VOICE
            else:
                char["voice"] = DEFAULT_FEMALE_NARRATOR_VOICE
            continue

        gender = char.get("gender", "unknown")

        if gender == "female":
            char["voice"] = FEMALE_VOICES[female_idx % len(FEMALE_VOICES)]
            female_idx += 1
        elif gender == "male":
            char["voice"] = MALE_VOICES[male_idx % len(MALE_VOICES)]
            male_idx += 1
        else:
            # Alternate between female and male pools for unknowns
            if unknown_idx % 2 == 0:
                char["voice"] = FEMALE_VOICES[female_idx % len(FEMALE_VOICES)]
                female_idx += 1
            else:
                char["voice"] = MALE_VOICES[male_idx % len(MALE_VOICES)]
                male_idx += 1
            unknown_idx += 1

    return characters
