import { useState } from "react";

export function isPlaceholderSrc(src: string): boolean {
  return src.includes("/placeholders/");
}

export function PhotoFrame({
  src,
  alt,
  label,
  eager = false,
}: {
  src: string;
  alt: string;
  label: string;
  eager?: boolean;
}) {
  const [broken, setBroken] = useState(false);
  const pending = !src || broken || isPlaceholderSrc(src);

  return (
    <span className={pending ? "photo-frame photo-frame-pending" : "photo-frame"}>
      {src && !broken ? (
        <img
          src={src}
          alt={alt}
          width={800}
          height={600}
          decoding="async"
          loading={eager ? "eager" : "lazy"}
          onError={() => setBroken(true)}
        />
      ) : (
        <span className="photo-fallback">{label}</span>
      )}
      {pending ? <span className="photo-note">Photo coming</span> : null}
    </span>
  );
}
