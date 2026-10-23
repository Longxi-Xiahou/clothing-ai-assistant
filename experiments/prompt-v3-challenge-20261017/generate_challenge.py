import json
from collections import Counter
from pathlib import Path

from app.schemas.chat_intent import ChatIntent

OUT = Path("experiments/prompt-v3-challenge-20261017/challenge_cases.jsonl")

def case(cid, group, message, expected, previous=None, history=None):
    complete = {
        "intent": "general" if group == "general" else "product_search",
        "action": (
            "general" if group == "general"
            else "modify_filters" if group in {"modify_filters", "clear_filters"}
            else "new_search"
        ),
        "category": None,
        "color": None,
        "min_price": None,
        "max_price": None,
        "clear_filters": [],
    }
    complete.update(expected)
    return {
        "id": cid,
        "group": group,
        "message": message,
        "previous_filters": previous or {},
        "history": history or [],
        "expected": complete,
    }

cases = []

# 15 general
general = [
    "What should I wear to a summer graduation?",
    "Explain the difference between smart casual and business casual.",
    "Thanks, that explanation helped.",
    "Can you suggest colors that pair well with olive green?",
    "What is a good way to organize a small wardrobe?",
    "Good morning!",
    "How do I care for wool clothing?",
    "What does relaxed fit mean?",
    "Is layering useful in cold weather?",
    "Help me choose an outfit for a job interview.",
    "What are some timeless clothing basics?",
    "Can you explain the difference between linen and cotton?",
    "I appreciate the suggestions.",
    "What should I pack for a weekend trip?",
    "How can I make an outfit look more formal?",
]
for i, message in enumerate(general, 1):
    cases.append(case(f"CH{i:03}", "general", message, {}))

# 20 new searches
searches = [
    ("Find burgundy sweaters priced below $65.", {"category": "Sweaters", "color": "burgundy", "max_price": 65}),
    ("I need gray joggers for no more than $45.", {"category": "Joggers", "color": "gray", "max_price": 45}),
    ("Show me beige trench coats between $80 and $180.", {"category": "Trench Coats", "color": "beige", "min_price": 80, "max_price": 180}),
    ("Look for navy polo shirts.", {"category": "Polo Shirts", "color": "navy"}),
    ("Find cardigans that cost at least $35.", {"category": "Cardigans", "min_price": 35}),
    ("I'd like a pair of white chinos under $70.", {"category": "Chinos", "color": "white", "max_price": 70}),
    ("Search for purple running shorts.", {"category": "Running Shorts", "color": "purple"}),
    ("Show me a brown leather jacket around $150.", {"category": "Leather Jackets", "color": "brown", "min_price": 150, "max_price": 150}),
    ("Find yellow raincoats costing between $30 and $90.", {"category": "Raincoats", "color": "yellow", "min_price": 30, "max_price": 90}),
    ("I want striped button-down shirts.", {"category": "Button-Down Shirts"}),
    ("Any olive cargo pants under 60 dollars?", {"category": "Cargo Pants", "color": "olive", "max_price": 60}),
    ("Search for black ankle boots costing at least $55.", {"category": "Ankle Boots", "color": "black", "min_price": 55}),
    ("Find cream-colored blazers.", {"category": "Blazers", "color": "cream"}),
    ("Show me denim shorts from $20 to $50.", {"category": "Denim Shorts", "min_price": 20, "max_price": 50}),
    ("I need a lightweight windbreaker for less than $75.", {"category": "Windbreakers", "max_price": 75}),
    ("Look for teal scarves.", {"category": "Scarves", "color": "teal"}),
    ("Find tan loafers under $100.", {"category": "Loafers", "color": "tan", "max_price": 100}),
    ("Show me floral skirts between $25 and $60.", {"category": "Skirts", "min_price": 25, "max_price": 60}),
    ("I'd like charcoal dress pants.", {"category": "Dress Pants", "color": "charcoal"}),
    ("Start fresh: find orange athletic tops below $40.", {"category": "Athletic Tops", "color": "orange", "max_price": 40}),
]
for i, (message, expected) in enumerate(searches, 16):
    cases.append(case(f"CH{i:03}", "new_search", message, expected))

