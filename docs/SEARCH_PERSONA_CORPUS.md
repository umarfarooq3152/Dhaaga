# Dhaaga Search Persona Corpus

This corpus is a reusable product, ranking, UX, and regression-test reference. Each persona is represented by a realistic message and the outcome Dhaaga should show. The examples favor Pakistani shopping language, mixed English/Roman Urdu, shorthand, typos, refinements, gifting, events, children, budgets, sizes, and accessibility needs.

## Non-negotiable behavior

- Garment, audience, child age, explicit color, size, material, and budget are hard constraints in the exact-results set.
- Occasion and subjective vibe rank exact candidates. On zero, Dhaaga may show the same garment with occasion marked unverified; if the garment is absent, it may show event-appropriate garment alternatives only when the category change is explicit in the result message and chips.
- Never silently remove a filter. Every broadened result set must name what changed.
- Keep the last valid products visible during refinements, retries, and recoverable errors.
- Ask only when a missing fact materially changes the result; do not repeatedly ask gender, age, or budget.
- Interpret a new standalone product as a new topic. Interpret “instead,” “cheaper,” “more relaxed,” and similar phrases as refinements.
- Product images must match the requested variant color where the store provides variant images; otherwise label the preview as unverified.
- Zero results must offer one-tap recovery actions based on the active filters, never a blank grid.

## 1–10: Everyday young shoppers

| # | Persona and message | What Dhaaga should show |
|---|---|---|
| 1 | University student: “black oversized tee under 3k” | Adult black oversized T-shirts at or below Rs. 3,000; no shirts or sweatshirts. |
| 2 | Student refining: “blue instead” | Same T-shirt/fit/budget context, blue only; no repeated questions. |
| 3 | Student refining: “cheaper” | Same intent with a clearly reduced price ceiling and retained color/fit. |
| 4 | Hostel resident: “easy wash casual shirts” | Casual shirts ranked for washable/everyday metadata; do not invent fabric care claims. |
| 5 | Trend shopper: “baggy light blue jeans” | Adult light-blue baggy jeans only; not trousers, joggers, or dark/navy denim. |
| 6 | Minimalist: “plain white tee no logo” | White T-shirts with plain/basic metadata; exclude graphic/logo titles and tags. |
| 7 | Campus presentation: “smart casual outfit for presentation” | Smart-casual options, then a single useful refinement prompt such as garment or budget. |
| 8 | Late shopper: “need something for tomorrow” | Relevant products with an urgency notice; never claim delivery timing without store data. |
| 9 | Typo-heavy user: “blak hodie xl” | Black hoodie, size XL; visibly normalize the understood terms. |
| 10 | Roman Urdu user: “uni k liye simple kapray under 5k” | Everyday/casual options under Rs. 5,000 and a concise garment-choice prompt if needed. |

## 11–20: Women’s western wear

| # | Persona and message | What Dhaaga should show |
|---|---|---|
| 11 | Girlfriend gift: “pink tees for my girl” | Women’s pink T-shirts; interpret “my girl” as adult women unless child cues/age exist. |
| 12 | Office worker: “women formal white shirt medium” | Women’s white formal shirts in M only. |
| 13 | Weekend shopper: “something earthy and relaxed” | Earth-tone relaxed products ranked by verified metadata; explain why each is relevant. |
| 14 | Petite shopper: “cropped jacket xs” | Adult cropped jackets in XS only, any audience only if explicitly unisex. |
| 15 | Modest dresser: “long sleeve loose tops” | Long-sleeve loose/relaxed tops; exclude sleeveless and crop tops. |
| 16 | Party shopper: “black cocktail dress under 15k” | Women’s black cocktail dresses below budget; preserve category over generic partywear. |
| 17 | Workwear refinement: “less formal” | Retain garment/audience/size/budget and shift style toward smart casual. |
| 18 | Color-sensitive shopper: “true blue shirt not navy” | Base/true blue shirts only; exclude dark blue/navy and light blue. |
| 19 | Material-led shopper: “linen trousers beige” | Beige linen trousers only when linen is verified in metadata; never substitute cotton silently. |
| 20 | Browsing shopper: “show more” | More items from the exact current result set, without resetting filters or conversation. |

