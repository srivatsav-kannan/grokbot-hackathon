# Fairlot design

Auction-lot board for Bay Area bikes, computers, and furniture. Dense, left aligned, and quiet except for one moving rail. Not a SaaS landing page.

## Tokens

Set on `:root` in `src/styles.css`.

| Token | Hex | Use |
| --- | --- | --- |
| `--paper` | `#FFFEFB` | Page background. Slightly warm white, not cream. |
| `--paper-2` | `#FFF6D8` | Gold wash for the hero rail, drag-over, and empty slots. |
| `--ink` | `#1C140F` | Text and focus. About 18:1 on the page. |
| `--muted` | `#5C5146` | Neighborhoods and dates. About 7.6:1 on the page. |
| `--line` | `#E2C56A` | Gold hairlines. |
| `--gold` | `#8A6412` | Borders on badges, photos, and the rail. Not small body text. |
| `--gold-fill` | `#E2B33C` | Wordmark underline, selected chips, Good deal, Sample, photo note. Ink on this fill is about 9:1. |
| `--gold-deep` | `#C49214` | Hover on a gold fill. |
| `--red` | `#9E1C14` | Search, Make an offer, Publish, Overpriced, No deal, and the error rule. |
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
2. On a negotiation, a gold or ink spoke grows beside each turn as it scrolls into view. The words stay at full contrast. Prices render their final dollar amount immediately, once, for sighted readers and screen readers.
3. The masthead shrinks after a short scroll so the first row of listings is not covered. `scroll-padding` follows the live header height.

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
