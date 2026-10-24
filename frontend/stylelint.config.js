// Stylelint: CSS logical properties only, so the layout mirrors when `dir` flips.
// Inline disables are ignored (ignoreDisables), so these rules cannot be switched off per file.

const physical = (what) =>
  `"${what}" is a physical direction. Use the logical equivalent ` +
  '(margin-inline-start, padding-block-end, inset-inline-end, border-start-start-radius, …).';

// Four-value shorthands set top/right/bottom/left separately, so right and left can differ.
// Use margin-block / margin-inline (and the same for padding, inset, border-*).
const FOUR_VALUES = '/^\\s*[^\\s()]+\\s+[^\\s()]+\\s+[^\\s()]+\\s+[^\\s()]+\\s*$/';
// More than one radius before an optional "/" assigns corners physically.
const MULTI_RADIUS = '/^\\s*[^\\s()/]+\\s+[^\\s()/]+/';

/** @type {import('stylelint').Config} */
export default {
  extends: ['stylelint-config-standard'],
  ignoreDisables: true,
  rules: {
    // CSS Modules class names are camelCase (styles.langSwitch).
    'selector-class-pattern': null,
    'property-disallowed-list': [
      [
        '/^(margin|padding|scroll-margin|scroll-padding)-(left|right|top|bottom)$/',
        '/^(left|right|top|bottom)$/',
        '/^border-(left|right|top|bottom)(-(width|style|color))?$/',
        '/^border-(top|bottom)-(left|right)-radius$/',
      ],
      { message: physical },
    ],
    'declaration-property-value-disallowed-list': [
      {
        '/^(text-align|text-align-last)$/': ['left', 'right'],
        '/^(float|clear)$/': ['left', 'right'],
        '/^(margin|padding|inset|scroll-margin|scroll-padding|border-width|border-style|border-color)$/':
          [FOUR_VALUES],
        'border-radius': [MULTI_RADIUS],
      },
      {
        message: (property, value) =>
          `"${property}: ${value}" is direction-dependent. Use start/end values, ` +
          '*-block / *-inline shorthands, or logical corner radii.',
      },
    ],
  },
};