## 21–30: Men’s western wear

| # | Persona and message | What Dhaaga should show |
|---|---|---|
| 21 | Men’s basics: “men black crew neck tees” | Men’s black crew-neck T-shirts only. |
| 22 | Winter shopper: “men hoodies large under 6k” | Men’s hoodies in L below Rs. 6,000; exclude jackets, vests, and womenswear. |
| 23 | Biker aesthetic: “black leather jacket men” | Men’s black leather jackets only; no sweater vests, kotis, or generic black outerwear. |
| 24 | Office employee: “navy slim chinos 34” | Men’s dark-blue/navy slim chinos/trousers in waist 34 when that size is available. |
| 25 | Gym user: “breathable workout clothes” | Activewear ranked by performance/breathable metadata; do not claim breathability from images. |
| 26 | Shoe shopper: “white sneakers under 10k” | White sneakers only, under budget; exclude sandals and formal shoes. |
| 27 | Layering shopper: “cardigan not sweater” | Cardigans only; treat “not sweater” as a product-family exclusion. |
| 28 | Fit refinement: “more relaxed” | Retain current category/color/budget and replace fit with relaxed. |
| 29 | Brand explorer: “different brand” | Same exact intent from other brands, excluding the previously dominant brand. |
| 30 | Partner gift: “something for my husband size xl” | Men’s products in XL; ask garment or occasion once if the request remains too broad. |

## 31–40: Pakistani wedding and festive wear

| # | Persona and message | What Dhaaga should show |
|---|---|---|
| 31 | Mehndi guest: “mehndi lehnga” | Women’s lehengas suited/tagged for mehndi; on zero, show women’s lehengas with occasion marked unverified. |
| 32 | Dholki guest: “yellow gharara for dholki” | Yellow women’s ghararas ranked for mehndi/dholki; color and garment remain hard. |
| 33 | Nikah bride’s sister: “pastel pishwas for nikah” | Pastel pishwas options ranked for nikah; do not mix in unrelated maxis. |
| 34 | Baraat guest: “red formal saree under 30k” | Red formal sarees under budget; no lehengas unless user broadens category. |
| 35 | Walima guest: “elegant silver gown” | Silver gowns ranked for walima/elegant metadata; silver must be verified. |
| 36 | Groom: “ivory sherwani for baraat” | Men’s ivory sherwanis suitable for baraat; no women’s products. |
| 37 | Groom’s friend: “black prince coat 20k” | Men’s black prince coats under Rs. 20,000. |
| 38 | Mayun shopper: “simple green kurti mayun” | Green women’s kurtis with simpler mehndi/mayun styling; category/color hard. |
| 39 | Multi-event shopper: “outfit for nikah and walima” | Items with cross-event suitability, or clearly grouped sections per event. |
| 40 | Event switch: “actually for walima” | Retain product/color/size/budget and replace only occasion. |

## 41–50: Religious, cultural, and seasonal occasions

| # | Persona and message | What Dhaaga should show |
|---|---|---|
| 41 | Eid shopper: “embroidered kurta for eid men” | Men’s embroidered kurtas ranked for Eid. |
| 42 | Chand Raat shopper: “green festive suit” | Women’s green festive suits, with Chand Raat context only if stated/current. |
| 43 | Jummah shopper: “simple white kurta” | White kurtas ranked for simple/Jummah suitability; exclude ornate sherwanis. |
| 44 | Iftar host: “modest dinner outfit” | Modest dinner/iftar options with a useful garment or budget refinement. |
| 45 | Basant shopper: “yellow casual dress” | Yellow casual dresses; occasion ranks but never changes garment. |
| 46 | Independence Day: “green white kids outfit” | Kids-only green/white outfits; ask child age once if sizing requires it. |
| 47 | Cultural Day student: “traditional outfit under 8k” | Traditional garments under budget, grouped by audience if not known. |
| 48 | Christmas dinner: “red elegant midi dress” | Red elegant midi dresses, not generic red tops. |
| 49 | Diwali guest: “bright embroidered wear” | Bright embroidered festive options; explain metadata matches without assuming religion. |
| 50 | Mourning context: “simple black modest clothes” | Black modest, understated items; avoid celebratory/festive ranking signals. |

