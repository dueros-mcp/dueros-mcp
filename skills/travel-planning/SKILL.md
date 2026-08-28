---
name: travel-planning
description: Plan practical trips with current destination research, geographically coherent daily itineraries, transportation and lodging guidance, budget ranges, reservation checklists, and optional polished HTML publishing. Use for vacations, multi-city travel, weekend trips, family travel, business-trip extensions, or requests for a shareable itinerary page. Do not use for generic project, study, or event plans.
---

# Travel Planning

Create a trip plan that is realistic enough to use, while keeping uncertain prices, availability, and live conditions clearly separated from confirmed facts.

## Collect The Brief

Reuse facts already supplied. Ask one compact question for any missing details that would materially change the trip:

- origin and destination or route;
- exact or flexible dates;
- travelers, ages, accessibility needs, and pace;
- total or per-person budget and currency;
- interests, must-see places, and places to avoid;
- transport and lodging preferences;
- dietary, visa, health, or other hard constraints.

Make low-risk assumptions only when they do not change bookings, safety, or major costs. State those assumptions in the result.

## Research Current Facts

Browse when current information affects the recommendation. Prefer official or primary sources for entry rules, public transportation, attraction hours, closures, permits, weather warnings, and safety notices. Use operators' own sites for schedules and fares when available.

- Distinguish confirmed facts from estimates and suggestions.
- Include the date checked for facts that can change.
- Never invent availability, prices, travel times, ratings, or reservation status.
- For recommendations that could consume substantial time or money, compare reasonable alternatives and explain the tradeoff.
- Do not book, purchase, reserve, or message anyone without explicit user authorization.

## Build The Itinerary

Produce the sections that help the specific trip; do not force empty sections.

- Trip summary with dates, route, party, pace, and budget target.
- Day-by-day itinerary grouped geographically to reduce backtracking.
- Realistic transfer, meal, rest, check-in, and contingency time.
- Arrival and departure logistics, local transportation, and intercity connections.
- Lodging-area guidance based on route and traveler needs; do not claim room availability.
- Budget ranges with assumptions and major cost drivers.
- Reservation and preparation checklist with suggested decision deadlines.
- Weather, accessibility, safety, closure, and entry-rule risks.
- One practical fallback for weather, fatigue, or a closure when it matters.

Prefer a usable plan over an overfilled schedule. Flag any day whose timing depends on an unverified connection or reservation.

## Create A Shareable HTML Page

When the user asks for a webpage, visual itinerary, or public link, read [references/design-taste-frontend.md](references/design-taste-frontend.md) completely before building the page. It is vendored design guidance inside this skill, not an external skill dependency. Apply only the parts relevant to a travel itinerary.

Create a responsive static page with accessible structure, print styles, and relative asset paths. A useful travel page normally emphasizes the route, daily schedule, transport transitions, budget, reservations, and practical notes. Use maps or images only when they materially improve navigation or understanding.

Keep secrets, passport details, booking references, private addresses, personal contact information, and precise live location out of public pages. Ask before including other sensitive personal details.

Validate the page locally at desktop and mobile widths. Check links, asset paths, visible copy, printing, and console errors before delivery.

## Publish With Surge

Publish only when the user explicitly asks for a public link. Explain that Surge pages are publicly accessible and are not password protected, then use the bundled script:

```bash
python3 <travel-planning-skill-dir>/scripts/deploy_surge.py \
  <html-file-or-site-dir> \
  --domain <chosen-name>.surge.sh
```

If no domain is supplied, choose a non-sensitive name derived from the destination plus a short suffix. The script uses `surge` when available and otherwise `npx --yes surge`.

Use `--dry-run` to validate packaging without publishing. Use `--check-auth-only` to confirm Surge login. If login is missing, stop and tell the user which login command is required. Do not expose the account name or credentials in the page.

After publishing, verify the URL returns HTTP 200 and return both the public URL and the local source path. Do not claim completion until the published page is reachable.

## Boundaries

- Verify rather than guess on visas, entry restrictions, health rules, safety alerts, and time-sensitive transport.
- Present travel and cost estimates as planning guidance, not guarantees.
- Preserve the user's chosen dates, budget, pace, and must-see priorities.
- Do not silently turn a travel-planning request into a public page; local output is the default unless publishing is requested.
