export type Company = {
  id: number;
  name: string;
  industry: string | null;
  size: string | null;
  use_case: string | null;
  logo_url: string | null;
};

export type User = {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  company: Company | null;
};

export function saveToken(token: string) {
  localStorage.setItem("chimera_token", token);
}

export function saveUser(user: User) {
  localStorage.setItem("chimera_user", JSON.stringify(user));
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("chimera_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("chimera_token");
}

export function logout() {
  localStorage.removeItem("chimera_token");
  localStorage.removeItem("chimera_user");
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}
