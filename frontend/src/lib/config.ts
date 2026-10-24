// Build-time UI settings (Vite exposes VITE_* variables to the bundle). Read them here only,
// so components and tests never touch import.meta.env directly.
import { parseArabicNumbering } from './format';

/** VITE_AR_NUMBERING=arab|latn (default arab): digits in the Arabic UI. */
export const AR_NUMBERING = parseArabicNumbering(import.meta.env.VITE_AR_NUMBERING);
