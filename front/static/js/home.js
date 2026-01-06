/* ================= Home & Header ================= */

function updateHeader(peers) {
    if (state.room === 'all') {
        els.title.textContent = 'Home';
        els.roomChip.textContent = 'Home';
        els.count.textContent = `${peers.length} nearby device(s)`;
        updateRoomActionUI();
        return;
    }

    const room = roomById(state.room);
    if (room) {
        const count = room.member_count || 0;
        const limit = room.max_members ? ` / ${room.max_members}` : '';
        els.title.textContent = `Room: ${room.name || state.room.substring(0, 8)}`;
        els.roomChip.textContent = room.locked ? 'Locked' : 'Room';
        els.count.textContent = room.pending ? 'Join request pending' : `${count}${limit} member(s)`;
        updateRoomActionUI();
        return;
    }

    const peer = peers.find(p => p.id === state.room);
    const label = peer ? peerLabel(peer.id) : `${state.room.substring(0, 8)}...`;
    els.title.textContent = `Priv: ${label}`;
    els.roomChip.textContent = 'Direct';
    if (peer && peer.last_seen) {
        els.count.textContent = `Last seen ${relativeTime(peer.last_seen)}`;
    } else {
        els.count.textContent = 'Direct channel';
    }
    updateRoomActionUI();
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
    if (els.homeRoomCount) {
        const roomCount = state.rooms.filter(room => room.joined).length + 1;
        els.homeRoomCount.textContent = `${roomCount}`;
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
    renderHomeNotifications();
}

function addNotification(msg) {
    if (isRoomMuted(msg.room)) {
        return;
    }
    const roomName = roomLabel(msg.room);
    const isGroup = Boolean(roomById(msg.room));
    state.notifications.unshift({
        room: msg.room,
        label: roomName,
        text: msg.text,
        ts: msg.ts,
        ip: isGroup ? '' : peerIp(msg.peer_id)
    });
    if (state.notifications.length > 6) {
        state.notifications.pop();
    }
    renderHomeNotifications();
}

function renderHomeNotifications() {
    if (!els.homeNotifications) return;
    const items = state.notifications.filter(
        note => !state.blockedPeers.has(note.room) && !isRoomMuted(note.room)
    );
    if (!items.length) {
        els.homeNotifications.innerHTML = '<div class="nav-empty">No new notifications</div>';
        return;
    }
    const grouped = new Map();
    items.forEach(note => {
        const key = note.ip || note.room || 'unknown';
        const existing = grouped.get(key);
        if (!existing) {
            grouped.set(key, { ...note, count: 1 });
        } else {
            existing.count += 1;
            if (typeof note.ts === 'number' && note.ts > (existing.ts || 0)) {
                existing.text = note.text;
                existing.ts = note.ts;
            }
            grouped.set(key, existing);
        }
    });
    els.homeNotifications.innerHTML = Array.from(grouped.values())
        .sort((a, b) => (b.ts || 0) - (a.ts || 0))
        .map(note => {
            const preview = String(note.text || '').slice(0, 48);
            const count = note.count > 1 ? ` (${note.count})` : '';
            return `<div class="summary-note"><strong>${note.label}${count}</strong><span>${preview}</span></div>`;
        })
        .join('');
}

function clearNotifications(roomId) {
    if (roomId === 'all') {
        state.notifications = [];
        renderHomeNotifications();
        return;
    }
    state.notifications = state.notifications.filter(note => note.room !== roomId);
    renderHomeNotifications();
}
