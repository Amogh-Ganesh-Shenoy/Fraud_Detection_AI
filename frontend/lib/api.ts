// lib/api.ts
// Centralised API client for all FastAPI calls from React components.
// Every endpoint has its own typed function — components never call fetch() directly.
// JWT token is attached automatically in the Authorization header on every request.
// On 401 responses, the user is redirected to the login page.

import {
  LoginResponse,
  ScoreRequest,
  ScoreResponse,
  UserSummary,
  UserProfile,
  AlertSummary,
  MetricsResponse,
  SessionResponse,
} from "@/types";

// API base URL — reads from environment variable in production (Vercel)
// Falls back to localhost:8000 for local development if variable is not set
// NEXT_PUBLIC_ prefix is required for Next.js to expose the variable to the browser
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";


// ══════════════════════════════════════════════════════════════════════════════
// TOKEN HELPERS
// Centralised token storage and retrieval — no component touches localStorage directly
// ══════════════════════════════════════════════════════════════════════════════

// Saves the JWT token to localStorage after successful login
export function saveToken(token: string): void {
  localStorage.setItem("auth_token", token);
}

// Retrieves the JWT token — returns null if not logged in
export function getToken(): string | null {
  return localStorage.getItem("auth_token");
}

// Removes the JWT token and redirects to login — called on logout or 401
export function clearToken(): void {
  localStorage.removeItem("auth_token");
  window.location.href = "/";
}


// ══════════════════════════════════════════════════════════════════════════════
// CORE FETCH WRAPPER
// Attaches JWT token header and handles 401 automatically
// ══════════════════════════════════════════════════════════════════════════════

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  /**
   * Wraps fetch() with:
   *   1. Authorization header — attaches JWT token on every request
   *   2. Content-Type header — tells FastAPI to expect JSON
   *   3. 401 handling — clears token and redirects to login if token expired
   *   4. Generic typing — caller specifies expected return type T
   *
   * All API functions below call apiFetch() instead of fetch() directly
   * so token logic never needs to be repeated in any component.
   */
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  // Attach JWT token if present — FastAPI verify_token() in dependencies.py reads this
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // Token expired or invalid — log the user out and redirect to login
  if (response.status === 401) {
    clearToken();
    throw new Error("Session expired. Please log in again.");
  }

  // Any other non-2xx response — extract error detail from FastAPI response
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  // Parse and return the JSON response typed as T
  return response.json() as Promise<T>;
}


// ══════════════════════════════════════════════════════════════════════════════
// POST /login
// ══════════════════════════════════════════════════════════════════════════════

export async function login(
  username: string,
  password: string
): Promise<LoginResponse> {
  /**
   * Authenticates the user and returns a JWT token.
   * FastAPI expects credentials as form data (not JSON) for OAuth2PasswordBearer.
   * Calls POST /login in api/main.py.
   * On success, caller should save the token using saveToken().
   */

  // OAuth2PasswordBearer requires form-encoded body — not JSON
  const formData = new URLSearchParams();
  formData.append("username", username);
  formData.append("password", password);

  const response = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString(),
  });

  if (!response.ok) {
    throw new Error("Invalid username or password.");
  }

  return response.json() as Promise<LoginResponse>;
}


// ══════════════════════════════════════════════════════════════════════════════
// GET /users
// ══════════════════════════════════════════════════════════════════════════════

export async function getUsers(): Promise<UserSummary[]> {
  /**
   * Fetches all users for the dropdown selector in ScoreForm.tsx.
   * Pulls user_id, full_name, city from users table via api/main.py.
   * Protected — JWT token required.
   */
  return apiFetch<UserSummary[]>("/users");
}


// ══════════════════════════════════════════════════════════════════════════════
// GET /users/{user_id}/profile
// ══════════════════════════════════════════════════════════════════════════════

export async function getUserProfile(userId: string): Promise<UserProfile> {
  /**
   * Fetches the behavioral baseline for a single user.
   * Displayed in ProfileCard.tsx — avg spend, usual location, typical device.
   * Pulls from behavior_profiles table via api/main.py.
   * Protected — JWT token required.
   */
  return apiFetch<UserProfile>(`/users/${userId}/profile`);
}


// ══════════════════════════════════════════════════════════════════════════════
// GET /alerts
// ══════════════════════════════════════════════════════════════════════════════

export async function getAlerts(limit: number = 10): Promise<AlertSummary[]> {
  /**
   * Fetches recent alert history for AlertTable.tsx.
   * JOINs alerts + transactions in api/main.py.
   * limit param controls how many rows are returned (default 10).
   * Protected — JWT token required.
   */
  return apiFetch<AlertSummary[]>(`/alerts?limit=${limit}`);
}


// ══════════════════════════════════════════════════════════════════════════════
// GET /metrics
// ══════════════════════════════════════════════════════════════════════════════

export async function getMetrics(): Promise<MetricsResponse> {
  /**
   * Fetches static model evaluation metrics for MetricsPanel.tsx and FeatureBar.tsx.
   * Returns Phase 5, Z-Score, Random Forest, and Ensemble results
   * plus feature importances from phase6/random_forest_model.py.
   * Protected — JWT token required.
   */
  return apiFetch<MetricsResponse>("/metrics");
}


// ══════════════════════════════════════════════════════════════════════════════
// POST /score — Full Ensemble Scoring
// ══════════════════════════════════════════════════════════════════════════════

export async function scoreTransaction(
  payload: ScoreRequest
): Promise<ScoreResponse> {
  /**
   * Submits a transaction for full ensemble scoring.
   * Calls POST /score in api/main.py which:
   *   1. Calls phase2/ingest.py → ingest_session() and ingest_transaction()
   *   2. Calls phase6/ensemble.py → ensemble_score()
   *   3. Returns combined result from all 3 models
   * Result displayed in ResultCard.tsx and GaugeChart.tsx.
   * Protected — JWT token required.
   */
  return apiFetch<ScoreResponse>("/score", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}