// The demo video and the README's language-toggle GIF, recorded from the running stack as the
// guest (nothing mocked).
//
//   make up
//   docker compose run --rm -T e2e node --input-type=module - < scripts/record-demo.mjs
//
// It writes JPEG frames and an ffmpeg concat list to frontend/.shots/video/<take>/ (git-ignored),
// for two takes: demo/ (about 75 seconds) and toggle/ (about 8 seconds). Then, from the repo root:
//
//   docker run --rm -v "$PWD/frontend/.shots/video:/v" -w /v linuxserver/ffmpeg:9.0.2-cli-ls87 \
//     -f concat -safe 0 -i demo/frames.txt -vf "fps=30,scale=in_range=full:out_range=limited,format=yuv420p" \
//     -c:v libx264 -crf 18 -preset slow -movflags +faststart demo.mp4
//   docker run --rm -v "$PWD/frontend/.shots/video:/v" -w /v linuxserver/ffmpeg:9.0.2-cli-ls87 \
//     -f concat -safe 0 -i toggle/frames.txt -vf "fps=12,scale=960:-1:flags=lanczos,split[a][b];\
//     [a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" toggle.gif
//
// Honest timing: restart ollama first (docker compose restart ollama), so nothing is in the
// model's prompt cache. The model is then warmed up with a different question, so each recorded
// question is answered at its real speed (about 34 s on a laptop CPU). Each answer's wait is
// shown at 4x speed, with a badge in the frames for exactly that stretch, and the screen's own
// "Elapsed" counter shows the real time. The refusal is real time. Captions at the bottom say
// what each step shows.
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from '@playwright/test';

const base = process.env.E2E_BASE_URL;
const root = '/app/frontend/.shots/video';
const en = JSON.parse(fs.readFileSync('/app/frontend/src/locales/en.json', 'utf8'));
const ar = JSON.parse(fs.readFileSync('/app/frontend/src/locales/ar.json', 'utf8'));

// Dev set D01, D08, D03 and D20 (eval/dev_questions.yaml): never the headline questions.
const WARM_Q = 'ما متوسط ما أنفقه برنامج الشباب مقابل كل شاب نجح فعلاً في الحصول على عمل خلال المرحلة الأولى؟';
const EN_Q =
  'While schools were shut in 2020, roughly how many girls kept up their studies by following the radio broadcasts?';
const AR_Q = 'كم من الوقت كانت تستغرق رحلة إحضار الماء في قرى الهضبة الشرقية قبل بدء مشروع المياه؟';
const REFUSE_Q = "How many weeks of paid maternity leave do the foundation's employees get?";

const W = 1280;
const H = 720;
const DPR = 1.5;
const SPEED = 4;
const BADGE = `Waiting time shown at ${SPEED}x speed`;

