const puppeteer = require('../ui/node_modules/puppeteer-core');
const path = require('path');
const fs = require('fs');

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  const screenshotsDir = path.join(__dirname, '..', 'docs', 'screenshots');
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  console.log('Launching Chrome...');
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: 'new',
    defaultViewport: {
      width: 1728,
      height: 1080,
      deviceScaleFactor: 2,
    },
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
  });

  const page = await browser.newPage();
  console.log('Navigating to http://127.0.0.1:8501 ...');
  await page.goto('http://127.0.0.1:8501', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  // Switch to Keepers catalog explicitly via select dropdown if not already Keepers
  console.log('Switching to Keepers catalog...');
  await page.evaluate(() => {
    const selects = Array.from(document.querySelectorAll('select'));
    for (const s of selects) {
      for (const opt of s.options) {
        if (opt.value === 'Keepers') {
          s.value = 'Keepers';
          s.dispatchEvent(new Event('change', { bubbles: true }));
          break;
        }
      }
    }
  });
  await sleep(2500);

  // Verify that active catalog text or photos contain ONLY Keepers
  const verifyData = await page.evaluate(() => {
    const bodyText = document.body.innerText;
    return {
      hasKeepersText: bodyText.includes('Keepers') || bodyText.includes('866'),
      hasAustinInView: bodyText.includes('Austin 2024'),
    };
  });
  console.log('Verification data:', verifyData);

  // 1. Studio Grid Workspace Screenshot
  console.log('Capturing 01-studio-grid-workspace.png ...');
  await page.screenshot({
    path: path.join(screenshotsDir, '01-studio-grid-workspace.png'),
  });

  // 2. Open Lightbox on first photo
  console.log('Opening Lightbox Inspector...');
  const photoCard = await page.$('div[role="button"], [data-photo-id], img[alt]');
  if (photoCard) {
    await photoCard.click();
    await sleep(2000);
  } else {
    // Fallback: click first image
    await page.evaluate(() => {
      const img = document.querySelector('img');
      if (img) img.click();
    });
    await sleep(2000);
  }

  console.log('Capturing 02-lightbox-inspector.png ...');
  await page.screenshot({
    path: path.join(screenshotsDir, '02-lightbox-inspector.png'),
  });

  // Close Lightbox
  await page.keyboard.press('Escape');
  await sleep(1000);

  // 3. Open Voice Teach & Scout Modal
  console.log('Opening Scout Archive / Voice Modal...');
  await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    const scoutBtn = buttons.find((b) => b.innerText.includes('Scout Archive'));
    if (scoutBtn) scoutBtn.click();
  });
  await sleep(1800);

  console.log('Capturing 03-voice-teach-scout.png ...');
  await page.screenshot({
    path: path.join(screenshotsDir, '03-voice-teach-scout.png'),
  });

  // Close Voice Modal
  await page.keyboard.press('Escape');
  await sleep(1000);

  // 4. Open Unified Import Modal
  console.log('Opening Unified Import Modal...');
  await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    const importBtn = buttons.find((b) => b.innerText.includes('Import & AI Tag'));
    if (importBtn) importBtn.click();
  });
  await sleep(1800);

  console.log('Capturing 04-unified-import-modal.png ...');
  await page.screenshot({
    path: path.join(screenshotsDir, '04-unified-import-modal.png'),
  });

  await browser.close();
  console.log('All 4 screenshots captured successfully!');
}

main().catch((err) => {
  console.error('Error capturing screenshots:', err);
  process.exit(1);
});
