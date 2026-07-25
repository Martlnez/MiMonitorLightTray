/* Mi Monitor Light Tray — GitHub Pages 交互脚本 */

const REPO = 'Martlnez/MiMonitorLightTray';
const API_LATEST = `https://api.github.com/repos/${REPO}/releases/latest`;
const RELEASES_URL = `https://github.com/${REPO}/releases/latest`;

/** 从 GitHub API 拉取最新 Release，把下载按钮更新为直链 EXE */
async function fetchLatestRelease() {
    const downloadBtn = document.querySelector('[data-download]');
    const versionLabel = document.querySelector('[data-version]');
    if (!downloadBtn && !versionLabel) return;

    try {
        const res = await fetch(API_LATEST, {
            headers: { 'Accept': 'application/vnd.github.v3+json' }
        });
        if (!res.ok) throw new Error(`API ${res.status}`);
        const data = await res.json();

        const exe = (data.assets || []).find(a => a.name.endsWith('.exe'));
        if (downloadBtn && exe) {
            downloadBtn.href = exe.browser_download_url;
            downloadBtn.dataset.size = formatBytes(exe.size);
            const sizeLabel = downloadBtn.querySelector('.btn-size');
            if (sizeLabel) sizeLabel.textContent = ` · ${formatBytes(exe.size)}`;
        }
        if (versionLabel && data.tag_name) {
            versionLabel.textContent = data.tag_name;
        }
    } catch (err) {
        console.warn('无法拉取最新 Release，使用回退链接', err);
        if (downloadBtn) downloadBtn.href = RELEASES_URL;
    }
}

function formatBytes(bytes) {
    if (!bytes) return '';
    const mb = bytes / 1024 / 1024;
    return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
}

/** 文档页：滚动时高亮当前章节 TOC */
function initTocScrollSpy() {
    const tocLinks = document.querySelectorAll('.doc-toc a[href^="#"]');
    if (!tocLinks.length) return;

    const targets = Array.from(tocLinks)
        .map(a => document.getElementById(a.getAttribute('href').slice(1)))
        .filter(Boolean);
    if (!targets.length) return;

    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            const id = entry.target.id;
            tocLinks.forEach(a => {
                a.classList.toggle('active', a.getAttribute('href') === `#${id}`);
            });
        });
    }, { rootMargin: '-80px 0px -70% 0px', threshold: 0 });

    targets.forEach(t => observer.observe(t));
}

/** 顶部导航高亮当前页 */
function highlightCurrentNav() {
    const path = location.pathname.split('/').pop() || 'index.html';
    document.querySelectorAll('.nav-links a').forEach(a => {
        const href = a.getAttribute('href');
        if (href === path || (path === '' && href === 'index.html')) {
            a.classList.add('active');
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    fetchLatestRelease();
    initTocScrollSpy();
    highlightCurrentNav();
});
