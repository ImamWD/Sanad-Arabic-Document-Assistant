// Stylelint: CSS logical properties only, so the layout mirrors when `dir` flips.
// Inline disables are ignored (ignoreDisables), so these rules cannot be switched off per file.
import physicalShorthand from './stylelint/physical-shorthand.js';

const physical = (what) =>
  `"${what}" is a physical direction. Use the logical equivalent ` +
  '(margin-inline-start, padding-block-end, inset-inline-end, border-start-start-radius, …).';

/** @type {import('stylelint').Config} */
export default {
  extends: ['stylelint-config-standard'],
  plugins: [physicalShorthand],
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
      },
      {
        message: (property, value) =>
          `"${property}: ${value}" is direction-dependent. Use start/end (or inline-start/end).`,
      },
    ],
    // More than 2 values in margin/padding/inset/border-* shorthands, or more than one
    // border-radius value, sets physical sides. Counts top-level values, so var()/calc() count.
    'sanad/no-physical-shorthand': true,
  },
};
