/* ================= Logic ================= */

const ICONS = {
    HASH: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 9h16M4 15h16M10 3L8 21M16 3l-2 18"/></svg>`,
    USER: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`
};

const EMOJI_PICKER = [
    '😀','😁','😂','🤣','😊','😍','😎','🤩',
    '😇','😅','😉','🙃','😴','🤔','😮','😤',
    '🥳','😱','😭','😡','👍','👎','👏','🙏',
    '🔥','✨','🚀','💡','🎯','✅','❗','⚡',
    '🎉','🤝','💬','🧠','🧩','📌','🔒','🛰️'
];

const state = {
    room: 'all',
    lastId: 0,
    fetching: false,
    autoScroll: true,
    unread: 0,
    navQuery: '',
    filterQuery: '',
    peers: [],
    lastGroupKey: null,
    rooms: [],
    currentInterface: '',
    interfaces: [],
    pendingOut: []
};

const els = {
    feed: document.getElementById('feed'),
    rooms: document.getElementById('rooms-list'),
    peers: document.getElementById('peers-list'),
    title: document.getElementById('current-room-name'),
    count: document.getElementById('peer-count'),
    statusDot: document.getElementById('status-indicator'),
    statusText: document.getElementById('connection-status'),
    statusLabel: document.getElementById('status-label'),
    userName: document.getElementById('user-name'),
    nicknameInput: document.getElementById('nickname-input'),
    nicknameSave: document.getElementById('nickname-save'),
    form: document.getElementById('send-form'),
    msg: document.getElementById('message'),
    ifaceButton: document.getElementById('interface-button'),
    ifaceMenu: document.getElementById('interface-menu'),
    ifaceLabel: document.getElementById('current-interface'),
    navFilter: document.getElementById('nav-filter'),
    messageFilter: document.getElementById('message-filter'),
    autoScrollBtn: document.getElementById('auto-scroll'),
    clearBtn: document.getElementById('clear-feed'),
    roomChip: document.getElementById('room-chip'),
    scrollBtn: document.getElementById('scroll-to-bottom'),
    unreadBadge: document.getElementById('unread-count'),
    emptyState: document.getElementById('empty-state'),
    toast: document.getElementById('toast'),
    charCount: document.getElementById('char-count'),
    emojiToggle: document.getElementById('emoji-toggle'),
    emojiPicker: document.getElementById('emoji-picker')
};

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
    els.autoScrollBtn.textContent = `Auto-scroll: ${state.autoScroll ? 'On' : 'Off'}`;
    els.autoScrollBtn.classList.toggle('off', !state.autoScroll);
}

function updateScrollButton() {
    const shouldShow = !state.autoScroll || state.unread > 0;
    els.scrollBtn.classList.toggle('show', shouldShow);
    els.unreadBadge.textContent = state.unread;
    els.unreadBadge.classList.toggle('hidden', state.unread === 0);
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

function updateHeader(peers) {
    if (state.room === 'all') {
        els.title.textContent = 'Global Lobby';
        els.roomChip.textContent = 'Global';
        els.count.textContent = `${peers.length} active peer(s)`;
    } else {
        const peer = peers.find(p => p.id === state.room);
        els.title.textContent = `Priv: ${state.room.substring(0, 8)}...`;
        els.roomChip.textContent = 'Direct';
        if (peer && peer.last_seen) {
            els.count.textContent = `Last seen ${relativeTime(peer.last_seen)}`;
        } else {
            els.count.textContent = 'Direct channel';
        }
    }
}

function renderNav(rooms, peers) {
    const safeRooms = Array.isArray(rooms) ? rooms : [];
    const safePeers = Array.isArray(peers) ? peers : [];
    const query = state.navQuery.trim().toLowerCase();

    els.rooms.innerHTML = '';
    const allItem = document.createElement('div');
    allItem.className = `nav-item ${state.room === 'all' ? 'active' : ''}`;
    allItem.innerHTML = `${ICONS.HASH} <span>Global Lobby</span>`;
    allItem.onclick = () => switchRoom('all');
    if (!query || 'global lobby'.includes(query)) {
        els.rooms.appendChild(allItem);
    }

    safeRooms.forEach(r => {
        if (r === 'all') return;
        if (query && !String(r).toLowerCase().includes(query)) return;
        const item = document.createElement('div');
        item.className = `nav-item ${state.room === r ? 'active' : ''}`;
        item.innerHTML = `${ICONS.HASH} <span>${r}</span>`;
        item.onclick = () => switchRoom(r);
        els.rooms.appendChild(item);
    });

    els.peers.innerHTML = '';
    const filteredPeers = safePeers.filter(p => !query || (p.id && p.id.toLowerCase().includes(query)));

    if (filteredPeers.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'nav-empty';
        empty.textContent = query ? 'No matches' : 'No active peers';
        els.peers.appendChild(empty);
    }

    filteredPeers.forEach(p => {
        const item = document.createElement('div');
        item.className = `nav-item ${state.room === p.id ? 'active' : ''}`;
        item.innerHTML = `${ICONS.USER} <span class="mono">${p.id.substring(0, 8)}...</span>`;
        item.onclick = () => switchRoom(p.id);
        els.peers.appendChild(item);
    });

    els.statusDot.className = safePeers.length > 0 ? 'status-dot active' : 'status-dot';
    els.statusText.textContent = safePeers.length > 0 ? 'Connected' : 'Searching...';
    els.statusLabel.textContent = safePeers.length > 0 ? 'Live' : 'Syncing';

    updateHeader(safePeers);
}

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

function registerPending(text, room) {
    state.pendingOut.push({ text, room });
    if (state.pendingOut.length > 50) {
        state.pendingOut.shift();
    }
}

function consumePending(text, room) {
    const index = state.pendingOut.findIndex(p => p.text === text && p.room === room);
    if (index === -1) return false;
    state.pendingOut.splice(index, 1);
    return true;
}

function addMessage(msg) {
    const isOut = msg.direction === 'out';
    const msgRoom = msg.room || state.room;
    if (!msg.optimistic && isOut && consumePending(msg.text, msgRoom)) {
        return;
    }
    const groupKey = `${msg.direction}:${msg.peer_id}`;
    const bubble = document.createElement('div');
    bubble.className = `bubble ${isOut ? 'out' : 'in'}`;
    bubble.textContent = msg.text;
    bubble.title = `${isOut ? 'You' : msg.peer_id.substring(0, 8)} - ${relativeTime(msg.ts)}`;

    let group = els.feed.lastElementChild;
    if (!group || !group.classList.contains('bubble-group') || group.dataset.groupKey !== groupKey) {
        group = document.createElement('div');
        group.className = isOut ? 'bubble-group out' : 'bubble-group';
        group.dataset.groupKey = groupKey;
        group.dataset.text = msg.text.toLowerCase();

        if (!isOut) {
            const meta = document.createElement('div');
            meta.className = 'bubble-meta';
            meta.innerHTML = `<strong>${msg.peer_id.substring(0, 8)}</strong> - ${relativeTime(msg.ts)}`;
            group.appendChild(meta);
        }

        els.feed.appendChild(group);
    } else {
        group.dataset.text += ` ${msg.text.toLowerCase()}`;
    }

    group.appendChild(bubble);
    state.lastGroupKey = groupKey;

    applyMessageFilter();

    if (state.autoScroll || isNearBottom()) {
        els.feed.scrollTop = els.feed.scrollHeight;
        resetUnread();
    } else {
        state.unread += 1;
        updateScrollButton();
    }

    updateEmptyState();
}

function applyMessageFilter() {
    const query = state.filterQuery.trim().toLowerCase();
    const groups = els.feed.querySelectorAll('.bubble-group');
    if (!query) {
        groups.forEach(group => group.classList.remove('hidden'));
        updateEmptyState();
        return;
    }

    let matches = 0;
    groups.forEach(group => {
        const text = group.dataset.text || '';
        const hit = text.includes(query);
        group.classList.toggle('hidden', !hit);
        if (hit) matches += 1;
    });

    updateEmptyState({
        title: matches ? 'Filtered view' : 'No matches',
        subtitle: matches ? `${matches} message group(s) match.` : 'Try a different search term.'
    });
}

function switchRoom(room) {
    if (state.room === room) return;
    state.room = room;
    state.lastId = 0;
    state.lastGroupKey = null;
    els.feed.querySelectorAll('.bubble-group').forEach(node => node.remove());
    resetUnread();
    updateEmptyState();
    fetchState(true);
}

async function fetchState(force = false) {
    if (state.fetching) return;
    state.fetching = true;
    try {
        const res = await fetch(`/api/state?after=${force ? 0 : state.lastId}&room=${encodeURIComponent(state.room)}`);
        if (!res.ok) return;
        const data = await res.json();

        state.rooms = data.rooms || [];
        state.peers = data.peers || [];
        renderNav(state.rooms, state.peers);

        if (data.me && data.me.name && els.userName) {
            els.userName.textContent = data.me.name;
        }

        if (data.interface && data.interface.current) {
            state.currentInterface = data.interface.current;
            els.ifaceLabel.textContent = data.interface.current;
            if (state.interfaces.length) {
                renderInterfaceMenu(state.interfaces);
            }
        }

        if (data.messages && data.messages.length) {
            data.messages.forEach(addMessage);
            state.lastId = data.messages[data.messages.length - 1].id;
        }
    } finally {
        state.fetching = false;
    }
}

async function sendMessage(e) {
    e.preventDefault();
    const text = els.msg.value.trim();
    if (!text) return;

    registerPending(text, state.room);
    addMessage({
        direction: 'out',
        text,
        peer_id: 'me',
        ts: Math.floor(Date.now() / 1000),
        room: state.room,
        optimistic: true
    });

    els.msg.value = '';
    els.msg.style.height = 'auto';
    els.charCount.textContent = '0';

    await fetch('/api/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room: state.room, text })
    });
}

function insertEmoji(emoji) {
    const input = els.msg;
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const value = input.value;
    input.value = `${value.slice(0, start)}${emoji}${value.slice(end)}`;
    const cursor = start + emoji.length;
    input.setSelectionRange(cursor, cursor);
    input.focus();
    input.dispatchEvent(new Event('input', { bubbles: true }));
}

function renderEmojiPicker() {
    if (!els.emojiPicker) return;
    els.emojiPicker.innerHTML = EMOJI_PICKER
        .map(emoji => `<button class="emoji-btn" type="button" data-emoji="${emoji}" aria-label="Emoji ${emoji}">${emoji}</button>`)
        .join('');
}

function toggleEmojiPicker(force) {
    if (!els.emojiPicker) return;
    const isHidden = els.emojiPicker.classList.contains('hidden');
    const shouldShow = force !== undefined ? force : isHidden;
    els.emojiPicker.classList.toggle('hidden', !shouldShow);
}

function toggleInterfaceMenu(force) {
    if (!els.ifaceMenu) return;
    const isHidden = els.ifaceMenu.classList.contains('hidden');
    const shouldShow = force !== undefined ? force : isHidden;
    els.ifaceMenu.classList.toggle('hidden', !shouldShow);
}

function handleFeedScroll() {
    if (isNearBottom()) {
        if (!state.autoScroll) {
            state.autoScroll = true;
            updateAutoScrollUI();
        }
        resetUnread();
    } else if (state.autoScroll) {
        state.autoScroll = false;
        updateAutoScrollUI();
    }
    updateScrollButton();
}

async function loadInterfaces() {
    const res = await fetch('/api/interfaces');
    const data = await res.json();
    const list = data.interfaces || [];
    state.interfaces = list;
    renderInterfaceMenu(list);
}

els.navFilter.addEventListener('input', () => {
    state.navQuery = els.navFilter.value;
    renderNav(state.rooms, state.peers);
});

els.messageFilter.addEventListener('input', () => {
    state.filterQuery = els.messageFilter.value;
    applyMessageFilter();
});

els.autoScrollBtn.addEventListener('click', () => {
    state.autoScroll = !state.autoScroll;
    updateAutoScrollUI();
    if (state.autoScroll) {
        els.feed.scrollTop = els.feed.scrollHeight;
        resetUnread();
    }
    updateScrollButton();
});

els.clearBtn.addEventListener('click', () => {
    if (!confirm('Clear the local message view?')) return;
    els.feed.querySelectorAll('.bubble-group').forEach(node => node.remove());
    resetUnread();
    updateEmptyState();
});

els.scrollBtn.addEventListener('click', () => {
    els.feed.scrollTop = els.feed.scrollHeight;
    state.autoScroll = true;
    updateAutoScrollUI();
    resetUnread();
    updateScrollButton();
});

els.feed.addEventListener('scroll', handleFeedScroll);

els.feed.addEventListener('click', async e => {
    const bubble = e.target.closest('.bubble');
    if (!bubble) return;
    try {
        await navigator.clipboard.writeText(bubble.textContent);
        showToast('Message copied');
    } catch (err) {
        showToast('Copy failed');
    }
});

if (els.emojiToggle) {
    els.emojiToggle.addEventListener('click', () => {
        toggleEmojiPicker();
    });
}

if (els.emojiPicker) {
    els.emojiPicker.addEventListener('click', e => {
        const button = e.target.closest('.emoji-btn');
        if (!button || !button.dataset.emoji) return;
        insertEmoji(button.dataset.emoji);
    });
}

if (els.ifaceButton) {
    els.ifaceButton.addEventListener('click', () => {
        toggleInterfaceMenu();
    });
}

if (els.ifaceMenu) {
    els.ifaceMenu.addEventListener('click', async e => {
        const button = e.target.closest('.interface-option');
        if (!button) return;
        const ip = button.dataset.ip;
        if (!ip) return;
        toggleInterfaceMenu(false);
        if (confirm(`Switch interface to ${ip}?`)) {
            await fetch('/api/interface', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ip })
            });
            window.location.reload();
        }
    });
}

if (els.nicknameSave && els.nicknameInput) {
    const submitNickname = async () => {
        const nickname = els.nicknameInput.value.trim();
        const res = await fetch('/api/nickname', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nickname })
        });
        const data = await res.json();
        if (!res.ok) {
            showToast(data.error || 'Nickname update failed');
            return;
        }
        if (data.name && els.userName) {
            els.userName.textContent = data.name;
        }
        els.nicknameInput.value = '';
        showToast(nickname ? 'Nickname updated' : 'Nickname cleared');
    };

    els.nicknameSave.addEventListener('click', submitNickname);
    els.nicknameInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            submitNickname();
        }
    });
}

document.addEventListener('click', e => {
    if (els.emojiPicker && !els.emojiPicker.contains(e.target) && !els.emojiToggle?.contains(e.target)) {
        toggleEmojiPicker(false);
    }
    if (els.ifaceMenu && !els.ifaceMenu.contains(e.target) && !els.ifaceButton?.contains(e.target)) {
        toggleInterfaceMenu(false);
    }
});

els.msg.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = `${this.scrollHeight}px`;
    els.charCount.textContent = `${this.value.length}`;
});

els.msg.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage(e);
    }
});

els.form.addEventListener('submit', sendMessage);

updateAutoScrollUI();
updateScrollButton();
updateEmptyState();
renderEmojiPicker();
loadInterfaces();
setInterval(fetchState, 1000);
fetchState(true);
