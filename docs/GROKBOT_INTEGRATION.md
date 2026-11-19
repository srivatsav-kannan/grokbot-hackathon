# Grok Bot integration

A user's own Grok Bot is a remote control for Fairlot. It posts a want, reads matches, and points the buyer agent at a listing. Negotiation runs on the Fairlot server. The bot never receives a buyer's max or a seller's minimum.

Base URL is the public site, path prefix `/api`. Plain HTTP and JSON. Send `Content-Type: application/json` except for the photo lister, which the bot does not need.

## Flow

1. The person tells their Grok Bot what they want ("road bike under $400 in SF").
2. The bot calls `POST /api/wants` and stores the returned `access_token` for that want only.
3. The bot calls `POST /api/wants/{id}/hunt`, or `POST /api/wants/{id}/target` with one `listing_id`.
4. The bot polls `GET /api/wants/{id}` and tells the person the matches (price verdict, trust) and whether a deal landed.
5. The bot does not ask the server for the max, does not invent one in later calls, and does not repeat the token in chat.

Values below are fake. `tok_example_not_a_real_secret` is not a credential.

## Token handling

- Create returns `access_token` once. Later routes need `Authorization: Bearer <access_token>`.
- Scope is one want. A token does not list other people's wants or any limits.
- Keep it in the bot's private memory for that conversation. Do not put it in a public post, a log line, or a message the user will forward.
- If the token is missing, the API returns `401`. Create a new want. Do not guess.

## Endpoints

### `POST /api/wants`

```http
POST /api/wants
Content-Type: application/json

{
  "text": "road bike under $400 in SF",
  "category": "bikes",
  "area": "San Francisco"
}
```

`category` and `area` are optional. A budget in `text` is stored on the server as the private max and is not echoed back.

```json
{
  "id": "wnt_demo",
  "access_token": "tok_example_not_a_real_secret",
  "status": "open"
}
```

### `GET /api/wants/{id}`

```http
GET /api/wants/wnt_demo
Authorization: Bearer tok_example_not_a_real_secret
```

```json
{
  "id": "wnt_demo",
  "text": "road bike under $400 in SF",
  "criteria": {
    "category": "bikes",
    "area": "San Francisco",
    "keywords": ["road bike"]
  },
  "status": "negotiating",
  "matches": [
    {
      "listing_id": "lst_demo",
      "score": 0.86,
      "reason": "Road bike in San Francisco, asking price inside the stated budget.",
      "title": "City bike, ready to ride",
      "price": 280,
      "appraisal": { "estimated_value": 340, "verdict": "good_deal" },
      "inspection": { "trust_level": "high" }
    }
  ],
  "negotiations": [
    {
      "id": "neg_demo",
      "listing_id": "lst_demo",
      "status": "closed",
      "outcome": "deal",
      "messages": [
        {
          "from": "buyer",
          "kind": "offer",
          "amount": 300,
          "text": "I can do 300 if I pick it up this week.",
          "at": "2026-11-19T18:05:00Z"
        },
        {
          "from": "seller",
          "kind": "accept",
          "amount": 300,
          "text": "That works. Pickup this week.",
          "at": "2026-11-19T18:05:02Z"
        }
      ]
    }
  ]
}
```

No `buyer_max`, `seller_min`, or token in this body.

### `POST /api/wants/{id}/hunt`

```http
POST /api/wants/wnt_demo/hunt
Authorization: Bearer tok_example_not_a_real_secret
```

Empty body. The buyer agent searches and opens negotiations with the top matches. Response matches GET.

### `POST /api/wants/{id}/target`

```http
POST /api/wants/wnt_demo/target
Authorization: Bearer tok_example_not_a_real_secret
Content-Type: application/json

{ "listing_id": "lst_demo" }
```

The buyer agent negotiates on that listing only. Response matches GET.

The public feed (`GET /api/listings`, `GET /api/listings/{id}`) needs no token. Use it when the person names a specific bike, computer, or desk and the bot needs a `listing_id`.

## As a Grok Bot skill

Give the bot these instructions and no others about price limits:

1. When the user describes something to buy in bikes, computers, or furniture, call `POST /api/wants` with their words. Save `id` and `access_token` privately.
2. If they already have a listing id, call `POST /api/wants/{id}/target`. Otherwise call `POST /api/wants/{id}/hunt`.
3. Read `GET /api/wants/{id}`. Summarize each match with asking price, verdict, and trust. Report deal or no deal from `negotiations`.
4. Never send, store in the reply, or ask the API to return a max, a minimum, or the access token.
5. Speak in short updates: what you searched, what looked fair and trustworthy, and the outcome.
