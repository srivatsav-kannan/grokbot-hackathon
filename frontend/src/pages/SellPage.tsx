import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, createDraft, publishListing } from "../api/client";
import { useAuth } from "../auth";
import { CATEGORIES, CATEGORY_LABEL, loginPath } from "../lib/format";
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

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Could not read that photo."));
    reader.readAsDataURL(file);
  });
}

/** Re-encode any photo the browser can show as a JPEG at most 1400px wide, so every listing photo displays everywhere. */
async function fileToDataUrl(file: File): Promise<string> {
  const original = await readAsDataUrl(file);
  const image = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image();
    el.onload = () => resolve(el);
    el.onerror = () => reject(new Error("That photo format can't be shown in browsers. Use a JPG or PNG."));
    el.src = original;
  });
  const scale = Math.min(1, 1400 / Math.max(image.naturalWidth, image.naturalHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(image.naturalWidth * scale);
  canvas.height = Math.round(image.naturalHeight * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) return original;
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.85);
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
  const [minimum, setMinimum] = useState("");
  const [neighborhood, setNeighborhood] = useState("");
  const { user, loading } = useAuth();
  const [phase, setPhase] = useState<"idle" | "drafting" | "publishing">("idle");
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const photoInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function rememberFile(next: File | null) {
    setFile(next);
    const input = photoInput.current;
    if (!input) return;
    if (!next) {
      input.value = "";
      return;
    }
    const transfer = new DataTransfer();
    transfer.items.add(next);
    input.files = transfer.files;
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragOver(false);
    const next = event.dataTransfer.files?.[0] ?? null;
    if (next) rememberFile(next);
  }

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

  const publishKey = useRef<string | null>(null);

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
      const floor = minimum.trim() === "" ? undefined : Number.parseInt(minimum, 10);
      const listing = await publishListing({
        category,
        title: title.trim(),
        description: description.trim(),
        price: amount,
        photos: [photoUrl],
        neighborhood: neighborhood.trim(),
        minimum: floor != null && Number.isFinite(floor) ? floor : undefined,
      }, (publishKey.current ??= crypto.randomUUID()));
      navigate(`/listings/${listing.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The listing wasn't published.");
      setPhase("idle");
    }
  }

  if (loading) {
    return (
      <div className="wrap board">
        <p>Loading…</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="wrap board sell">
        <h1>Sell from a photo</h1>
        <p>Log in first. The lister drafts the listing, and your seller bot will not go below the private minimum you set.</p>
        <Link className="button-primary" to={loginPath("/sell")}>
          Log in to sell
        </Link>
      </div>
    );
  }

  return (
    <div className="wrap board sell">
      <h1>Sell from a photo</h1>
      <div className="sell-layout">
      <form id="sell-photo-form" onSubmit={onDraft}>
        <label
          className={dragOver ? "dropzone dropzone-over" : "dropzone"}
          htmlFor="sell-photo"
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          {preview ? (
            <img className="dropzone-preview" src={preview} alt="Selected listing photo" width={800} height={600} />
          ) : (
            <span className="dropzone-copy">
              <span className="dropzone-title">Drop a photo here</span>
              <span>or choose a file. Under 2 MB.</span>
            </span>
          )}
          <input
            ref={photoInput}
            id="sell-photo"
            name="photo"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            required={!draft}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
            }}
          />
        </label>
        <button className="button-primary" type="submit" data-action="draft" disabled={phase !== "idle"}>
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
          <label htmlFor="sell-minimum">
            Private minimum in dollars
            <input
              id="sell-minimum"
              name="minimum"
              type="number"
              min={0}
              step={1}
              inputMode="numeric"
              value={minimum}
              onChange={(event) => setMinimum(event.target.value)}
            />
          </label>
          <p className="agent-note">The seller bot will not go below this. It is not shown on the listing.</p>
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
      ) : (
        <div className="sell-steps">
          <h2>How a listing gets on the board</h2>
          <ol>
            <li>Add a photo of the bike, computer, or piece of furniture.</li>
            <li>Edit the draft title, price, and neighborhood.</li>
            <li>Publish. The listing is priced and checked before it appears.</li>
          </ol>
        </div>
      )}
      </div>

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
