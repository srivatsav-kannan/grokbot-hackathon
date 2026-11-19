const TOKEN_PREFIX = "fairlot.token.";
const TEXT_PREFIX = "fairlot.wantText.";
const ACTIVE = "fairlot.activeWantId";

function read(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    /* Private browsing can block storage. The want still exists on the server. */
  }
}

export function saveWant(id: string, token: string, text: string): void {
  write(TOKEN_PREFIX + id, token);
  write(TEXT_PREFIX + id, text);
  write(ACTIVE, id);
}

export function tokenFor(id: string): string | null {
  return read(TOKEN_PREFIX + id);
}

export function textFor(id: string): string | null {
  return read(TEXT_PREFIX + id);
}

export function activeWant(): { id: string; token: string; text: string } | null {
  const id = read(ACTIVE);
  if (!id) return null;
  const token = read(TOKEN_PREFIX + id);
  if (!token) return null;
  return { id, token, text: read(TEXT_PREFIX + id) ?? "" };
}
