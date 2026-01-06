/* ================= Rooms & Navigation ================= */

function roomById(roomId) {
    return state.rooms.find(room => room.id === roomId);
}

function roomLabel(roomId) {
    if (roomId === 'all') return 'Home';
    const room = roomById(roomId);
    if (room && room.name) {
        return room.name;
    }
    return peerLabel(roomId);
}

function peerLabel(peerId) {
    const peer = state.peers.find(item => item.id === peerId);
    if (peer && peer.nickname) {
        return `${peer.nickname} (${peerId.substring(0, 8)})`;
    }
    return `${peerId.substring(0, 8)}...`;
}

function peerIp(peerId) {
    const peer = state.peers.find(item => item.id === peerId);
    return peer ? peer.ip : '';
}

function loadBlockedPeers() {
    try {
        const raw = localStorage.getItem('anonchat.blocked');
        const list = raw ? JSON.parse(raw) : [];
        state.blockedPeers = new Set(Array.isArray(list) ? list : []);
    } catch (err) {
        state.blockedPeers = new Set();
    }
}

function saveBlockedPeers() {
    localStorage.setItem('anonchat.blocked', JSON.stringify(Array.from(state.blockedPeers)));
}

function renderNav(rooms, peers) {
    const safeRooms = Array.isArray(rooms) ? rooms : [];
    const safePeers = Array.isArray(peers) ? peers : [];
    const query = state.navQuery.trim().toLowerCase();

    els.rooms.innerHTML = '';
    const allItem = document.createElement('div');
    allItem.className = `nav-item ${state.room === 'all' ? 'active' : ''}`;
    allItem.innerHTML = `<span class="nav-icon">${ICONS.HASH}</span><span class="nav-text">Home</span>`;
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

    let shownRooms = 0;
    safeRooms.forEach(room => {
        if (!room || !room.id) return;
        const roomName = room.name || `Room ${room.id.substring(0, 6)}`;
        const haystack = `${roomName} ${room.id}`.toLowerCase();
        if (query && !haystack.includes(query)) return;

        const item = document.createElement('div');
        item.className = `nav-item ${state.room === room.id ? 'active' : ''} ${room.joined ? '' : 'inactive'}`;
        const icon = document.createElement('span');
        icon.className = 'nav-icon';
        icon.innerHTML = ICONS.HASH;
        item.appendChild(icon);

        const label = document.createElement('div');
        label.className = 'nav-label';
        const name = document.createElement('div');
        name.className = 'nav-name';
        name.textContent = roomName;
        label.appendChild(name);

        const meta = document.createElement('div');
        meta.className = 'nav-meta';
        const count = room.member_count || 0;
        const limit = room.max_members ? ` / ${room.max_members}` : '';
        const metaText = document.createElement('span');
        metaText.textContent = `${count}${limit} member(s)`;
        meta.appendChild(metaText);
        if (room.locked) {
            const lock = document.createElement('span');
            lock.className = 'nav-tag lock';
            lock.innerHTML = `${ICONS.LOCK} Locked`;
            meta.appendChild(lock);
        }
        if (isRoomMuted(room.id)) {
            const muted = document.createElement('span');
            muted.className = 'nav-tag muted';
            muted.textContent = 'Muted';
            meta.appendChild(muted);
        }
        if (room.is_owner) {
            const owner = document.createElement('span');
            owner.className = 'nav-tag owner';
            owner.textContent = 'Owner';
            meta.appendChild(owner);
        } else if (room.pending) {
            const pending = document.createElement('span');
            pending.className = 'nav-tag pending';
            pending.textContent = 'Pending';
            meta.appendChild(pending);
        }
        label.appendChild(meta);
        item.appendChild(label);

        const unread = state.unreadByRoom[room.id] || 0;
        if (unread > 0) {
            const badge = document.createElement('span');
            badge.className = 'nav-badge';
            badge.textContent = unread;
            item.appendChild(badge);
        }

        if (!room.is_owner) {
            const action = document.createElement('button');
            action.className = 'nav-action';
            action.textContent = room.joined ? 'Leave' : 'Join';
            action.classList.add(room.joined ? 'leave' : 'join');
            if (room.pending) {
                action.disabled = true;
                action.textContent = 'Pending';
            }
            action.onclick = e => {
                e.stopPropagation();
                if (room.pending) return;
                if (room.joined) {
                    if (!confirm(`Leave ${roomName}?`)) return;
                    leaveRoom(room.id);
                } else {
                    openRoomModal('join', room);
                }
            };
            item.appendChild(action);
        }

        item.onclick = () => {
            if (room.joined) {
                switchRoom(room.id);
            } else if (!room.pending) {
                openRoomModal('join', room);
            }
        };
        els.rooms.appendChild(item);
        shownRooms += 1;
    });

    if (shownRooms === 0) {
        const empty = document.createElement('div');
        empty.className = 'nav-empty';
        empty.textContent = query ? 'No matches' : 'No rooms found';
        els.rooms.appendChild(empty);
    }

    els.peers.innerHTML = '';
    const filteredPeers = safePeers.filter(p => !state.blockedPeers.has(p.id))
        .filter(p => !query || (p.id && p.id.toLowerCase().includes(query)));

    if (filteredPeers.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'nav-empty';
        if (query) {
            empty.textContent = 'No matches';
        } else if (safePeers.length && state.blockedPeers.size) {
            empty.textContent = `All peers blocked (${state.blockedPeers.size})`;
        } else {
            empty.textContent = 'No active peers';
        }
        els.peers.appendChild(empty);
    }

    filteredPeers.forEach(p => {
        const item = document.createElement('div');
        item.className = `nav-item ${state.room === p.id ? 'active' : ''}`;
        item.innerHTML = `<span class="nav-icon">${ICONS.USER}</span><span class="nav-text">${peerLabel(p.id)}</span>`;
        if (isRoomMuted(p.id)) {
            const muted = document.createElement('span');
            muted.className = 'nav-tag muted';
            muted.textContent = 'Muted';
            item.appendChild(muted);
        }
        const unread = state.unreadByRoom[p.id] || 0;
        if (unread > 0) {
            const badge = document.createElement('span');
            badge.className = 'nav-badge';
            badge.textContent = unread;
            item.appendChild(badge);
        }
        const blockBtn = document.createElement('button');
        blockBtn.className = 'nav-action';
        blockBtn.classList.add('block');
        blockBtn.textContent = 'Block';
        blockBtn.onclick = e => {
            e.stopPropagation();
            if (!confirm(`Block ${peerLabel(p.id)}?`)) return;
            state.blockedPeers.add(p.id);
            saveBlockedPeers();
            renderNav(state.rooms, state.peers);
        };
        item.appendChild(blockBtn);
        item.onclick = () => switchRoom(p.id);
        els.peers.appendChild(item);
    });

    els.statusDot.className = safePeers.length > 0 ? 'status-dot active' : 'status-dot';
    els.statusText.textContent = safePeers.length > 0 ? 'Connected' : 'Searching...';
    els.statusLabel.textContent = safePeers.length > 0 ? 'Live' : 'Syncing';

    updateHeader(safePeers);
    updateHomeSummary(safePeers);
    updateUnreadTotals();
    renderMembers(roomById(state.room));
}
