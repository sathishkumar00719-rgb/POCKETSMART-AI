"""
PocketSmart AI - AI Recommendation Engine

Uses Google Gemini for:
- Home Interior Planning
- Party Planning
- Jewelry Recommendations

If Gemini is unavailable, the functions return safe fallback data.
"""

import os
import re
import json
import random
import urllib.parse
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from models import (
    HomeBudgetInput,
    PartyBudgetInput,
    JewelryBudgetInput,
)

# Load .env
load_dotenv()


# ============================================================
# GEMINI SETUP
# ============================================================

GENAI_AVAILABLE = False
client = None

try:
    from google import genai

    API_KEY = (
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )

    if API_KEY and API_KEY.strip():
        client = genai.Client(
            api_key=API_KEY.strip()
        )

        GENAI_AVAILABLE = True

        print("Gemini AI: ENABLED")

    else:
        print("Gemini AI: API KEY NOT FOUND")

except Exception as e:
    GENAI_AVAILABLE = False
    client = None

    print(
        f"Gemini AI initialization failed: {e}"
    )


# Gemini model
GEMINI_MODEL = "gemini-3.5-flash"


# ============================================================
# SHOPPING PLATFORM CONFIGURATION
# ============================================================

CATEGORY_PLATFORMS = {

    "lighting":
        ["amazon", "flipkart", "ikea"],

    "ceiling_fans":
        ["amazon", "flipkart"],

    "furniture":
        ["amazon", "flipkart", "ikea"],

    "dining_tables":
        ["amazon", "flipkart", "ikea"],

    "decor":
        ["amazon", "flipkart", "ikea", "meesho"],

    "venue":
        ["makemytrip", "oyorooms", "nobroker", "google"],

    "catering":
        ["swiggy", "zomato"],

    "food":
        ["swiggy", "zomato"],

    "drinks":
        ["swiggy", "zomato", "bigbasket"],

    "decoration":
        ["amazon", "flipkart", "meesho"],

    "entertainment":
        ["amazon", "flipkart", "bookmyshow"],

    "photography":
        ["google", "amazon"],

    "music":
        ["amazon", "bookmyshow"],

    "games":
        ["amazon", "flipkart"],

    "gifts":
        ["amazon", "flipkart", "myntra"],

    "accessories":
        ["amazon", "flipkart", "myntra"],

    "return_gifts":
        ["amazon", "flipkart", "meesho"],

    "contingency":
        ["amazon", "flipkart", "google"],

    "transportation":
        ["makemytrip", "google"],
}


DEFAULT_PLATFORMS = [
    "amazon",
    "flipkart",
    "google"
]


JEWELRY_PLATFORMS = [
    "amazon",
    "flipkart",
    "bluestone",
    "tanishq",
    "caratlane",
    "melorra",
    "meesho",
]


# ============================================================
# SHOPPING URL BUILDER
# ============================================================

def _search_url(
    platform: str,
    query: str
) -> Optional[str]:

    q = urllib.parse.quote_plus(query)

    urls = {

        "amazon":
            f"https://www.amazon.in/s?k={q}",

        "flipkart":
            f"https://www.flipkart.com/search?q={q}",

        "ikea":
            f"https://www.ikea.com/in/en/search/?q={q}",

        "myntra":
            f"https://www.myntra.com/{q}",

        "ajio":
            f"https://www.ajio.com/search/?text={q}",

        "meesho":
            f"https://www.meesho.com/search?q={q}",

        "swiggy":
            f"https://www.swiggy.com/search?query={q}",

        "zomato":
            f"https://www.zomato.com/search?q={q}",

        "bigbasket":
            f"https://www.bigbasket.com/ps/?q={q}",

        "bookmyshow":
            f"https://in.bookmyshow.com/search?q={q}",

        "google":
            f"https://www.google.com/search?q={q}",

        "booking":
            f"https://www.booking.com/search.html?ss={q}",

        "makemytrip":
            f"https://www.makemytrip.com/hotels/hotel-listing/?searchText={q}",

        "oyorooms":
            f"https://www.oyorooms.com/search/?location={q}",

        "nobroker":
            f"https://www.nobroker.in/property/search?searchTerm={q}",

        "bluestone":
            f"https://www.bluestone.com/search.html?query={q}",

        "tanishq":
            f"https://www.tanishq.co.in/search?q={q}",

        "caratlane":
            f"https://www.caratlane.com/search?q={q}",

        "melorra":
            f"https://www.melorra.com/search?q={q}",
    }

    return urls.get(platform)


