// sanad/no-physical-shorthand: box shorthands may not set physical sides.
//
// `margin: a b c d` sets top/right/bottom/left separately, and `border-radius: a b` assigns
// corners physically, so neither mirrors when `dir` flips. We count *top-level* values with
// postcss-value-parser, so var(), calc() and other functions count as one value each
// (a regex over the raw text skipped any value containing a function).
//   box shorthands: at most 2 values (block, inline); use *-block / *-inline instead
//   border-radius:  1 value on each side of "/"; use the logical corner properties instead
import valueParser from 'postcss-value-parser';
import stylelint from 'stylelint';

const {
  createPlugin,
  utils: { report, ruleMessages, validateOptions },
} = stylelint;

const ruleName = 'sanad/no-physical-shorthand';

const messages = ruleMessages(ruleName, {
  box: (prop, count) =>
    `"${prop}" with ${count} values sets physical sides. Use ${prop}-block / ${prop}-inline ` +
    '(or at most 2 values).',
  radius: () =>
    '"border-radius" with several values assigns physical corners. Use one value or ' +
    'border-start-start-radius, border-start-end-radius, …',
});

const BOX_SHORTHAND =
  /^(margin|padding|inset|scroll-margin|scroll-padding|border-width|border-style|border-color)$/i;

/** Number of top-level values in each "/"-separated group of a declaration value. */
function topLevelCounts(value) {
  const counts = [0];
  for (const node of valueParser(value).nodes) {
    if (node.type === 'div' && node.value === '/') counts.push(0);
    else if (node.type !== 'space' && node.type !== 'comment' && node.type !== 'div') {
      counts[counts.length - 1] += 1;
    }
  }
  return counts;
}

const rule = (primary) => (root, result) => {
  if (!validateOptions(result, ruleName, { actual: primary, possible: [true] })) return;

  root.walkDecls((decl) => {
    const prop = decl.prop.toLowerCase();
    if (BOX_SHORTHAND.test(prop)) {
      const [count = 0] = topLevelCounts(decl.value);
      if (count > 2) {
        report({
          ruleName,
          result,
          node: decl,
          message: messages.box(prop, count),
          word: decl.prop,
        });
      }
    } else if (prop === 'border-radius' && topLevelCounts(decl.value).some((c) => c > 1)) {
      report({ ruleName, result, node: decl, message: messages.radius(), word: decl.prop });
    }
  });
};

rule.ruleName = ruleName;
rule.messages = messages;

export default createPlugin(ruleName, rule);
