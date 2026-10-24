// Build-time settings Vite exposes to the bundle (documented in .env.example).
interface ImportMetaEnv {
  /** Digits in the Arabic UI: `arab` (Arabic-Indic, default) or `latn`. */
  readonly VITE_AR_NUMBERING?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
