import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { PersistGate } from "redux-persist/integration/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { store, persistor } from "@/store/store";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient();
const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

const app = (
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provider store={store}>
      <PersistGate loading={null} persistor={persistor}>
        {googleClientId ? (
          <GoogleOAuthProvider clientId={googleClientId}>{app}</GoogleOAuthProvider>
        ) : (
          app
        )}
      </PersistGate>
    </Provider>
  </StrictMode>
);
