/* ================= API & Network ================= */

async function fetchState(force = false) {
    if (state.fetching) return;
    state.fetching = true;
    try {
        const res = await fetch(`/api/state?after=${force ? 0 : state.lastId}&room=${encodeURIComponent(state.room)}`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.me && data.me.id) {
            state.meId = data.me.id;
        }
        state.rooms = Array.isArray(data.rooms) ? data.rooms : [];
        state.peers = data.peers || [];
        renderNav(state.rooms, state.peers);
        const activeRoom = roomById(state.room);
        if (activeRoom && !activeRoom.joined && !activeRoom.pending) {
            switchRoom('all');
            return;
        }

        if (data.me) {
            if (data.me.id) {
                state.meId = data.me.id;
            }
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

        if (data.room_events && data.room_events.length) {
            handleRoomEvents(data.room_events);
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

        if (data.me && data.me.id) {
            state.meId = data.me.id;
        }
        if (Array.isArray(data.rooms)) {
            state.rooms = data.rooms;
        }
        state.peers = data.peers || state.peers;
        renderNav(state.rooms, state.peers);

        if (data.messages && data.messages.length) {
            data.messages.forEach(msg => {
                if (msg.direction !== 'in') return;
                const msgRoom = msg.room || msg.peer_id;
                if (msgRoom === state.room) return;
                state.unreadByRoom[msgRoom] = (state.unreadByRoom[msgRoom] || 0) + 1;
                addNotification(msg);
            });
            state.sidebarLastId = data.messages[data.messages.length - 1].id;
            updateUnreadTotals();
        }

        if (data.room_events && data.room_events.length) {
            handleRoomEvents(data.room_events);
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
    }).then(async res => {
        if (res.ok) return;
        try {
            const data = await res.json();
            showToast(data.error || 'Send failed');
        } catch (err) {
            showToast('Send failed');
        }
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
    if (file.size > MAX_UPLOAD_BYTES) {
        showToast(`File too large (max ${MAX_UPLOAD_LABEL})`);
        return;
    }
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

function handleRoomEvents(events) {
    events.forEach(event => {
        if (event.type === 'room_joined') {
            showToast(`Joined ${event.name || 'room'}`);
        } else if (event.type === 'room_join_denied') {
            showToast(event.reason || 'Join denied');
        } else if (event.type === 'room_discovered') {
            showToast(`New room: ${event.name || 'room'}`);
        } else if (event.type === 'room_kicked') {
            showToast(event.reason || 'Removed from room');
            if (event.room_id && state.room === event.room_id) {
                switchRoom('all');
            }
        }
    });
}

function openRoomModal(mode, room) {
    if (!els.roomModal) return;
    els.roomModal.dataset.mode = mode;
    els.roomModal.classList.remove('hidden');
    els.roomModal.setAttribute('aria-hidden', 'false');

    if (mode === 'create') {
        delete els.roomModal.dataset.roomId;
        if (els.roomModalTitle) els.roomModalTitle.textContent = 'Create room';
        if (els.roomModalSubmit) els.roomModalSubmit.textContent = 'Create room';
        if (els.roomCreateName) els.roomCreateName.value = '';
        if (els.roomCreatePassword) els.roomCreatePassword.value = '';
        if (els.roomCreateLimit) els.roomCreateLimit.value = '12';
        if (els.roomCreateDiscoverable) els.roomCreateDiscoverable.checked = true;
        if (els.roomCreateName) els.roomCreateName.focus();
        return;
    }

    if (mode === 'join' && room) {
        els.roomModal.dataset.roomId = room.id;
        if (els.roomModalTitle) els.roomModalTitle.textContent = 'Join room';
        if (els.roomModalSubmit) els.roomModalSubmit.textContent = 'Join room';
        if (els.roomJoinName) {
            els.roomJoinName.textContent = room.name || `Room ${room.id.substring(0, 6)}`;
        }
        if (els.roomJoinMeta) {
            const lockLabel = room.locked ? 'Locked room' : 'Open room';
            const count = room.member_count || 0;
            const limit = room.max_members ? ` / ${room.max_members}` : '';
            els.roomJoinMeta.textContent = `${lockLabel} · ${count}${limit} member(s)`;
        }
        if (els.roomJoinPassword) {
            els.roomJoinPassword.value = '';
            const field = els.roomJoinPassword.closest('.field');
            if (field) {
                field.classList.toggle('hidden', !room.locked);
            }
        }
        if (els.roomJoinPassword && room.locked) {
            els.roomJoinPassword.focus();
        }
    }
}

function closeRoomModal() {
    if (!els.roomModal) return;
    els.roomModal.classList.add('hidden');
    els.roomModal.setAttribute('aria-hidden', 'true');
    delete els.roomModal.dataset.mode;
    delete els.roomModal.dataset.roomId;
}

async function createRoom(payload) {
    const res = await fetch('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) {
        showToast(data.error || 'Room creation failed');
        return null;
    }
    if (data.room) {
        state.rooms = state.rooms.filter(room => room.id !== data.room.id).concat(data.room);
        renderNav(state.rooms, state.peers);
    }
    showToast('Room created');
    return data.room || null;
}

async function joinRoom(roomId, password) {
    const res = await fetch('/api/rooms/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room_id: roomId, password })
    });
    const data = await res.json();
    if (!res.ok) {
        showToast(data.error || 'Join failed');
        return;
    }
    const room = roomById(roomId);
    if (room) {
        room.pending = true;
        renderNav(state.rooms, state.peers);
    }
    showToast('Join request sent');
}

async function leaveRoom(roomId) {
    const res = await fetch('/api/rooms/leave', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room_id: roomId })
    });
    const data = await res.json();
    if (!res.ok) {
        showToast(data.error || 'Leave failed');
        return;
    }
    const room = roomById(roomId);
    if (room) {
        room.joined = false;
        room.pending = false;
    }
    state.unreadByRoom[roomId] = 0;
    updateUnreadTotals();
    if (state.room === roomId) {
        switchRoom('all');
    } else {
        renderNav(state.rooms, state.peers);
    }
    showToast('Left room');
}

async function kickMember(roomId, memberId) {
    const res = await fetch('/api/rooms/kick', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room_id: roomId, member_id: memberId })
    });
    const data = await res.json();
    if (!res.ok) {
        showToast(data.error || 'Kick failed');
        return;
    }
    await fetchState(true);
    showToast('Member removed');
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
