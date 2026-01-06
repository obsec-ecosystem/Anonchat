/* ================= Interfaces ================= */

function renderInterfaceMenu(list) {
    if (!els.ifaceMenu) return;
    if (!list.length) {
        els.ifaceMenu.innerHTML = '<div class="nav-empty">No interfaces</div>';
        return;
    }

    els.ifaceMenu.innerHTML = list
        .map(i => {
            const isActive = i.ip === state.currentInterface;
            return `<button class="interface-option ${isActive ? 'active' : ''}" type="button" data-ip="${i.ip}">\n` +
                `<span class="mono">${i.ip}</span>\n` +
                `<span>${i.name}</span>\n` +
                `</button>`;
        })
        .join('');
}
