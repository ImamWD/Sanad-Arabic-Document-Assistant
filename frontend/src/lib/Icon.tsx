import { cx } from './cx';
import styles from './Icon.module.css';

interface IconDef {
  paths: readonly string[];
  /** Points along the reading direction (arrows, "sign out"), so it mirrors in RTL. */
  directional?: boolean;
}

// 24×24 stroke icons, inlined: no icon font, no CDN.
const ICONS = {
  ask: { paths: ['M4 5h16v11H9l-5 4z', 'M8 9h8', 'M8 12h5'] },
  library: {
    paths: [
      'M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4z',
      'M20 4h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6z',
    ],
  },
  upload: { paths: ['M12 16V4', 'M7 9l5-5 5 5', 'M4 20h16'] },
  admin: { paths: ['M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z', 'M9 12l2 2 4-4'] },
  user: { paths: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M4 21a8 8 0 0 1 16 0'] },
  chevronDown: { paths: ['M6 9l6 6 6-6'] },
  globe: {
    paths: [
      'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z',
      'M3 12h18',
      'M12 3a14 14 0 0 1 0 18',
      'M12 3a14 14 0 0 0 0 18',
    ],
  },
  signOut: { paths: ['M10 4H5v16h5', 'M15 8l4 4-4 4', 'M19 12H9'], directional: true },
  forward: { paths: ['M5 12h14', 'M13 6l6 6-6 6'], directional: true },
} satisfies Record<string, IconDef>;

export type IconName = keyof typeof ICONS;

/** Decorative icon (hidden from assistive tech); the control next to it carries the label. */
export function Icon({ name }: { name: IconName }) {
  const icon: IconDef = ICONS[name];
  return (
    <svg
      className={cx(styles.icon, icon.directional && styles.mirror)}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      data-icon={name}
    >
      {icon.paths.map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