// A visible cursor, the speed badge and a caption, drawn in one SVG over the page. Headless
// Chromium draws no cursor, and SVG coordinates don't depend on the page direction. The styles go
// through the style object, because the app's CSP (style-src 'self') blocks inline style
// attributes.
const overlay = () => {
  const NS = 'http://www.w3.org/2000/svg';
  const install = () => {
    if (document.getElementById('demo-overlay')) return;
    const svg = document.createElementNS(NS, 'svg');
    svg.id = 'demo-overlay';
    Object.assign(svg.style, {
      position: 'fixed',
      inset: '0',
      width: '100vw',
      height: '100vh',
      pointerEvents: 'none',
      zIndex: '2147483647',
    });
    const make = (tag, attrs) => {
      const el = document.createElementNS(NS, tag);
      for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
      return el;
    };
    const saved = JSON.parse(sessionStorage.getItem('demo-cursor') || 'null') ?? [innerWidth / 2, innerHeight / 2];
    const ring = make('circle', { cx: saved[0], cy: saved[1], r: 13, fill: 'rgba(17,24,39,0.10)', stroke: 'rgba(17,24,39,0.55)', 'stroke-width': 2 });
    const dot = make('circle', { cx: saved[0], cy: saved[1], r: 4, fill: 'rgba(17,24,39,0.8)' });
    svg.append(ring, dot);
    document.documentElement.appendChild(svg);
    // A dark pill with centred text; show(null) hides it.
    const pill = (y, size) => {
      const g = make('g', { visibility: 'hidden' });
      const rect = make('rect', { y, height: size * 2.3, rx: size * 1.15, fill: 'rgba(17,24,39,0.88)' });
      const text = make('text', { y: y + size * 1.55, fill: '#fff', 'font-size': size, 'font-family': 'system-ui, sans-serif', 'text-anchor': 'middle' });
      g.append(rect, text);
      svg.insertBefore(g, ring);
      return (label) => {
        if (!label) return g.setAttribute('visibility', 'hidden');
        text.textContent = label;
        text.setAttribute('x', innerWidth / 2);
        g.setAttribute('visibility', 'visible');
        const width = text.getComputedTextLength() + size * 2.4;
        rect.setAttribute('x', innerWidth / 2 - width / 2);
        rect.setAttribute('width', width);
      };
    };
    // The caption sits in the empty middle of the header bar, and the badge just below it, so
    // neither covers an answer or its sources. In the viewer the header scrolls away, so the
    // caption goes to the bottom there.
    window.__demoBadge = pill(80, 14);
    const top = pill(15, 16);
    const bottom = pill(innerHeight - 64, 16);
    window.__demoCaption = (label, where) => {
      (where === 'bottom' ? top : bottom)(null);
      (where === 'bottom' ? bottom : top)(label);
    };
    window.addEventListener(
      'mousemove',
      (e) => {
        for (const c of [ring, dot]) {
          c.setAttribute('cx', e.clientX);
          c.setAttribute('cy', e.clientY);
        }
        sessionStorage.setItem('demo-cursor', JSON.stringify([e.clientX, e.clientY]));
      },
      true,
    );
    window.addEventListener('mousedown', () => ring.setAttribute('r', 20), true);
    window.addEventListener('mouseup', () => setTimeout(() => ring.setAttribute('r', 13), 150), true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install);
  else install();
};

const browser = await chromium.launch();
const mouse = { x: W / 2, y: H / 2 };
const newPage = async () => {
  mouse.x = W / 2;
  mouse.y = H / 2;
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: DPR });
  await ctx.addInitScript(overlay);
  return { ctx, page: await ctx.newPage() };
};

// The new question's heading first, then no progress bar and either citations or a refusal.
const refusals = [en.ask.refusal.gate, en.ask.refusal.read, ar.ask.refusal.gate, ar.ask.refusal.read];
const waitAnswer = async (page, q) => {
  await page.waitForFunction((t) => document.querySelector('h2')?.textContent?.includes(t), q, { timeout: 30_000 });
  await page.waitForFunction(
    (texts) =>
      !document.querySelector('[role="progressbar"]') &&
      (document.querySelectorAll('a[href^="/documents/"]').length > 0 ||
        texts.some((t) => document.querySelector('main')?.innerText?.includes(t))),
    refusals,
    { timeout: 240_000 },
  );
};
const caption = (page, text, where = 'top') => page.evaluate(([t, w]) => window.__demoCaption(t, w), [text, where]);
const cards = (page) => page.getByRole('link').filter({ hasText: /Page \d+|صفحة|الصفحة/ });