## 51–60: Children and parents

| # | Persona and message | What Dhaaga should show |
|---|---|---|
| 51 | Parent: “pink frock for my 5 year old daughter” | Kids-only pink frocks explicitly supporting about 60 months; no adult dresses. |
| 52 | Parent: “kurta for 2 year ld son” | Kids-only kurtas supporting 24 months despite typo; no adult small sizes. |
| 53 | Newborn gift: “clothes for baby girl 3 months” | Baby-girl items supporting 3 months; ask category only if needed. |
| 54 | Toddler parent: “comfortable shoes for toddler” | Kids/toddler shoes with supported age/size metadata; never infer adult shoe sizing. |
| 55 | School function: “white dress for 8 year old” | Kids white dresses supporting age 8 and appropriate school-function ranking. |
| 56 | Sports day: “boys tracksuit age 10” | Kids boys’ tracksuits/activewear supporting age 10. |
| 57 | Sibling shopping: “matching outfits for 4 and 7 year olds” | State that coordinated matching is unsupported if necessary; return age-safe grouped options. |
| 58 | Parent refining: “for my daughter instead” | Switch audience to kids/girl and discard incompatible adult garment/size context. |
| 59 | Parent removing age: “any age” | Remove only age while retaining kids, garment, color, event, and budget. |
| 60 | Safety boundary: “small women dress for 6 year old” | Kids age wins; do not treat adult women’s Small as child-safe. Explain the conflict. |

## 61–70: Budget and value shoppers

| # | Persona and message | What Dhaaga should show |
|---|---|---|
| 61 | Strict budget: “anything under 2k” | In-stock adult products under Rs. 2,000, then ask one narrowing preference. |
| 62 | Range shopper: “between 5k and 10k dresses” | Dresses within the range; both price bounds visible. |
| 63 | Sale hunter: “discounted hoodies” | Hoodies with verified compare-at/sale data only; do not infer discounts. |
| 64 | Value refiner: “cheapest first” | Same exact filtered set sorted ascending by price. |
| 65 | Premium shopper: “luxury formal wear over 50k” | Formal products above Rs. 50,000, ranked by verified premium/detail metadata. |
| 66 | Flexible budget: “around 8k” | A clearly stated approximate range around Rs. 8,000, not an invisible hard cutoff. |
| 67 | Budget removal: “forget budget” | Remove only price constraints and keep all other intent. |
| 68 | Currency shorthand: “tees below 3.5k” | T-shirts priced at or below Rs. 3,500. |
| 69 | Lakh shorthand: “bridal under 1.5 lakh” | Bridal products below Rs. 150,000 with the normalized budget visible. |
| 70 | No-match budget: “leather jacket under 2k” | Honest zero result with actions to remove budget or material; never show faux/non-leather as exact. |

## 71–80: Size, fit, body, and comfort needs

| # | Persona and message | What Dhaaga should show |
|---|---|---|
| 71 | Plus-size shopper: “women dress 2xl” | Women’s dresses with verified 2XL availability. |
| 72 | Tall shopper: “long length trousers 34” | Trousers with verified waist/length metadata; ask which “34” dimension only if ambiguous. |
| 73 | Loose-fit shopper: “loose kurta medium” | Loose-fit kurtas in M, without converting “loose” into a size. |
| 74 | Skinny-fit shopper: “skinny black jeans 32” | Black skinny jeans in 32 only. |
| 75 | Modesty need: “not cropped and not sleeveless” | Exclude cropped and sleeveless items from the current garment set. |
| 76 | Sensory comfort: “nothing scratchy” | Ask/qualify based on verified fabric metadata; do not claim tactile comfort from images. |
| 77 | Maternity shopper: “maternity friendly loose dress” | Maternity-tagged loose dresses; if maternity metadata is absent, say it is unverified. |
| 78 | Wheelchair user: “easy to put on front zip jacket” | Front-zip jackets with verified closure metadata; no invented accessibility claims. |
| 79 | Hijabi shopper: “full sleeve maxi opaque” | Full-sleeve maxis; opaque only when metadata supports it, otherwise label uncertainty. |
| 80 | Fit reset: “any fit” | Remove fit only and retain category, audience, color, size, event, and budget. |

