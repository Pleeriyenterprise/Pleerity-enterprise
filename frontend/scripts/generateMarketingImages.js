/**
 * Generate marketing-ready cropped images from raw full-page screenshots.
 * Run: node scripts/generateMarketingImages.js (or npm run generate-marketing-images)
 *
 * Prerequisites: Place raw screenshots in public/images/raw/ with names:
 *   - hero-command-centre.png (or hero-command-centre-raw.png)
 *   - feature-expiry-list.png (or feature-expiry-list-raw.png)
 *   - support-calendar.png (or support-calendar-raw.png)
 *
 * Output: Cropped files in public/images/marketing/
 * Crop coordinates are configurable below; adjust per screenshot if needed.
 */

const path = require('path');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '..');
const RAW_DIR = path.join(ROOT, 'public', 'images', 'raw');
const OUT_DIR = path.join(ROOT, 'public', 'images', 'marketing');

const CROP_SPECS = [
  {
    outputName: 'hero-command-centre.png',
    inputNames: ['hero-command-centre.png', 'hero-command-centre-raw.png'],
    targetWidth: 1200,
    targetHeight: 850,
    trimTop: 120,
    trimBottom: 100,
    description: 'Dashboard: Compliance Score + Quick Actions (remove nav + footer)',
  },
  {
    outputName: 'feature-expiry-list.png',
    inputNames: ['feature-expiry-list.png', 'feature-expiry-list-raw.png'],
    targetWidth: 1200,
    targetHeight: 800,
    trimTop: 120,
    trimBottom: 80,
    description: 'Upcoming Expiries list (3–5 rows visible)',
  },
  {
    outputName: 'support-calendar.png',
    inputNames: ['support-calendar.png', 'support-calendar-raw.png', 'support-calender.png', 'support-calender-raw.png'],
    targetWidth: 1200,
    targetHeight: 800,
    trimTop: 120,
    trimBottom: 80,
    description: 'Calendar month header + events',
  },
];

async function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

async function findInputPath(spec) {
  for (const name of spec.inputNames) {
    const p = path.join(RAW_DIR, name);
    if (fs.existsSync(p)) return p;
  }
  return null;
}

async function run() {
  const sharp = require('sharp');
  await ensureDir(RAW_DIR);
  await ensureDir(OUT_DIR);

  const generated = [];
  for (const spec of CROP_SPECS) {
    const inputPath = await findInputPath(spec);
    if (!inputPath) {
      console.warn(`[generateMarketingImages] Skip ${spec.outputName}: no raw file found in ${RAW_DIR} (tried: ${spec.inputNames.join(', ')})`);
      continue;
    }

    const meta = await sharp(inputPath).metadata();
    const w = meta.width || 0;
    const h = meta.height || 0;
    if (w === 0 || h === 0) {
      console.warn(`[generateMarketingImages] Skip ${spec.outputName}: invalid dimensions`);
      continue;
    }

    const top = Math.min(spec.trimTop || 0, h - 1);
    const bottom = Math.min(spec.trimBottom || 0, h - top);
    const left = 0;
    const width = w;
    const height = Math.max(100, h - top - bottom);

    const outPath = path.join(OUT_DIR, spec.outputName);
    await sharp(inputPath)
      .extract({ left, top, width, height })
      .resize(spec.targetWidth, spec.targetHeight, { fit: 'cover' })
      .png()
      .toFile(outPath);

    const relativeOut = path.relative(ROOT, outPath);
    generated.push(relativeOut);
    console.log(`[generateMarketingImages] Generated ${relativeOut} (crop: top=${top}, bottom=${bottom}, resize ${spec.targetWidth}x${spec.targetHeight})`);
  }

  if (generated.length > 0) {
    console.log('[generateMarketingImages] Done. Files created:', generated.join(', '));
  } else {
    console.log('[generateMarketingImages] No files generated. Add raw screenshots to public/images/raw/ and re-run.');
  }
}

run().catch((err) => {
  console.error('[generateMarketingImages] Error:', err);
  process.exit(1);
});