def add_shopping_links(
    item: Dict[str, Any],
    platforms: list
) -> Dict[str, Any]:

    search_terms = (
        item.get("search_terms")
        or item.get("name")
        or item.get("item_type")
        or ""
    )

    links = {}

    for platform in platforms:

        url = _search_url(
            platform,
            search_terms
        )

        if url:
            links[platform] = url

    item["shopping_links"] = links

    return item


# ============================================================
# GEMINI JSON PARSER
# ============================================================

def extract_json_from_response(
    text: str
) -> Dict[str, Any]:

    if not text:
        raise ValueError(
            "Gemini returned an empty response"
        )

    cleaned = text.strip()

    # Remove markdown fences
    cleaned = re.sub(
        r"^```json",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"^```",
        "",
        cleaned
    )

    cleaned = re.sub(
        r"```$",
        "",
        cleaned
    )

    cleaned = cleaned.strip()

    # Find JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(
            "Gemini response does not contain valid JSON"
        )

    cleaned = cleaned[start:end + 1]

    return json.loads(cleaned)


# ============================================================
# GEMINI CALL
# ============================================================

def _call_gemini(
    prompt: str
) -> Optional[Dict[str, Any]]:

    if not GENAI_AVAILABLE or client is None:

        print(
            "[ai_service] Gemini is not available."
        )

        return None

    try:

        response = client.models.generate_content(

            model=GEMINI_MODEL,

            contents=prompt

        )

        result = extract_json_from_response(
            response.text
        )

        print(
            "[ai_service] Gemini response received successfully."
        )

        return result

    except Exception as e:

        print(
            f"[ai_service] Gemini call failed: {e}"
        )

        return None


# ============================================================
# HOME MOCK FALLBACK
# ============================================================

def _mock_home_recommendations(
    budget_input: HomeBudgetInput
) -> Dict[str, Any]:

    total = budget_input.total_budget

    allocations = {

        "lighting": (
            0.15,
            budget_input.num_lights,
            "LED Bulb (Warm White)",
            "Energy-efficient LED bulb for general lighting."
        ),

        "ceiling_fans": (
            0.20,
            budget_input.num_fans,
            "Ceiling Fan (Standard)",
            "Basic functional ceiling fan with 3-speed control."
        ),

        "furniture": (
            0.30,
            budget_input.num_furniture,
            "Modular Chair/Sofa Unit",
            "Space-saving comfortable furniture piece."
        ),

        "dining_tables": (
            0.20,
            budget_input.num_dining_tables,
            "Dining Table Set",
            "4-seater wooden dining table."
        ),

        "decor": (
            0.15,
            1,
            "Wall Art & Decor Bundle",
            "Curated decor pieces."
        ),
    }

    budget_breakdown = []

    remaining = total

    for category, (
        pct,
        qty,
        name,
        desc
    ) in allocations.items():

        qty = (
            max(qty, 1)
            if category == "decor"
            else qty
        )

        if qty <= 0:
            continue

        cat_budget = round(
            total * pct,
            2
        )

        unit_price = round(
            cat_budget / qty,
            2
        )

        item = {

            "name": name,

            "description": desc,

            "estimated_price":
                unit_price,

            "quantity":
                qty,

            "search_terms":
                f"{name} for home",
        }

        add_shopping_links(
            item,
            CATEGORY_PLATFORMS.get(
                category,
                DEFAULT_PLATFORMS
            )
        )

        budget_breakdown.append({

            "category":
                category,

            "allocation":
                cat_budget,

            "items":
                [item],
        })

        remaining -= cat_budget

    return {

        "total_budget":
            total,

        "budget_breakdown":
            budget_breakdown,

        "remaining_budget":
            round(
                max(remaining, 0),
                2
            ),

        "additional_suggestions": [

            "Consider purchasing pre-owned furniture for further cost savings.",

            "Watch for seasonal sales and festival discounts.",

            "Prioritize essential items first.",
        ],

        "_source":
            "fallback",
    }


# ============================================================
# HOME PLANNER
# ============================================================