// Frames come from the Chrome DevTools screencast: sharper than Playwright's own video. A frame
// arrives only when the page changes, so each frame lasts until the next one.
const startTake = async (ctx, page, name) => {
  const dir = path.join(root, name);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const cdp = await ctx.newCDPSession(page);
  const frames = [];
  const fast = [];
  cdp.on('Page.screencastFrame', async ({ data, metadata, sessionId }) => {
    const file = `f${String(frames.length).padStart(5, '0')}.jpg`;
    fs.writeFileSync(path.join(dir, file), Buffer.from(data, 'base64'));
    frames.push({ file, t: metadata.timestamp ?? Date.now() / 1000 });
    await cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
  });
  // Every frame normally; every SPEED-th frame while sped up, which keeps the same frame rate in
  // the video and leaves more CPU to the model.
  const cast = async (everyNthFrame) => {
    await cdp.send('Page.stopScreencast').catch(() => {});
    await cdp.send('Page.startScreencast', {
      format: 'jpeg',
      quality: 92,
      maxWidth: W * DPR,
      maxHeight: H * DPR,
      everyNthFrame,
    });
  };
  await cast(1);
  await page.waitForTimeout(300);
  // The speed window is measured on the screencast's own clock: from the first frame that shows
  // the badge to the first frame without it.
  const lastT = () => frames.at(-1)?.t ?? 0;
  return {
    speedUp: async (work) => {
      await page.evaluate((label) => window.__demoBadge(label), BADGE);
      await page.waitForTimeout(250);
      const from = lastT();
      await cast(SPEED);
      await work();
      await cast(1);
      await page.evaluate(() => window.__demoBadge(null));
      await page.waitForTimeout(250);
      fast.push([from, lastT()]);
    },
    stop: async (hold) => {
      await cdp.send('Page.stopScreencast');
      const isFast = (t) => fast.some(([a, b]) => t >= a && t < b);
      const lines = ['ffconcat version 1.0'];
      frames.forEach((f, i) => {
        const next = frames[i + 1];
        const d = next ? (next.t - f.t) / (isFast(f.t) ? SPEED : 1) : hold;
        lines.push(`file '${f.file}'`, `duration ${d.toFixed(4)}`);
      });
      // The concat demuxer ignores the last duration unless the last file is listed again.
      lines.push(`file '${frames.at(-1).file}'`);
      fs.writeFileSync(path.join(root, name, 'frames.txt'), lines.join('\n') + '\n');
      const real = frames.at(-1).t - frames[0].t;
      const shown = real - fast.reduce((s, [a, b]) => s + (b - a) * (1 - 1 / SPEED), 0) + hold;
      console.log(`${name}: ${frames.length} frames, ${real.toFixed(1)} s recorded, ${shown.toFixed(1)} s in the video`);
      for (const [a, b] of fast) console.log(`  ${SPEED}x window: ${(b - a).toFixed(1)} s real`);
    },
  };
};

// Moves the drawn cursor in small eased steps, then clicks where it stopped.
const moveTo = async (page, loc) => {
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox();
  const x = b.x + b.width / 2;
  const y = b.y + b.height / 2;
  const n = Math.max(12, Math.round(Math.hypot(x - mouse.x, y - mouse.y) / 22));
  for (let i = 1; i <= n; i++) {
    const k = 0.5 - Math.cos((Math.PI * i) / n) / 2;
    await page.mouse.move(mouse.x + (x - mouse.x) * k, mouse.y + (y - mouse.y) * k);
    await page.waitForTimeout(14);
  }
  mouse.x = x;
  mouse.y = y;
  await page.waitForTimeout(200);
};
const click = async (page, loc) => {
  await moveTo(page, loc);
  await page.mouse.down();
  await page.waitForTimeout(90);
  await page.mouse.up();
};
const type = async (page, label, text) => {
  await click(page, page.getByRole('textbox', { name: label }));
  await page.keyboard.type(text, { delay: 32 });
  await page.waitForTimeout(400);
  await page.keyboard.press('Enter');
};
const guest = async (page) => {
  await click(page, page.getByRole('button', { name: en.auth.login.guest }));
  await page.getByRole('textbox', { name: en.ask.form.label }).waitFor();
};

// 1. Warm-up, not recorded: loads the model with a different question.
{
  const { ctx, page } = await newPage();
  await page.goto(`${base}/login?lang=en`);
  await guest(page);
  await page.getByRole('textbox', { name: en.ask.form.label }).fill(WARM_Q);
  await page.keyboard.press('Enter');
  await waitAnswer(page, WARM_Q);
  await ctx.close();
  console.log('warm-up done');
}

