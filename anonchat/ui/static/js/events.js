/* ================= Events & Init ================= */

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

if (els.muteRoomBtn) {
    els.muteRoomBtn.addEventListener('click', () => {
        if (state.room === 'all') return;
        if (isRoomMuted(state.room)) {
            state.mutedRooms.delete(state.room);
            showToast('Unmuted room');
        } else {
            state.mutedRooms.add(state.room);
            showToast('Room muted');
        }
        saveMutedRooms();
        updateRoomActionUI();
        renderNav(state.rooms, state.peers);
    });
}

if (els.markReadBtn) {
    els.markReadBtn.addEventListener('click', () => {
        if (state.room === 'all') {
            clearUnread('all');
            renderNav(state.rooms, state.peers);
            showToast('All caught up');
            return;
        }
        clearUnread(state.room);
        resetUnread();
        renderNav(state.rooms, state.peers);
        showToast('Marked read');
    });
}

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

if (els.memberPopoverMessage) {
    els.memberPopoverMessage.addEventListener('click', () => {
        const memberId = els.memberPopover && els.memberPopover.dataset.memberId;
        if (!memberId) return;
        hideMemberPopover();
        switchRoom(memberId);
    });
}

if (els.memberPopoverKick) {
    els.memberPopoverKick.addEventListener('click', async () => {
        const memberId = els.memberPopover && els.memberPopover.dataset.memberId;
        const roomId = els.memberPopover && els.memberPopover.dataset.roomId;
        if (!memberId || !roomId) return;
        hideMemberPopover();
        if (!confirm(`Remove ${peerLabel(memberId)} from this room?`)) return;
        await kickMember(roomId, memberId);
    });
}

document.addEventListener('click', e => {
    if (!els.memberPopover || els.memberPopover.classList.contains('hidden')) return;
    if (els.memberPopover.contains(e.target)) return;
    if (e.target.closest('.member-item')) return;
    hideMemberPopover();
});

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        hideMemberPopover();
    }
});

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
        openRoomModal('create');
    });
}

if (els.sidebarSettings) {
    els.sidebarSettings.addEventListener('click', () => {
        switchRoom('all');
        if (els.homeSummary) {
            els.homeSummary.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
}

if (els.roomModalClose) {
    els.roomModalClose.addEventListener('click', closeRoomModal);
}

if (els.roomModalCancel) {
    els.roomModalCancel.addEventListener('click', closeRoomModal);
}

if (els.roomModalSubmit) {
    els.roomModalSubmit.addEventListener('click', async () => {
        if (!els.roomModal) return;
        const mode = els.roomModal.dataset.mode;
        if (mode === 'create') {
            const name = (els.roomCreateName && els.roomCreateName.value || '').trim();
            const password = (els.roomCreatePassword && els.roomCreatePassword.value || '').trim();
            const limitValue = els.roomCreateLimit ? els.roomCreateLimit.value : '';
            const maxMembers = parseInt(limitValue, 10);
            const discoverable = Boolean(els.roomCreateDiscoverable && els.roomCreateDiscoverable.checked);
            if (!name) {
                showToast('Room name required');
                return;
            }
            const room = await createRoom({
                name,
                password,
                max_members: Number.isFinite(maxMembers) ? maxMembers : 0,
                discoverable
            });
            if (room && room.id) {
                closeRoomModal();
                switchRoom(room.id);
            }
            return;
        }

        if (mode === 'join') {
            const roomId = els.roomModal.dataset.roomId;
            if (!roomId) return;
            const password = (els.roomJoinPassword && els.roomJoinPassword.value || '').trim();
            await joinRoom(roomId, password);
            closeRoomModal();
        }
    });
}

if (els.roomModal) {
    els.roomModal.addEventListener('click', e => {
        if (e.target === els.roomModal) {
            closeRoomModal();
        }
    });
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && els.roomModal && !els.roomModal.classList.contains('hidden')) {
        closeRoomModal();
    }
});

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
loadBlockedPeers();
loadMutedRooms();
updateRoomActionUI();
renderNav(state.rooms, state.peers);
loadInterfaces();
setInterval(fetchSidebarState, 2000);
setInterval(fetchState, 1000);
fetchState(true);
