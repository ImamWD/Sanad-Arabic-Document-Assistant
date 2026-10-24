// eslint-plugin-i18next, minus one exemption.
//
// Upstream `no-literal-string` skips everything under a variable whose name matches
// /^[A-Z_-]+$/ (meant for `const API_URL = '…'`). Single-letter component names match too,
// so `export const P = () => <p>Hello</p>` passed lint. We hand the upstream
// VariableDeclarator handler a lower-case name so that scope is checked like any other.
// Outside JSX the rule (mode jsx-only) ignores literals anyway, so this only makes it stricter.
// scripts/check-lint-gates.sh proves the rule still fires.
import upstream from 'eslint-plugin-i18next';

const base = upstream.rules['no-literal-string'];

const noLiteralString = {
  ...base,
  create(context) {
    const visitor = base.create(context);
    const enter = visitor.VariableDeclarator;
    if (typeof enter !== 'function') {
      throw new Error('eslint-plugin-i18next changed: VariableDeclarator handler not found');
    }
    return {
      ...visitor,
      VariableDeclarator(node) {
        enter({ ...node, id: { ...node.id, name: 'checked' } });
      },
    };
  },
};

export default {
  ...upstream,
  rules: { ...upstream.rules, 'no-literal-string': noLiteralString },
};
