/* ================= Utilities ================= */

function relativeTime(ts) {
    if (!ts) return 'just now';
    const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
    if (s < 60) return 'just now';
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    return `${Math.floor(s / 3600)}h ago`;
}

function isNearBottom() {
    const threshold = 80;
    return els.feed.scrollHeight - els.feed.scrollTop - els.feed.clientHeight < threshold;
}

function updateAutoScrollUI() {
    const label = els.autoScrollBtn.querySelector('.btn-label');
    if (label) {
        label.textContent = `Auto-scroll: ${state.autoScroll ? 'On' : 'Off'}`;
    } else {
        els.autoScrollBtn.textContent = `Auto-scroll: ${state.autoScroll ? 'On' : 'Off'}`;
    }
    els.autoScrollBtn.classList.toggle('off', !state.autoScroll);
    els.autoScrollBtn.setAttribute('aria-pressed', state.autoScroll ? 'true' : 'false');
    els.autoScrollBtn.classList.toggle('active', state.autoScroll);
}

function isRoomMuted(roomId) {
    return state.mutedRooms.has(roomId);
}

function loadMutedRooms() {
    try {
        const raw = localStorage.getItem('anonchat.muted');
        const list = raw ? JSON.parse(raw) : [];
        state.mutedRooms = new Set(Array.isArray(list) ? list : []);
    } catch (err) {
        state.mutedRooms = new Set();
    }
}

function saveMutedRooms() {
    localStorage.setItem('anonchat.muted', JSON.stringify(Array.from(state.mutedRooms)));
}

function updateRoomActionUI() {
    if (els.muteRoomBtn) {
        const isHome = state.room === 'all';
        const isMuted = isRoomMuted(state.room);
        els.muteRoomBtn.disabled = isHome;
        els.muteRoomBtn.classList.toggle('active', !isHome && isMuted);
        els.muteRoomBtn.setAttribute('aria-pressed', isMuted ? 'true' : 'false');
        const label = els.muteRoomBtn.querySelector('.btn-label');
        if (label) {
            label.textContent = isMuted ? 'Muted' : 'Mute';
        }
    }

    if (els.markReadBtn) {
        const unread = state.room === 'all'
            ? (state.unreadByRoom.all || 0)
            : (state.unreadByRoom[state.room] || 0);
        const label = els.markReadBtn.querySelector('.btn-label');
        if (label) {
            label.textContent = state.room === 'all' ? 'Mark all read' : 'Mark read';
        }
        els.markReadBtn.disabled = unread === 0;
    }
}

function updateScrollButton() {
    const shouldShow = !state.autoScroll || state.unread > 0;
    els.scrollBtn.classList.toggle('show', shouldShow);
    els.unreadBadge.textContent = state.unread;
    els.unreadBadge.classList.toggle('hidden', state.unread === 0);
}

function updateUnreadTotals() {
    const total = Object.entries(state.unreadByRoom)
        .filter(([key]) => key !== 'all')
        .reduce((sum, [, value]) => sum + value, 0);
    state.unreadByRoom.all = total;
    if (total > 0) {
        document.title = `(${total}) AnonChat // Secure`;
    } else {
        document.title = 'AnonChat // Secure';
    }
    if (els.homeUnread) {
        els.homeUnread.textContent = `${total}`;
    }
    updateRoomActionUI();
}

function resetUnread() {
    state.unread = 0;
    updateScrollButton();
}

function updateEmptyState(message) {
    const hasMessages = Boolean(els.feed.querySelector('.bubble-group:not(.hidden)'));
    if (message) {
        els.emptyState.querySelector('.empty-title').textContent = message.title;
        els.emptyState.querySelector('.empty-subtitle').textContent = message.subtitle;
    } else {
        els.emptyState.querySelector('.empty-title').textContent = 'No messages yet';
        els.emptyState.querySelector('.empty-subtitle').textContent = 'Say hello or switch to a peer to begin.';
    }
    els.emptyState.classList.toggle('hidden', hasMessages);
}

function showToast(text) {
    els.toast.textContent = text;
    els.toast.classList.add('show');
    window.clearTimeout(showToast._t);
    showToast._t = window.setTimeout(() => {
        els.toast.classList.remove('show');
    }, 1400);
}