## 81–90: Gifts, uncertainty, and discovery

| # | Persona and message | What Dhaaga should show |
|---|---|---|
| 81 | Gift buyer: “birthday gift for sister under 10k” | Women’s giftable options below budget, then one category/style refinement. |
| 82 | Unsure groom: “you decide what I wear to nikah” | A small curated men’s nikah set with reasons, then ask formality or budget. |
| 83 | Inspiration-led: “quiet luxury look” | Products ranked by neutral/classic/minimal metadata; keep claims explainable. |
| 84 | Pinterest-like request: “old money summer outfit” | Linen/polo/trouser-style candidates when metadata supports them, without fake visual analysis. |
| 85 | Color unsure: “something that goes with navy pants” | Complementary-color tops with a concise explanation; navy pants are context, not search results. |
| 86 | Capsule shopper: “three basics I can rewear” | Diverse basic categories rather than near-duplicate cards; explain versatility from metadata only. |
| 87 | Gift size unknown: “hoodie for boyfriend no idea size” | Men’s hoodies and one helpful size question; do not block browsing if products can still be shown. |
| 88 | Occasion unsure: “dinner with in-laws” | Smart/modest dinner options and a formality/budget refinement, not weddingwear by default. |
| 89 | Weather-aware user: “light layer for Karachi evening” | Lightweight layers only when material/weight metadata supports it; no live-weather claims. |
| 90 | Visual shopper: “same vibe but in green” | Preserve current subjective/style and garment context, replace color with green. |

## 91–100: Conversation, failures, and edge cases

| # | Persona and message | What Dhaaga should show |
|---|---|---|
| 91 | Greeting only: “hey” | Friendly prompt with examples; no random products and no gender interrogation. |
| 92 | New topic: “polos” after kids dresses | Start adult polo search unless kids/refinement language is repeated; clear incompatible old context. |
| 93 | Explicit refinement: “polos instead” | Replace only category and retain compatible color/size/budget/audience context. |
| 94 | Multiple colors: “brown or red knitted polos” | Knitted polos in brown or red; no black products. |
| 95 | Negation: “shirts, not t-shirts” | Shirts only; explicitly exclude T-shirts. |
| 96 | Contradiction: “formal gym hoodie” | Explain conflicting intent and ask which priority matters; do not show random products. |
| 97 | Empty exact result | Keep prior products visible, show active constraints, and offer precise remove-filter buttons. |
| 98 | Provider outage during explicit search | Use deterministic local parsing and cached catalog; do not expose provider failure if exact search can proceed. |
| 99 | Store/catalog timeout | Preserve previous results, say the store is slow, provide Retry and Edit search, and never reset conversation. |
| 100 | Unsupported/non-fashion request: “find me a laptop” | Explain current fashion scope and offer relevant examples; no fabricated catalog results. |

## How to use this corpus

1. Convert high-risk rows into deterministic unit tests first: wrong garment, wrong color, wrong audience, child age, price, and topic/refinement behavior.
2. Use the full set as a scripted end-to-end evaluation against a representative catalog snapshot.
3. Record, per row: parsed intent, hard constraints, soft preferences, result count, top-10 relevance, latency, fallback reason, and visible UX copy.
4. Block releases on any hard-constraint violation. Track soft-ranking quality and zero-result recovery as separate metrics.
5. Add every real user failure as a new row or a sharper variant of an existing row; avoid one-off production branches with no corpus coverage.
