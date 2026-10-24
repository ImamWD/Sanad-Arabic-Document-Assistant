// ESLint flat config. `make lint` runs it with --max-warnings 0.
import comments from '@eslint-community/eslint-plugin-eslint-comments/configs';
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
    linterOptions: { reportUnusedDisableDirectives: 'error' },
  },
  js.configs.recommended,
  comments.recommended,
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
      // The i18n rule may not be switched off with an inline comment.
      '@eslint-community/eslint-comments/no-restricted-disable': [
        'error',
        'i18next/no-literal-string',
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
    files: ['src/**/*.test.{ts,tsx}', 'e2e/**/*.ts'],
    rules: { 'i18next/no-literal-string': 'off' },
  },
  {
    files: ['*.{js,ts}', 'e2e/**/*.ts'],
    languageOptions: { globals: globals.node },
  },
  prettier,
);