// 2. The demo: an English answer with its citation, the switch to Arabic, the cited page, an
// Arabic answer, a refusal, and the Library.
{
  const { ctx, page } = await newPage();
  await page.goto(`${base}/login?lang=en`);
  const take = await startTake(ctx, page, 'demo');
  await caption(page, 'Sanad answers questions from your own documents, in Arabic or English');
  await page.waitForTimeout(2500);
  await guest(page);
  await caption(page, 'A question in English');
  await page.waitForTimeout(700);
  await type(page, en.ask.form.label, EN_Q);
  await page.waitForTimeout(1500);
  await take.speedUp(() => waitAnswer(page, EN_Q));
  await caption(page, 'The answer cites its source: document and page');
  await page.waitForTimeout(4000);

  await click(page, page.getByRole('button', { name: en.language.switch }));
  await page.waitForFunction(() => document.documentElement.dir === 'rtl');
  await caption(page, 'One click mirrors the whole interface to Arabic, and the answer stays');
  await page.waitForTimeout(4000);

  await click(page, cards(page).first());
  await page.locator('[aria-current="true"][data-rendered="true"]').first().waitFor({ timeout: 60_000 });
  await caption(page, 'The citation opens the document at the cited page', 'bottom');
  await page.waitForTimeout(3500);
  // Back to the top smoothly, so the nav link doesn't make the page jump.
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
  await caption(page, null, 'bottom');
  await page.waitForTimeout(1200);

  await click(page, page.getByRole('link', { name: ar.shell.nav.ask, exact: true }));
  await caption(page, 'A question in Arabic');
  await page.waitForTimeout(800);
  await type(page, ar.ask.form.label, AR_Q);
  await page.waitForTimeout(1500);
  await take.speedUp(() => waitAnswer(page, AR_Q));
  await caption(page, 'Answered in Arabic, from two documents');
  await page.waitForTimeout(4500);

  await click(page, page.getByRole('button', { name: ar.language.switch }));
  await page.waitForFunction(() => document.documentElement.dir === 'ltr');
  await caption(page, 'A question the documents do not cover');
  await page.waitForTimeout(1000);
  await type(page, en.ask.form.label, REFUSE_Q);
  await waitAnswer(page, REFUSE_Q);
  await caption(page, 'Not in the documents, so Sanad says so instead of guessing');
  await page.waitForTimeout(4500);

  await click(page, page.getByRole('link', { name: en.shell.nav.library, exact: true }));
  await page.locator('table tbody tr').first().waitFor({ timeout: 30_000 });
  await caption(page, 'The Library, in English and Arabic');
  await page.waitForTimeout(3000);
  await click(page, page.getByRole('button', { name: en.language.switch }));
  await page.waitForFunction(() => document.documentElement.dir === 'rtl');
  await page.waitForTimeout(3000);
  await take.stop(1.0);
  await ctx.close();
}

// 3. The toggle clip: an answer on screen, to Arabic and back. The question is asked again
// before recording (from the prompt cache, not shown), so the clip starts with the answer.
{
  const { ctx, page } = await newPage();
  await page.goto(`${base}/login?lang=en`);
  await guest(page);
  await page.getByRole('textbox', { name: en.ask.form.label }).fill(EN_Q);
  await page.keyboard.press('Enter');
  await waitAnswer(page, EN_Q);
  await page.mouse.move(W - 260, 120);
  mouse.x = W - 260;
  mouse.y = 120;
  await page.waitForTimeout(500);
  const take = await startTake(ctx, page, 'toggle');
  await page.waitForTimeout(1200);
  await click(page, page.getByRole('button', { name: en.language.switch }));
  await page.waitForFunction(() => document.documentElement.dir === 'rtl');
  await page.waitForTimeout(3800);
  await click(page, page.getByRole('button', { name: ar.language.switch }));
  await page.waitForFunction(() => document.documentElement.dir === 'ltr');
  await page.waitForTimeout(2800);
  await take.stop(0.4);
  await ctx.close();
}

await browser.close();
