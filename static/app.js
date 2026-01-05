/* ================= Logic ================= */

const ICONS = {
    HASH: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 9h16M4 15h16M10 3L8 21M16 3l-2 18"/></svg>`,
    USER: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`
};

const EMOJI_PICKER = ['😀', '😄', '😂', '😊', '😍', '😎', '👍', '🔥', '✨', '🎉'];

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
    pendingOut: [],
    unreadByRoom: {},
    sidebarLastId: 0
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
    ifaceMenu: document.getElementById('interface-menu'),
    ifaceLabel: document.getElementById('current-interface'),
    navFilter: document.getElementById('nav-filter'),
    createRoom: document.getElementById('create-room'),
    messageFilter: document.getElementById('message-filter'),
    autoScrollBtn: document.getElementById('auto-scroll'),
    clearBtn: document.getElementById('clear-feed'),
    roomChip: document.getElementById('room-chip'),
    scrollBtn: document.getElementById('scroll-to-bottom'),
    unreadBadge: document.getElementById('unread-count'),
    emptyState: document.getElementById('empty-state'),
    toast: document.getElementById('toast'),
    charCount: document.getElementById('char-count'),
    fileInput: document.getElementById('file-input'),
    attachButton: document.getElementById('attach-button'),
    emojiToggle: document.getElementById('emoji-toggle'),
    emojiPicker: document.getElementById('emoji-picker'),
    homeSummary: document.getElementById('home-summary'),
    homePeers: document.getElementById('home-peers'),
    homePeerCount: document.getElementById('home-peer-count'),
    homeNearby: document.getElementById('home-nearby'),
    homeInterface: document.getElementById('home-interface'),
    toolbar: document.querySelector('.toolbar'),
    composer: document.querySelector('.composer')
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

function updateUnreadTotals() {
    const total = Object.values(state.unreadByRoom).reduce((sum, value) => sum + value, 0);
    if (total > 0) {
        document.title = `(${total}) AnonChat // Secure`;
    } else {
        document.title = 'AnonChat // Secure';
    }
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
        els.title.textContent = 'Home';
        els.roomChip.textContent = 'Home';
        els.count.textContent = `${peers.length} nearby device(s)`;
    } else {
        const peer = peers.find(p => p.id === state.room);
        const label = peer ? peerLabel(peer.id) : `${state.room.substring(0, 8)}...`;
        els.title.textContent = `Priv: ${label}`;
        els.roomChip.textContent = 'Direct';
        if (peer && peer.last_seen) {
            els.count.textContent = `Last seen ${relativeTime(peer.last_seen)}`;
        } else {
            els.count.textContent = 'Direct channel';
        }
    }
}

function updateHomeSummary(peers) {
    if (!els.homeSummary || !els.feed) return;
    const isHome = state.room === 'all';
    els.homeSummary.classList.toggle('hidden', !isHome);
    els.feed.classList.toggle('hidden', isHome);
    if (els.toolbar) {
        els.toolbar.classList.toggle('hidden', isHome);
    }
    if (els.composer) {
        els.composer.classList.toggle('hidden', isHome);
    }
    if (els.scrollBtn) {
        els.scrollBtn.classList.toggle('hidden', isHome);
    }
    if (!isHome) return;

    const count = peers.length;
    if (els.homePeerCount) {
        els.homePeerCount.textContent = `${count} nearby`;
    }
    if (els.homeNearby) {
        els.homeNearby.textContent = `${count}`;
    }
    if (els.homeInterface) {
        els.homeInterface.textContent = state.currentInterface || '-';
    }
    if (els.homePeers) {
        if (!count) {
            els.homePeers.innerHTML = '<div class="nav-empty">No nearby devices yet</div>';
            return;
        }
        els.homePeers.innerHTML = peers
            .map(peer => {
                const label = peerLabel(peer.id);
                const lastSeen = peer.last_seen ? relativeTime(peer.last_seen) : 'just now';
                return `<div class="summary-peer">${label}<span>${lastSeen}</span></div>`;
            })
            .join('');
    }
}