def get_home_recommendations(
    budget_input: HomeBudgetInput
) -> Dict[str, Any]:

    rooms = []

    if budget_input.has_living_room:
        rooms.append("Living Room")

    if budget_input.has_kitchen:
        rooms.append("Kitchen")

    if budget_input.has_bedroom:
        rooms.append("Bedroom")

    prompt = f"""
You are PocketSmart AI, an intelligent home interior
budget recommendation assistant for users in India.

Create practical product recommendations within the
user's total budget.

Total budget:
Rs.{budget_input.total_budget:.2f}

Requirements:

Lights:
{budget_input.num_lights}

Ceiling fans:
{budget_input.num_fans}

Furniture:
{budget_input.num_furniture}

Dining tables:
{budget_input.num_dining_tables}

Rooms:
{', '.join(rooms) if rooms else 'Not specified'}

Additional requirements:
{budget_input.additional_requirements or 'None'}

Important:

1. Use Indian prices in INR.
2. Keep the total cost within the budget.
3. Give realistic product recommendations.
4. Use useful Indian shopping search terms.
5. Do not use markdown.
6. Return ONLY valid JSON.

Return exactly:

{{
  "total_budget": 0.0,
  "budget_breakdown": [
    {{
      "category": "lighting",
      "allocation": 0.0,
      "items": [
        {{
          "name": "",
          "description": "",
          "estimated_price": 0.0,
          "quantity": 0,
          "search_terms": ""
        }}
      ]
    }}
  ],
  "remaining_budget": 0.0,
  "additional_suggestions": []
}}
"""

    result = _call_gemini(prompt)

    if result is None:

        return _mock_home_recommendations(
            budget_input
        )

    result["_source"] = "gemini"

    for category in result.get(
        "budget_breakdown",
        []
    ):

        category_name = (
            category.get(
                "category",
                ""
            ).lower()
        )

        platforms = CATEGORY_PLATFORMS.get(
            category_name,
            DEFAULT_PLATFORMS
        )

        for item in category.get(
            "items",
            []
        ):

            add_shopping_links(
                item,
                platforms
            )

    result.setdefault(
        "remaining_budget",
        0.0
    )

    result.setdefault(
        "additional_suggestions",
        []
    )

    return result


# ============================================================
# PARTY MOCK FALLBACK
# ============================================================

def _mock_party_recommendations(
    budget_input: PartyBudgetInput
) -> Dict[str, Any]:

    total = budget_input.total_budget

    breakdown_plan = []

    remaining = total

    # Venue
    if (
        budget_input.venue_type
        and budget_input.venue_type.lower()
        not in ("home", "none", "")
    ):

        venue_alloc = round(
            total * 0.35,
            2
        )

        item = {

            "name":
                f"{budget_input.venue_type} venue booking",

            "description":
                f"Venue suitable for {budget_input.num_guests} guests.",

            "estimated_price":
                venue_alloc,

            "quantity":
                1,

            "search_terms":
                f"{budget_input.venue_type} venue for {budget_input.party_type}",
        }

        add_shopping_links(
            item,
            CATEGORY_PLATFORMS["venue"]
        )

        breakdown_plan.append({

            "category":
                "venue",

            "allocation":
                venue_alloc,

            "items":
                [item],
        })

        remaining -= venue_alloc

    else:

        breakdown_plan.append({

            "category":
                "venue",

            "allocation":
                0.0,

            "items": [{

                "name":
                    "Home",

                "description":
                    "Using home as the venue.",

                "estimated_price":
                    0.0,

                "quantity":
                    1,

                "search_terms":
                    "",

                "shopping_links":
                    {},
            }],
        })

    # Catering
    if budget_input.needs_catering:

        cat_alloc = round(
            total * 0.40,
            2
        )

        per_guest = round(
            cat_alloc /
            max(
                budget_input.num_guests,
                1
            ),
            2
        )

        item = {

            "name":
                f"Catering for {budget_input.num_guests} guests",

            "description":
                f"Food and beverages, approx Rs.{per_guest}/guest.",

            "estimated_price":
                cat_alloc,

            "quantity":
                1,

            "search_terms":
                f"party catering {budget_input.party_type}",
        }

        add_shopping_links(
            item,
            CATEGORY_PLATFORMS["catering"]
        )

        breakdown_plan.append({

            "category":
                "catering",

            "allocation":
                cat_alloc,

            "items":
                [item],
        })

        remaining -= cat_alloc

    # Decoration
    if budget_input.needs_decoration:

        dec_alloc = round(
            total * 0.15,
            2
        )

        item = {

            "name":
                f"{budget_input.party_type} theme decoration",

            "description":
                "Balloons, banners and themed decor.",

            "estimated_price":
                dec_alloc,

            "quantity":
                1,

            "search_terms":
                f"{budget_input.party_type} party decoration",
        }

        add_shopping_links(
            item,
            CATEGORY_PLATFORMS["decoration"]
        )

        breakdown_plan.append({

            "category":
                "decoration",

            "allocation":
                dec_alloc,

            "items":
                [item],
        })

        remaining -= dec_alloc

    # Entertainment
    if budget_input.needs_entertainment:

        ent_alloc = round(
            total * 0.10,
            2
        )

        item = {

            "name":
                "Entertainment package",

            "description":
                "Music, games or activities.",

            "estimated_price":
                ent_alloc,

            "quantity":
                1,

            "search_terms":
                f"{budget_input.party_type} entertainment",
        }

        add_shopping_links(
            item,
            CATEGORY_PLATFORMS["entertainment"]
        )

        breakdown_plan.append({

            "category":
                "entertainment",

            "allocation":
                ent_alloc,

            "items":
                [item],
        })

        remaining -= ent_alloc

    contingency = round(
        max(remaining, 0),
        2
    )

    breakdown_plan.append({

        "category":
            "contingency",

        "allocation":
            contingency,

        "items": [{

            "name":
                "Unexpected expenses buffer",

            "description":
                "Buffer for unforeseen costs.",

            "estimated_price":
                contingency,

            "quantity":
                1,

            "search_terms":
                "",

            "shopping_links":
                {},
        }],
    })

    return {

        "total_budget":
            total,

        "budget_breakdown":
            breakdown_plan,

        "venue_suggestions":
            [],

        "remaining_budget":
            0.0,

        "additional_suggestions": [

            "Consider a potluck-style meal to reduce catering costs.",

            "Look for discounts on decoration and entertainment.",

            "Book venues and vendors early.",
        ],

        "_source":
            "fallback",
    }


