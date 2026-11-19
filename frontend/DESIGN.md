# Fairlot design

Auction-lot board for Bay Area bikes, computers, and furniture. Dense, left aligned, and quiet except for one moving rail. Not a SaaS landing page.

## Tokens

Set on `:root` in `src/styles.css`.

| Token | Hex | Use |
| --- | --- | --- |
| `--paper` | `#F3EFE4` | Page background. Warm paper, not pure white. |
| `--paper-2` | `#E6DFD0` | Photo wells, skeletons, empty slots. |
| `--ink` | `#241C14` | Text, rules, focus, selected chips. 14.6:1 on paper. |
| `--muted` | `#5C5146` | Neighborhoods, dates, secondary lines. 6.7:1 on paper. |
| `--line` | `#D4C6AE` | Hairline dividers. |
| `--gold` | `#8A6424` | Rules, the wordmark underline, good-deal underline, buyer spoke. Not body text. |
| `--gold-fill` | `#D4B56A` | The Sample mark. Ink on this fill is 8.5:1. |
| `--red` | `#9E1C14` | Search, Make an offer, Publish, Overpriced, No deal, error rule. 7.0:1 on paper and the reverse. |
| `--red-deep` | `#7C140F` | Hover on red fills. |

Focus is a 2px ink outline with a 3px offset. Gold is not used for small text or for focus.

## Type

- **Newsreader** (Fontsource, self-hosted): wordmark, hero, page titles, Deal / No deal.
- **IBM Plex Sans** (Fontsource, self-hosted): UI, labels, and prices. Prices use `font-variant-numeric: tabular-nums`.
- Body is 17px. Nothing in the UI is under 16px.
- Headlines are left aligned. The hero title wraps at about 11 characters so it stacks as a column, not a centered banner.

## Layout

- Sticky masthead: wordmark, category links (`All`, `Bikes`, `Computers`, `Furniture`), `Add a listing`, then the search form.
- Search is a real GET form (`id="lot-search"`, field `q`). Home (`/`) is the newest listings. Any `q` switches to the catalogue, with `category` and `sort` in the URL.
- Listing grid: 2 columns on a phone, 3 from 720px, 4 from 1100px. Photos are 4:3, cropped with `object-fit: cover`.
- Card order: photo, price, title, neighborhood, verdict, trust, and Sample when `origin` is `seed`.
- Listing detail keeps the photo sticky on wide screens. Comps are a table. Signals are sentences.
- `Add a listing` is only the header control. It opens `/sell`. The empty board does not ask anyone to post.

## Motion

Three places, all off when `prefers-reduced-motion: reduce`:

1. The hero rail translates with scroll (GSAP ScrollTrigger). With listings it carries their photos and titles. Without listings it carries the words Bikes, Computers, Furniture, Priced, Checked. The rail is `aria-hidden`.
2. Prices already on screen count up once (Motion). The real amount is in a visually hidden span so a screen reader does not hear the intermediate numbers.
3. On a negotiation, a gold or ink spoke grows beside each turn as it scrolls into view. The words stay at full contrast.

Lenis smooths wheel scrolling on a fine pointer wider than 800px, and only when motion is allowed. Phones keep native scrolling. Photo crops wipe in once as they enter; they are never hidden if script does not run.

## Empty, loading, error

- Loading: photo-shaped skeletons and a polite live region.
- Home, successful, zero listings: "Listings coming soon".
- A category with nothing: "No bikes on the board yet" (or computers, furniture).
- A search with nothing: "Nothing matches that search".
- The request failed: a red rule, the server's message, and Try again.
- A missing listing or transcript has its own heading and a link back.

## Avoid

- Inter, Geist, or a default system stack as the design face.
- Purple or indigo gradients, glassmorphism, and blob backgrounds.
- A centered hero plus three identical feature cards.
- The same radius and the same shadow on every block. Corners are square. There is no drop shadow.
- Emoji or icon fonts standing in for content. Phosphor is not used.
- Gold as small text. Red on every button. Fade-up on every element.
- All-caps eyebrows, middot metadata strings, and a trailing arrow on every link.
- A max or minimum field, or the want token anywhere in the document.

## Markup for agents

Stable hooks live in `public/llms.txt`: listing `data-*` attributes, action `data-action` values, and the search URL.