# 20 filter modifications; each starts from an existing search.
base = {"category": "Jeans", "color": "black", "min_price": None, "max_price": 100}
hist = [{"role": "user", "content": "Find black jeans under $100."}]
modifications = [
    ("Make those gray instead.", {"color": "gray"}),
    ("Could you cap the price at $75?", {"max_price": 75}),
    ("Only show items costing at least $40.", {"min_price": 40}),
    ("Remove the color restriction.", {"clear_filters": ["color"]}),
    ("No maximum budget anymore.", {"clear_filters": ["max_price"]}),
    ("Actually, I meant blue.", {"color": "blue"}),
    ("Raise the minimum to $55.", {"min_price": 55}),
    ("Let me see black jeans under $80 instead.", {"color": "black", "max_price": 80}),
    ("Clear both the color and the price ceiling.", {"clear_filters": ["color", "max_price"]}),
    ("Keep the color, but remove the minimum price.", {"clear_filters": ["min_price"]}),
    ("Make the upper limit $90.", {"max_price": 90}),
    ("Switch the color to white.", {"color": "white"}),
    ("I don't want a minimum spend.", {"clear_filters": ["min_price"]}),
    ("Keep these filters, but set the minimum to $25.", {"min_price": 25}),
    ("Remove all price limits.", {"clear_filters": ["min_price", "max_price"]}),
    ("Change the color to dark blue.", {"color": "dark blue"}),
    ("Keep the same jeans, but lower the cap to $65.", {"max_price": 65}),
    ("No color preference, and cap it at $85.", {"clear_filters": ["color"], "max_price": 85}),
    ("Set the minimum to $20 and maximum to $70.", {"min_price": 20, "max_price": 70}),
    ("Remove the price ceiling but keep the color.", {"clear_filters": ["max_price"]}),
]
for i, (message, expected) in enumerate(modifications, 36):
    cases.append(case(f"CH{i:03}", "modify_filters", message, expected, base, hist))

# 15 explicit clear-filter requests
clear_cases = [
    ("Forget the color and category restrictions.", {"clear_filters": ["color", "category"]}),
    ("Remove the minimum and maximum price limits.", {"clear_filters": ["min_price", "max_price"]}),
    ("I no longer care about the category.", {"clear_filters": ["category"]}),
    ("Clear the color filter only.", {"clear_filters": ["color"]}),
    ("Take away the minimum price requirement.", {"clear_filters": ["min_price"]}),
    ("Delete the upper price bound.", {"clear_filters": ["max_price"]}),
    ("Remove every filter from this search.", {"clear_filters": ["category", "color", "min_price", "max_price"]}),
    ("No category restriction, please.", {"clear_filters": ["category"]}),
    ("I don't need a price floor anymore.", {"clear_filters": ["min_price"]}),
    ("Drop the color and minimum price filters.", {"clear_filters": ["color", "min_price"]}),
    ("Please remove the price cap.", {"clear_filters": ["max_price"]}),
    ("Clear category and both price limits.", {"clear_filters": ["category", "min_price", "max_price"]}),
    ("Keep everything except the color condition.", {"clear_filters": ["color"]}),
    ("Remove the price range altogether.", {"clear_filters": ["min_price", "max_price"]}),
    ("Take off the category and color filters.", {"clear_filters": ["category", "color"]}),
]
clear_base = {"category": "Sweaters", "color": "green", "min_price": 20, "max_price": 80}
clear_hist = [{"role": "user", "content": "Find green sweaters between $20 and $80."}]
for i, (message, expected) in enumerate(clear_cases, 56):
    cases.append(case(f"CH{i:03}", "clear_filters", message, expected, clear_base, clear_hist))

