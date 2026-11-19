import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, createDraft, publishListing } from "../api/client";
import { CATEGORIES, CATEGORY_LABEL } from "../lib/format";
import { useTitle } from "../lib/title";
import type { Category, Draft } from "../types";

const NEIGHBORHOODS = [
  "Mission, San Francisco",
  "Temescal, Oakland",
  "Downtown Berkeley",
  "Hayes Valley, San Francisco",
  "SoMa, San Francisco",
  "Palo Alto",
  "Sunnyvale",
  "Richmond District, San Francisco",
  "Bernal Heights, San Francisco",
];

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Could not read that photo."));
    reader.readAsDataURL(file);
  });
}

export function SellPage() {
  const navigate = useNavigate();
  useTitle("Add a listing");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [category, setCategory] = useState<Category>("furniture");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [neighborhood, setNeighborhood] = useState("");
  const [phase, setPhase] = useState<"idle" | "drafting" | "publishing">("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  async function onDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const chosen = data.get("photo");
    if (!(chosen instanceof File) || chosen.size === 0) {
      setError("Choose a photo first.");
      return;
    }
    if (chosen.size > 2_000_000) {
      setError("Photo must be under 2 MB.");
      return;
    }
    setFile(chosen);
    setPhase("drafting");
    setError("");
    try {
      const response = await createDraft(chosen);
      setDraft(response.draft);
      setCategory(response.draft.category);
      setTitle(response.draft.title);
      setDescription(response.draft.description);
      setPrice(String(response.draft.suggested_price));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The draft didn't come back.");
    } finally {
      setPhase("idle");
    }
  }

  async function onPublish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !draft) return;
    const amount = Number.parseInt(price, 10);
    if (!Number.isFinite(amount) || amount < 0) {
      setError("Enter a price in whole dollars.");
      return;
    }
    setPhase("publishing");
    setError("");
    try {
      const photoUrl = await fileToDataUrl(file);
      const listing = await publishListing({
        category,
        title: title.trim(),
        description: description.trim(),
        price: amount,
        photos: [photoUrl],
        neighborhood: neighborhood.trim(),
      });
      navigate(`/listings/${listing.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The listing wasn't published.");
      setPhase("idle");
    }
  }

  return (
    <div className="wrap board sell">
      <h1>Add a listing</h1>
      <p className="lede">
        Start with a photo. Fairlot drafts the title, category, and price. Edit anything before it
        goes on the board. The listing is priced and checked as soon as you publish.
      </p>

      <form id="sell-photo-form" onSubmit={onDraft}>
        <label className="file-field" htmlFor="sell-photo">
          Photo
          <input
            id="sell-photo"
            name="photo"
            type="file"
            accept="image/*"
            required={!draft}
            onChange={(event) => {
              const next = event.target.files?.[0] ?? null;
              setFile(next);
            }}
          />
        </label>
        {preview ? (
          <img className="sell-preview" src={preview} alt="Selected listing photo" width={800} height={600} />
        ) : null}
        <button type="submit" data-action="draft" disabled={phase !== "idle"}>
          {phase === "drafting" ? "Drafting…" : "Draft the listing"}
        </button>
      </form>

      {draft ? (
        <form id="sell-publish-form" className="publish-form" onSubmit={onPublish}>
          <h2>Edit the draft</h2>
          <label htmlFor="sell-category">
            Category
            <select
              id="sell-category"
              name="category"
              value={category}
              onChange={(event) => setCategory(event.target.value as Category)}
              required
            >
              {CATEGORIES.map((item) => (
                <option key={item} value={item}>
                  {CATEGORY_LABEL[item]}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="sell-title">
            Title
            <input
              id="sell-title"
              name="title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
            />
          </label>
          <label htmlFor="sell-description">
            Description
            <textarea
              id="sell-description"
              name="description"
              rows={5}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              required
            />
          </label>
          <label htmlFor="sell-price">
            Asking price in dollars
            <input
              id="sell-price"
              name="price"
              type="number"
              min={0}
              step={1}
              inputMode="numeric"
              value={price}
              onChange={(event) => setPrice(event.target.value)}
              required
            />
          </label>
          <label htmlFor="sell-neighborhood">
            Neighborhood
            <input
              id="sell-neighborhood"
              name="neighborhood"
              list="neighborhoods"
              value={neighborhood}
              onChange={(event) => setNeighborhood(event.target.value)}
              required
            />
          </label>
          <datalist id="neighborhoods">
            {NEIGHBORHOODS.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          <button
            type="submit"
            className="button-primary"
            data-action="publish"
            disabled={phase !== "idle"}
          >
            {phase === "publishing" ? "Publishing…" : "Publish"}
          </button>
        </form>
      ) : null}

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
