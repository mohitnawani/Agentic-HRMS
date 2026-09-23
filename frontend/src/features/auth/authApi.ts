import { apiClient } from "@/lib/api-client";
import type { Role } from "@/store/authSlice";

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export async function login(email: string, password: string) {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);

  const { data } = await apiClient.post<LoginResponse>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });

  const payload = JSON.parse(atob(data.access_token.split(".")[1]));
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    role: payload.role as Role,
    email,
  };
}

export async function googleLogin(idToken: string, emailHint: string) {
  const { data } = await apiClient.post<LoginResponse>("/auth/google", { id_token: idToken });

  const payload = JSON.parse(atob(data.access_token.split(".")[1]));
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    role: payload.role as Role,
    email: emailHint,
  };
}
