import { useEffect } from "react";

export function useTitle(title: string) {
  useEffect(() => {
    document.title = title === "Fairlot" ? "Fairlot" : `${title} · Fairlot`;
  }, [title]);
}