# ============================================================
# PARTY PLANNER
# ============================================================

def get_party_recommendations(
    budget_input: PartyBudgetInput
) -> Dict[str, Any]:

    prompt = f"""
You are PocketSmart AI, an intelligent party planning
assistant for users in India.

Create a complete party budget and recommendation plan.

Total budget:
Rs.{budget_input.total_budget:.2f}

Party type:
{budget_input.party_type}

Guests:
{budget_input.num_guests}

Venue:
{budget_input.venue_type or 'Not specified'}

Catering:
{"Yes" if budget_input.needs_catering else "No"}

Decoration:
{"Yes" if budget_input.needs_decoration else "No"}

Entertainment:
{"Yes" if budget_input.needs_entertainment else "No"}

Additional requirements:
{budget_input.additional_requirements or 'None'}

Rules:

1. Use INR.
2. Stay within the given budget.
3. Give realistic India-relevant suggestions.
4. Give useful search terms.
5. Return ONLY valid JSON.
6. No markdown.

Return exactly:

{{
  "total_budget": 0.0,
  "budget_breakdown": [
    {{
      "category": "",
      "allocation": 0.0,
      "items": [
        {{
          "name": "",
          "description": "",
          "estimated_price": 0.0,
          "quantity": 0,
          "search_terms": ""
        }}
      ]
    }}
  ],
  "venue_suggestions": [
    {{
      "name": "",
      "type": "",
      "capacity": 0,
      "estimated_cost": 0.0,
      "search_terms": ""
    }}
  ],
  "remaining_budget": 0.0,
  "additional_suggestions": []
}}
"""

    result = _call_gemini(prompt)

    if result is None:

        return _mock_party_recommendations(
            budget_input
        )

    result["_source"] = "gemini"

    for category in result.get(
        "budget_breakdown",
        []
    ):

        category_name = (
            category.get(
                "category",
                ""
            ).lower()
        )

        platforms = CATEGORY_PLATFORMS.get(
            category_name,
            DEFAULT_PLATFORMS
        )

        for item in category.get(
            "items",
            []
        ):

            add_shopping_links(
                item,
                platforms
            )

    for venue in result.get(
        "venue_suggestions",
        []
    ):

        add_shopping_links(
            venue,
            CATEGORY_PLATFORMS["venue"]
        )

    result.setdefault(
        "remaining_budget",
        0.0
    )

    result.setdefault(
        "additional_suggestions",
        []
    )

    result.setdefault(
        "venue_suggestions",
        []
    )

    return result


# ============================================================
# JEWELRY MOCK FALLBACK
# ============================================================

_JEWELRY_TYPES = [

    (
        "bracelet",
        "A minimal bracelet with metal accents that complements most outfits.",
        0.10
    ),

    (
        "ring",
        "A simple elegant ring suitable for everyday wear.",
        0.12
    ),

    (
        "earrings",
        "Lightweight earrings suitable for casual and semi-formal looks.",
        0.18
    ),

    (
        "necklace",
        "A statement necklace as the centerpiece of the look.",
        0.35
    ),

    (
        "watch",
        "A classic watch with a leather or metal band.",
        0.25
    ),

]


