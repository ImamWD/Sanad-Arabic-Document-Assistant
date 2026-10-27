// ESLint flat config. `make lint` runs it with --max-warnings 0.
import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

import i18next from './eslint/i18next-strict.js';

// Physical-direction keys that must not appear in React inline styles (CSS logical
// properties only; stylelint covers .css files, this covers style={{ ... }}).
const PHYSICAL_STYLE_KEY =
  '/^((margin|padding|border|scrollMargin|scrollPadding)(Left|Right|Top|Bottom).*|left|right|top|bottom|border(Top|Bottom)(Left|Right)Radius)$/';

export default tseslint.config(
  {
    ignores: ['dist/', 'coverage/', 'playwright-report/', 'test-results/', 'src/api/schema.d.ts'],
  },
  {
    // No inline configuration at all: `eslint-disable…` and `/* eslint rule: off */` comments
    // have no effect (and are reported). A rule can only be changed in this file, in review.
    linterOptions: { noInlineConfig: true, reportUnusedDisableDirectives: 'error' },
  },
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    extends: [tseslint.configs.strictTypeChecked, tseslint.configs.stylisticTypeChecked],
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: { globals: globals.browser },
    plugins: {
      i18next,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['error', { allowConstantExport: true }],
      // Every user-visible string goes through t(): JSX text, literals inside JSX, and the
      // attributes a user can read or hear.
      'i18next/no-literal-string': [
        'error',
        {
          mode: 'jsx-only',
          'jsx-attributes': {
            include: [
              'alt',
              'title',
              'placeholder',
              'label',
              'aria-label',
              'aria-description',
              'aria-placeholder',
              'aria-roledescription',
              'aria-valuetext',
            ],
          },
        },
      ],
      'no-restricted-syntax': [
        'error',
        {
          selector: `JSXAttribute[name.name='style'] Property[key.name=${PHYSICAL_STYLE_KEY}]`,
          message:
            'Physical direction in an inline style. Use the logical property (marginInlineStart, insetInlineEnd, …).',
        },
        {
          selector: `JSXAttribute[name.name='style'] Property[key.name=/^(textAlign|float|clear)$/][value.value=/^(left|right)$/]`,
          message: 'Use start/end (or inline-start/inline-end), not left/right.',
        },
      ],
    },
  },
  {
    // The error helpers have one home (src/lib/api.ts). A feature never takes them from
    // another feature's folder, so a second copy can't grow back there (review RV5).
    files: ['src/features/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              // A sibling feature (../library/api), not shared code (../../lib/api).
              group: ['../*/*', '!../../**'],
              importNames: ['errorFromResponse', 'parseJson', 'isRecord', 'ApiError'],
              message: 'Import the error helpers from src/lib/api.ts, not from another feature.',
            },
          ],
        },
      ],
    },
  },
  {
    files: ['src/**/*.test.{ts,tsx}', 'e2e/**/*.ts'],
    rules: { 'i18next/no-literal-string': 'off' },
  },
  {
    files: ['*.{js,ts}', 'e2e/**/*.ts'],
    languageOptions: { globals: globals.node },
  },
  prettier,
);
