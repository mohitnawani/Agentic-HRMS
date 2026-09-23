import { createAsyncThunk, createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { login as loginApi, googleLogin as googleLoginApi } from "@/features/auth/authApi";

export type Role = "admin" | "hr" | "employee";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  role: Role | null;
  email: string | null;
  status: "idle" | "loading" | "succeeded" | "failed";
  error: string | null;
}

const initialState: AuthState = {
  accessToken: null,
  refreshToken: null,
  role: null,
  email: null,
  status: "idle",
  error: null,
};

export const loginThunk = createAsyncThunk(
  "auth/login",
  async (
    credentials: { email: string; password: string },
    { rejectWithValue }
  ) => {
    try {
      return await loginApi(credentials.email, credentials.password);
    } catch {
      return rejectWithValue("Invalid email or password");
    }
  }
);

export const googleLoginThunk = createAsyncThunk(
  "auth/googleLogin",
  async (
    credential: { idToken: string; email: string },
    { rejectWithValue }
  ) => {
    try {
      return await googleLoginApi(credential.idToken, credential.email);
    } catch {
      return rejectWithValue("Google sign-in failed — is this email registered with HR?");
    }
  }
);

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setAuth: (
      state,
      action: PayloadAction<{ accessToken: string; refreshToken: string; role: Role; email: string }>
    ) => {
      state.accessToken = action.payload.accessToken;
      state.refreshToken = action.payload.refreshToken;
      state.role = action.payload.role;
      state.email = action.payload.email;
    },
    setAccessToken: (state, action: PayloadAction<string>) => {
      state.accessToken = action.payload;
    },
    logout: (state) => {
      state.accessToken = null;
      state.refreshToken = null;
      state.role = null;
      state.email = null;
      state.status = "idle";
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loginThunk.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(loginThunk.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.accessToken = action.payload.accessToken;
        state.refreshToken = action.payload.refreshToken;
        state.role = action.payload.role;
        state.email = action.payload.email;
      })
      .addCase(loginThunk.rejected, (state, action) => {
        state.status = "failed";
        state.error = (action.payload as string | undefined) ?? "Login failed";
      })
      .addCase(googleLoginThunk.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(googleLoginThunk.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.accessToken = action.payload.accessToken;
        state.refreshToken = action.payload.refreshToken;
        state.role = action.payload.role;
        state.email = action.payload.email;
      })
      .addCase(googleLoginThunk.rejected, (state, action) => {
        state.status = "failed";
        state.error = (action.payload as string | undefined) ?? "Google sign-in failed";
      });
  },
});

export const { setAuth, setAccessToken, logout } = authSlice.actions;
export default authSlice.reducer;
