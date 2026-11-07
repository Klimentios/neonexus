// Keep the composer under the conversation, beside the persistent side rails.
document.addEventListener('DOMContentLoaded', () => {
    const area = document.getElementById('content-area');
    const timeline = document.getElementById('timeline');
    const footer = document.querySelector('#app > footer');
    if (!area || !timeline || !footer) return;
    const center = document.createElement('div');
    center.id = 'center-workspace';
    timeline.before(center);
    center.append(timeline, footer);
});

// Tasks and rules live in the right rail. Return to the conversation before
// opening either panel from a full-width workspace.
document.addEventListener('click', (event) => {
    const route = event.target.closest?.('#nx-sidenav [data-nx-rail]');
    if (!route || document.body.dataset.nxView === 'chat') return;
    window.neonexusShell?.setView('chat');
}, true);

// The connection catalogue can be long. Keep its existing forms and buttons,
// but reveal one category at a time instead of showing every provider at once.
document.addEventListener('DOMContentLoaded', () => {
    const center = document.getElementById('center-workspace');
    if (!center) return;
    const states = new Map();
    const attach = () => {
        const box = document.getElementById('nx-connect');
        if (!box) return false;
        const enhance = () => {
            const sections = [...box.querySelectorAll(':scope > section.nx-csec')];
            sections.forEach((section, index) => {
                const header = section.querySelector(':scope > header');
                const grid = section.querySelector(':scope > .nx-cgrid');
                if (!header || !grid) return;
                const label = header.querySelector('h3')?.textContent || '';
                const group = document.createElement('details');
                group.className = 'nx-connect-group';
                group.open = states.has(label) ? states.get(label) : index === 0;
                const summary = document.createElement('summary');
                summary.append(...header.childNodes);
                group.append(summary, grid);
                group.addEventListener('toggle', () => states.set(label, group.open));
                section.replaceWith(group);
            });
        };
        new MutationObserver(enhance).observe(box, { childList: true });
        enhance();
        return true;
    };
    if (attach()) return;
    const observer = new MutationObserver(() => {
        if (attach()) observer.disconnect();
    });
    observer.observe(center, { childList: true });
});

// The hologram follows the pointer across the workspace without intercepting input.
document.addEventListener('DOMContentLoaded', () => {
    const signal = document.getElementById('sidebar-agent-signal');
    if (!signal || signal.classList.contains('webgl-ready') || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let frame = 0;
    let pointer = null;
    const update = () => {
        frame = 0;
        if (!pointer) return;
        const rect = signal.getBoundingClientRect();
        const dx = Math.max(-1, Math.min(1, (pointer.x - rect.left - rect.width / 2) / (window.innerWidth * .42)));
        const dy = Math.max(-1, Math.min(1, (pointer.y - rect.top - rect.height / 2) / (window.innerHeight * .42)));
        signal.style.setProperty('--face-x', (dx * 7).toFixed(2) + 'px');
        signal.style.setProperty('--face-y', (dy * 5).toFixed(2) + 'px');
        signal.style.setProperty('--face-tilt', (dx * 9).toFixed(2) + 'deg');
        signal.style.setProperty('--eye-x', (dx * 3).toFixed(2) + 'px');
        signal.style.setProperty('--eye-y', (dy * 2).toFixed(2) + 'px');
    };
    document.addEventListener('pointermove', event => {
        if (event.pointerType === 'touch') return;
        pointer = { x: event.clientX, y: event.clientY };
        if (!frame) frame = requestAnimationFrame(update);
    }, { passive: true });
    document.addEventListener('pointerout', event => {
        if (event.relatedTarget) return;
        pointer = null;
        for (const name of ['--face-x','--face-y','--face-tilt','--eye-x','--eye-y']) signal.style.removeProperty(name);
    });
});