# 15 colloquial or context-dependent cases
colloquial = [
    ("Got anything in plum?", "new_search", {"color": "plum"}),
    ("Something comfy for lounging, maybe joggers.", "new_search", {"category": "Joggers"}),
    ("Can we make that cheaper, like under 35?", "modify_filters", {"max_price": 35}),
    ("Same thing but in cream.", "modify_filters", {"color": "cream"}),
    ("Start over and show me olive chinos.", "new_search", {"category": "Chinos", "color": "olive"}),
    ("Anything less spendy than 50 bucks?", "new_search", {"max_price": 50}),
    ("Let's ditch the color thing.", "modify_filters", {"clear_filters": ["color"]}),
    ("Actually, switch to cardigans.", "modify_filters", {"category": "Cardigans"}),
    ("New search: tan loafers.", "new_search", {"category": "Loafers", "color": "tan"}),
    ("No price ceiling, thanks.", "modify_filters", {"clear_filters": ["max_price"]}),
    ("Could you show me the same style in red?", "modify_filters", {"color": "red"}),
    ("I'm looking for something under 42, no specific color.", "new_search", {"max_price": 42}),
    ("Lose the category filter; I'll browse broadly.", "modify_filters", {"clear_filters": ["category"]}),
    ("Different item entirely: a gray blazer.", "new_search", {"category": "Blazers", "color": "gray"}),
    ("Keep the category but get rid of all price limits.", "modify_filters", {"clear_filters": ["min_price", "max_price"]}),
]
for i, (message, action, expected) in enumerate(colloquial, 71):
    previous = base if action == "modify_filters" else {}
    history = hist if action == "modify_filters" else []
    cases.append(case(f"CH{i:03}", "colloquial_ambiguous", message,
                      {"action": action, **expected}, previous, history))

# 15 boundary/conflict cases
boundary = [
    ("Find blue shirts under $0.", {"intent": "product_search", "action": "new_search", "category": "Shirts", "color": "blue", "max_price": 0}),
    ("Show me jeans between $90 and $40.", {"intent": "product_search", "action": "new_search", "category": "Jeans", "min_price": 40, "max_price": 90}),
    ("Can you explain how to choose jeans?", {"intent": "general", "action": "general"}),
    ("I want a coat, but don't apply any color filter.", {"intent": "product_search", "action": "new_search", "category": "Coats"}),
    ("Search for a green skirt under $50, and start a new search.", {"intent": "product_search", "action": "new_search", "category": "Skirts", "color": "green", "max_price": 50}),
    ("Make it under $60, not $40.", {"intent": "product_search", "action": "modify_filters", "max_price": 60}),
    ("I want blue jeans, not a discussion about jeans.", {"intent": "product_search", "action": "new_search", "category": "Jeans", "color": "blue"}),
    ("Forget the previous search; show me a red scarf.", {"intent": "product_search", "action": "new_search", "category": "Scarves", "color": "red"}),
    ("Can you recommend a color for my navy jacket?", {"intent": "general", "action": "general"}),
    ("Remove the minimum price but set the maximum to $70.", {"intent": "product_search", "action": "modify_filters", "max_price": 70, "clear_filters": ["min_price"]}),
    ("Find black boots between $50 and $120.", {"intent": "product_search", "action": "new_search", "category": "Boots", "color": "black", "min_price": 50, "max_price": 120}),
    ("I want something below $30, no category specified.", {"intent": "product_search", "action": "new_search", "max_price": 30}),
    ("Don't change the category; just make it blue.", {"intent": "product_search", "action": "modify_filters", "color": "blue"}),
    ("Start a fresh search for hoodies with no price limit.", {"intent": "product_search", "action": "new_search", "category": "Hoodies"}),
    ("What's the difference between a blazer and a suit jacket?", {"intent": "general", "action": "general"}),
]
for i, (message, expected) in enumerate(boundary, 86):
    action = expected.get("action", "new_search")
    intent = expected.get("intent", "product_search")
    group = "conflict_boundary"
    complete_expected = {k: v for k, v in expected.items() if k not in ("intent", "action")}
    previous = base if action == "modify_filters" else {}
    history = hist if action == "modify_filters" else []
    cases.append(case(f"CH{i:03}", group, message,
                      {"intent": intent, "action": action, **complete_expected},
                      previous, history))

assert len(cases) == 100, f"Expected 100 cases, got {len(cases)}"
assert len({c["id"] for c in cases}) == 100, "Duplicate IDs"

counts = Counter(c["group"] for c in cases)
expected_counts = {
    "general": 15,
    "new_search": 20,
    "modify_filters": 20,
    "clear_filters": 15,
    "colloquial_ambiguous": 15,
    "conflict_boundary": 15,
}
assert counts == expected_counts, f"Unexpected group counts: {counts}"

for item in cases:
    ChatIntent.model_validate(item["expected"])

OUT.write_text(
    "".join(json.dumps(item, ensure_ascii=False, default=str) + "\n" for item in cases)
)
print(f"Wrote {len(cases)} cases to {OUT}")
print("Group counts:", dict(counts))
print("All expected outputs pass ChatIntent validation.")
