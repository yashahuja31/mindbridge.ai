/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Override the API base URL for production builds (dev uses the Vite proxy at `/api`). */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
