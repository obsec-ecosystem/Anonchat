/* ================= Messages ================= */

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

function isImagePayload(payload) {
    if (!payload) return false;
    if (payload.mime && payload.mime.startsWith('image/')) return true;
    const name = (payload.name || '').toLowerCase();
    const url = (payload.url || '').toLowerCase();
    const data = (payload.data || '').toLowerCase();
    const imageExt = /\.(png|jpe?g|gif|webp|bmp)$/;
    if (imageExt.test(name) || imageExt.test(url)) return true;
    if (data.startsWith('data:image/')) return true;
    return false;
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
        if (previewUrl && isImagePayload(payload)) {
            const img = document.createElement('img');
            img.src = previewUrl;
            img.alt = payload.name;
            img.className = 'file-thumb';
            img.loading = 'lazy';
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
        const href = payload.data || payload.url || '#';
        link.href = href;
        if (payload.url) {
            link.textContent = 'Open';
            link.target = '_blank';
            link.rel = 'noopener';
        } else {
            link.textContent = 'Download';
            link.download = payload.name || 'download';
        }
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

    let unreadChanged = false;
    if (msg.direction === 'in' && msgRoom !== state.room) {
        unreadChanged = incrementUnread(msgRoom);
        addNotification(msg);
    }

    if (state.autoScroll || isNearBottom()) {
        els.feed.scrollTop = els.feed.scrollHeight;
        resetUnread();
    } else {
        state.unread += 1;
        updateScrollButton();
    }

    updateEmptyState();
    return unreadChanged;
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
    hideMemberPopover();
    const roomObj = roomById(room);
    if (roomObj && !roomObj.joined) {
        openRoomModal('join', roomObj);
        return;
    }
    state.room = room;
    state.lastId = 0;
    state.lastGroupKey = null;
    if (room === 'all') {
        clearUnread('all');
    } else {
        clearUnread(room);
    }
    els.feed.querySelectorAll('.bubble-group').forEach(node => node.remove());
    resetUnread();
    updateEmptyState();
    renderNav(state.rooms, state.peers);
    fetchState(true);
}
