#!/bin/sh
# Self-test for the lint gates: each probe must make the linter fail, *for the right rule*.
# Run by `make lint`, so weakening eslint.config.js or stylelint.config.js breaks the build.
set -u
dir=src/__lint_gate_probe__
mkdir -p "$dir"
trap 'rm -rf "$dir"' EXIT INT TERM
status=0

# expect_fail <linter> <file> <rule-id> <minimum count>
expect_fail() {
  linter=$1 file=$2 rule=$3 want=$4
  if [ "$linter" = eslint ]; then out=$(npx eslint --no-warn-ignored "$file" 2>&1); else out=$(npx stylelint "$file" 2>&1); fi
  code=$?
  got=$(printf '%s\n' "$out" | grep -c -- "$rule" || true)
  if [ "$code" -eq 0 ] || [ "$got" -lt "$want" ]; then
    echo "LINT GATE BROKEN: $file expected >= $want x $rule (exit=$code, hits=$got)"
    printf '%s\n' "$out"
    status=1
  else
    echo "ok   $rule catches $file ($got)"
  fi
}

# --- ESLint: literal UI strings -------------------------------------------------------------
printf 'export const P = () => <p>Hello</p>;\n' > "$dir/jsx-text.tsx"
expect_fail eslint "$dir/jsx-text.tsx" i18next/no-literal-string 1

cat > "$dir/jsx-attrs.tsx" <<'TSX'
export const Img = () => <img src="/logo.png" alt="Logo" />;
export const Field = () => <input placeholder="Search" aria-label="Search" title="Find" />;
export const Choice = ({ ok }: { ok: boolean }) => <span>{ok ? 'Yes' : 'No'}</span>;
TSX
expect_fail eslint "$dir/jsx-attrs.tsx" i18next/no-literal-string 6

# --- ESLint: inline configuration has no effect (linterOptions.noInlineConfig) ------------------
cat > "$dir/inline-disable.tsx" <<'TSX'
// eslint-disable-next-line i18next/no-literal-string
export const Hidden = () => <b>Hidden</b>;
TSX
expect_fail eslint "$dir/inline-disable.tsx" i18next/no-literal-string 1

cat > "$dir/inline-rule-off.tsx" <<'TSX'
/* eslint i18next/no-literal-string: "off" */
export const Off = () => <b>Switched off</b>;
TSX
expect_fail eslint "$dir/inline-rule-off.tsx" i18next/no-literal-string 1

cat > "$dir/file-disable.tsx" <<'TSX'
/* eslint-disable */
export const All = () => <b>Everything off</b>;
TSX
expect_fail eslint "$dir/file-disable.tsx" i18next/no-literal-string 1

# --- ESLint: physical directions in React inline styles ----------------------------------------
printf 'export const S = () => <div style={{ marginLeft: 4 }} />;\n' > "$dir/inline-style.tsx"
expect_fail eslint "$dir/inline-style.tsx" no-restricted-syntax 1

cat > "$dir/inline-style-disabled.tsx" <<'TSX'
// eslint-disable-next-line no-restricted-syntax
export const S = () => <div style={{ paddingRight: 4 }} />;
TSX
expect_fail eslint "$dir/inline-style-disabled.tsx" no-restricted-syntax 1

# --- stylelint: physical properties and values -------------------------------------------------
printf '.x{margin-left:4px}\n' > "$dir/margin.module.css"
expect_fail stylelint "$dir/margin.module.css" property-disallowed-list 1

cat > "$dir/physical.module.css" <<'CSS'
/* stylelint-disable */
.a { padding-right: 1px; }
.b { left: 0; }
.c { border-left: 1px solid; }
.d { border-top-right-radius: 2px; }
.e { text-align: left; }
.f { float: right; }
CSS
expect_fail stylelint "$dir/physical.module.css" property-disallowed-list 4
expect_fail stylelint "$dir/physical.module.css" declaration-property-value-disallowed-list 2

# --- stylelint: physical shorthands, including var() and calc() values -------------------------
cat > "$dir/shorthand.module.css" <<'CSS'
/* stylelint-disable sanad/no-physical-shorthand */
.g { margin: 1px 2px 3px 4px; }
.h { border-radius: 4px 0; }
.i { padding: 0 var(--s4) 0 0; }
.j { border-radius: var(--r2) 0; }
.k { margin: calc(1px + 2px) 0 0; }
.l { inset: 0 var(--gap) 0 var(--gap); }
CSS
expect_fail stylelint "$dir/shorthand.module.css" sanad/no-physical-shorthand 6

exit $status