function peerLabel(peerId) {
    const peer = state.peers.find(item => item.id === peerId);
    if (peer && peer.nickname) {
        return `${peer.nickname} (${peerId.substring(0, 8)})`;
    }
    return `${peerId.substring(0, 8)}...`;
}

function renderNav(rooms, peers) {
    const safeRooms = Array.isArray(rooms) ? rooms : [];
    const safePeers = Array.isArray(peers) ? peers : [];
    const query = state.navQuery.trim().toLowerCase();

    els.rooms.innerHTML = '';
    const allItem = document.createElement('div');
    allItem.className = `nav-item ${state.room === 'all' ? 'active' : ''}`;
    allItem.innerHTML = `${ICONS.HASH} <span>Home</span>`;
    const allUnread = state.unreadByRoom.all || 0;
    if (allUnread > 0) {
        const badge = document.createElement('span');
        badge.className = 'nav-badge';
        badge.textContent = allUnread;
        allItem.appendChild(badge);
    }
    allItem.onclick = () => switchRoom('all');
    if (!query || 'home'.includes(query)) {
        els.rooms.appendChild(allItem);
    }

    safeRooms.forEach(r => {
        if (r === 'all') return;
        if (query && !String(r).toLowerCase().includes(query)) return;
        const item = document.createElement('div');
        item.className = `nav-item ${state.room === r ? 'active' : ''}`;
        item.innerHTML = `${ICONS.HASH} <span>${peerLabel(r)}</span>`;
        const unread = state.unreadByRoom[r] || 0;
        if (unread > 0) {
            const badge = document.createElement('span');
            badge.className = 'nav-badge';
            badge.textContent = unread;
            item.appendChild(badge);
        }
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
        item.innerHTML = `${ICONS.USER} <span>${peerLabel(p.id)}</span>`;
        const unread = state.unreadByRoom[p.id] || 0;
        if (unread > 0) {
            const badge = document.createElement('span');
            badge.className = 'nav-badge';
            badge.textContent = unread;
            item.appendChild(badge);
        }
        item.onclick = () => switchRoom(p.id);
        els.peers.appendChild(item);
    });

    els.statusDot.className = safePeers.length > 0 ? 'status-dot active' : 'status-dot';
    els.statusText.textContent = safePeers.length > 0 ? 'Connected' : 'Searching...';
    els.statusLabel.textContent = safePeers.length > 0 ? 'Live' : 'Syncing';

    updateHeader(safePeers);
    updateHomeSummary(safePeers);
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

function parsePayload(text) {
    if (typeof text !== 'string') {
        return { type: 'text', text: '' };
    }
    if (text.startsWith('FILE::')) {
        try {
            const payload = JSON.parse(text.slice(6));
            if (payload && payload.data && payload.name) {
                return { type: 'file', ...payload };
            }
            if (payload && payload.url && payload.name) {
                return { type: 'file', ...payload };
            }
        } catch (err) {
            return { type: 'text', text };
        }
    }
    return { type: 'text', text };
}

function formatBytes(bytes) {
    if (!bytes) return '';
    const units = ['B', 'KB', 'MB', 'GB'];
    let idx = 0;
    let value = bytes;
    while (value >= 1024 && idx < units.length - 1) {
        value /= 1024;
        idx += 1;
    }
    return `${value.toFixed(value >= 10 || idx === 0 ? 0 : 1)}${units[idx]}`;
}

function buildBubbleContent(bubble, payload) {
    if (payload.type === 'text') {
        bubble.textContent = payload.text;
        return payload.text;
    }

    if (payload.type === 'file') {
        const wrapper = document.createElement('div');
        wrapper.className = 'file-card';

        const previewUrl = payload.data || payload.url;
        if (payload.mime && payload.mime.startsWith('image/') && previewUrl) {
            const img = document.createElement('img');
            img.src = previewUrl;
            img.alt = payload.name;
            img.className = 'file-thumb';
            wrapper.appendChild(img);
        }

        const info = document.createElement('div');
        info.className = 'file-info';
        const name = document.createElement('div');
        name.className = 'file-name';
        name.textContent = payload.name;
        const meta = document.createElement('div');
        meta.className = 'file-meta';
        meta.textContent = payload.size ? formatBytes(payload.size) : payload.mime || 'File';
        info.appendChild(name);
        info.appendChild(meta);

        const link = document.createElement('a');
        link.className = 'file-download';
        link.href = payload.data || payload.url || '#';
        link.download = payload.name || 'download';
        link.textContent = payload.url ? 'Open' : 'Download';
        link.target = payload.url ? '_blank' : '';
        link.rel = payload.url ? 'noopener' : '';
        info.appendChild(link);

        wrapper.appendChild(info);
        bubble.appendChild(wrapper);
        return payload.name || 'file';
    }

    bubble.textContent = payload.text || '';
    return payload.text || '';
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
    const payload = parsePayload(msg.text);
    const filterText = buildBubbleContent(bubble, payload);
    bubble.title = `${isOut ? 'You' : msg.peer_id.substring(0, 8)} - ${relativeTime(msg.ts)}`;

    let group = els.feed.lastElementChild;
    if (!group || !group.classList.contains('bubble-group') || group.dataset.groupKey !== groupKey) {
        group = document.createElement('div');
        group.className = isOut ? 'bubble-group out' : 'bubble-group';
        group.dataset.groupKey = groupKey;
        group.dataset.text = (filterText || '').toLowerCase();

        if (!isOut) {
            const meta = document.createElement('div');
            meta.className = 'bubble-meta';
            const label = peerLabel(msg.peer_id);
            meta.innerHTML = `<strong>${label}</strong> - ${relativeTime(msg.ts)}`;
            group.appendChild(meta);
        }

        els.feed.appendChild(group);
    } else {
        group.dataset.text += ` ${(filterText || '').toLowerCase()}`;
    }

    group.appendChild(bubble);
    state.lastGroupKey = groupKey;

    applyMessageFilter();

    if (msg.direction === 'in' && msgRoom !== state.room && state.room !== 'all') {
        state.unreadByRoom[msgRoom] = (state.unreadByRoom[msgRoom] || 0) + 1;
        renderNav(state.rooms, state.peers);
        updateUnreadTotals();
    }

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
    if (room === 'all') {
        state.unreadByRoom = {};
    } else {
        state.unreadByRoom[room] = 0;
    }
    els.feed.querySelectorAll('.bubble-group').forEach(node => node.remove());
    resetUnread();
    updateEmptyState();
    updateUnreadTotals();
    renderNav(state.rooms, state.peers);
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

        if (data.me) {
            if (data.me.name && els.userName) {
                els.userName.textContent = data.me.name;
            }
            if (typeof data.me.nickname === 'string' && els.nicknameInput) {
                const isEditing = document.activeElement === els.nicknameInput;
                if (!isEditing) {
                    els.nicknameInput.value = data.me.nickname;
                }
            }
        }

        if (data.interface && data.interface.current) {
            state.currentInterface = data.interface.current;
            els.ifaceLabel.textContent = data.interface.current;
            if (state.interfaces.length) {
                renderInterfaceMenu(state.interfaces);
            }
            updateHomeSummary(state.peers);
        }

        if (data.messages && data.messages.length) {
            data.messages.forEach(addMessage);
            state.lastId = data.messages[data.messages.length - 1].id;
            state.sidebarLastId = Math.max(state.sidebarLastId, state.lastId);
        }
    } finally {
        state.fetching = false;
    }
}