def _mock_jewelry_recommendations(
    budget_input: JewelryBudgetInput,
    has_image: bool
) -> Dict[str, Any]:

    total = budget_input.total_budget

    items = []

    remaining = total

    chosen = random.sample(
        _JEWELRY_TYPES,
        k=min(3, len(_JEWELRY_TYPES))
    )

    for (
        item_type,
        description,
        percentage
    ) in chosen:

        price = round(
            total * percentage,
            2
        )

        item = {

            "item_type":
                item_type,

            "description":
                description,

            "style":
                budget_input.preferences
                or "versatile",

            "estimated_price":
                price,

            "search_terms":
                f"{item_type} for {budget_input.occasion}",
        }

        add_shopping_links(
            item,
            JEWELRY_PLATFORMS
        )

        items.append(item)

        remaining -= price


    result = {

        "total_budget":
            total,

        "jewelry_recommendations":
            items,

        "remaining_budget":
            round(
                max(remaining, 0),
                2
            ),

        "styling_tips": [

            "Keep the jewelry minimal so it complements rather than overwhelms the outfit.",

            "Match metal tones such as gold or silver across all pieces.",

            f"For a {budget_input.occasion.lower()}, consider one statement piece and keep the rest subtle.",
        ],

        "_source":
            "fallback",
    }


    if has_image:

        result["outfit_analysis"] = {

            "colors":
                ["as detected from your uploaded image"],

            "style":
                budget_input.preferences
                or "casual",

            "formality":
                "informal",
        }


    return result


# ============================================================
# JEWELRY PLANNER
# ============================================================

def get_jewelry_recommendations(
    budget_input: JewelryBudgetInput,
    image_path: Optional[str] = None
) -> Dict[str, Any]:

    base_prompt = f"""
You are PocketSmart AI, an intelligent jewelry
recommendation assistant for users in India.

Create practical jewelry recommendations
within the user's budget.

Total budget:
Rs.{budget_input.total_budget:.2f}

Occasion:
{budget_input.occasion}

Preferences:
{budget_input.preferences or 'Not specified'}

Rules:

1. Use Indian prices in INR.
2. Stay within the given budget.
3. Recommend practical jewelry.
4. Consider the occasion and user's preferences.
5. If an outfit image is provided, consider its colors,
   style and formality.
6. Use useful Indian shopping search terms.
7. Return ONLY valid JSON.
8. Do not use markdown.
"""

    result = None


    # ========================================================
    # GEMINI JEWELRY CALL
    # ========================================================

    if GENAI_AVAILABLE and client is not None:

        try:

            if image_path:

                from PIL import Image

                img = Image.open(
                    image_path
                )

                prompt = base_prompt + """

An outfit image has been uploaded.

Analyze the outfit and recommend jewelry
that matches the outfit.

Consider:

- Outfit colors
- Outfit style
- Formality
- Occasion
- Budget

Return exactly:

{
  "outfit_analysis": {
    "colors": [],
    "style": "",
    "formality": ""
  },
  "total_budget": 0.0,
  "jewelry_recommendations": [
    {
      "item_type": "",
      "description": "",
      "style": "",
      "estimated_price": 0.0,
      "search_terms": ""
    }
  ],
  "remaining_budget": 0.0,
  "styling_tips": []
}
"""

                response = client.models.generate_content(

                    model=GEMINI_MODEL,

                    contents=[
                        prompt,
                        img
                    ]

                )

            else:

                prompt = base_prompt + """

Return exactly:

{
  "total_budget": 0.0,
  "jewelry_recommendations": [
    {
      "item_type": "",
      "description": "",
      "style": "",
      "estimated_price": 0.0,
      "search_terms": ""
    }
  ],
  "remaining_budget": 0.0,
  "styling_tips": []
}
"""

                response = client.models.generate_content(

                    model=GEMINI_MODEL,

                    contents=prompt

                )


            result = extract_json_from_response(
                response.text
            )

            print(
                "[ai_service] Gemini jewelry response received successfully."
            )


        except Exception as e:

            print(
                f"[ai_service] Gemini jewelry call failed: {e}"
            )

            result = None


    # ========================================================
    # FALLBACK
    # ========================================================

    if result is None:

        return _mock_jewelry_recommendations(
            budget_input,
            has_image=bool(image_path)
        )


    # ========================================================
    # ADD SHOPPING LINKS
    # ========================================================

    result["_source"] = "gemini"


    for item in result.get(
        "jewelry_recommendations",
        []
    ):

        add_shopping_links(
            item,
            JEWELRY_PLATFORMS
        )


    result.setdefault(
        "remaining_budget",
        0.0
    )

    result.setdefault(
        "styling_tips",
        []
    )


    return result