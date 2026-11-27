/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SE_API_URL: string;
  readonly VITE_ALLOWED_HOSTS?: string;
  readonly VITE_MAIN_APP_URL?: string;
  readonly VITE_PORT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