async function fetchSidebarState() {
    if (state.room === 'all') return;
    try {
        const res = await fetch(`/api/state?after=${state.sidebarLastId}&room=all`);
        if (!res.ok) return;
        const data = await res.json();

        state.rooms = data.rooms || state.rooms;
        state.peers = data.peers || state.peers;
        renderNav(state.rooms, state.peers);

        if (data.messages && data.messages.length) {
            data.messages.forEach(msg => {
                if (msg.direction !== 'in') return;
                const msgRoom = msg.room || msg.peer_id;
                if (msgRoom === state.room) return;
                state.unreadByRoom[msgRoom] = (state.unreadByRoom[msgRoom] || 0) + 1;
            });
            state.sidebarLastId = data.messages[data.messages.length - 1].id;
            updateUnreadTotals();
        }
    } catch (err) {
        return;
    }
}

async function sendPayload(text) {
    registerPending(text, state.room);
    addMessage({
        direction: 'out',
        text,
        peer_id: 'me',
        ts: Math.floor(Date.now() / 1000),
        room: state.room,
        optimistic: true
    });

    await fetch('/api/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room: state.room, text })
    });
}

async function sendMessage(e) {
    e.preventDefault();
    const text = els.msg.value.trim();
    if (!text) return;

    await sendPayload(text);

    els.msg.value = '';
    els.msg.style.height = 'auto';
    els.charCount.textContent = '0';
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

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
    });
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.error || 'Upload failed');
    }
    return data;
}

async function sendFile(file) {
    try {
        const uploaded = await uploadFile(file);
        const payload = {
            name: uploaded.name,
            mime: uploaded.mime,
            size: uploaded.size,
            url: uploaded.url
        };
        await sendPayload(`FILE::${JSON.stringify(payload)}`);
    } catch (err) {
        showToast(err.message || 'Upload failed');
    }
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

if (els.navFilter) {
    els.navFilter.addEventListener('input', () => {
        state.navQuery = els.navFilter.value;
        renderNav(state.rooms, state.peers);
    });
}

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

if (els.attachButton && els.fileInput) {
    els.attachButton.addEventListener('click', () => {
        els.fileInput.click();
    });
    els.fileInput.addEventListener('change', () => {
        const file = els.fileInput.files && els.fileInput.files[0];
        if (!file) return;
        sendFile(file);
        els.fileInput.value = '';
    });
}

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
        toggleEmojiPicker(false);
    });
}

if (els.ifaceMenu) {
    els.ifaceMenu.addEventListener('click', async e => {
        const button = e.target.closest('.interface-option');
        if (!button) return;
        const ip = button.dataset.ip;
        if (!ip) return;
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
        if (typeof data.nickname === 'string') {
            els.nicknameInput.value = data.nickname;
        } else {
            els.nicknameInput.value = '';
        }
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

if (els.createRoom) {
    els.createRoom.addEventListener('click', () => {
        showToast('Room creation coming soon');
    });
}

document.addEventListener('click', e => {
    const emojiToggleHit = els.emojiToggle && els.emojiToggle.contains(e.target);
    if (els.emojiPicker && !els.emojiPicker.contains(e.target) && !emojiToggleHit) {
        toggleEmojiPicker(false);
    }
});

els.msg.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = `${this.scrollHeight}px`;
    els.charCount.textContent = `${this.value.length}`;
});

els.msg.addEventListener('paste', e => {
    if (!e.clipboardData || !e.clipboardData.items) return;
    const items = Array.from(e.clipboardData.items);
    const imageItem = items.find(item => item.type && item.type.startsWith('image/'));
    if (!imageItem) return;
    const file = imageItem.getAsFile();
    if (!file) return;
    e.preventDefault();
    sendFile(file);
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
updateUnreadTotals();
renderEmojiPicker();
loadInterfaces();
setInterval(fetchSidebarState, 2000);
setInterval(fetchState, 1000);
fetchState(true);
