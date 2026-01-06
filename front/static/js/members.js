/* ================= Members ================= */

function renderMembers(room) {
    if (!els.membersSection || !els.membersList) return;
    hideMemberPopover();
    if (!room || state.room === 'all') {
        els.membersSection.classList.add('hidden');
        els.membersList.innerHTML = '';
        if (els.membersCount) {
            els.membersCount.textContent = '0';
        }
        return;
    }

    els.membersSection.classList.toggle('hidden', false);
    const members = Array.isArray(room.members) ? room.members : [];
    const count = members.length || room.member_count || 0;
    if (els.membersCount) {
        els.membersCount.textContent = `${count}`;
    }
    if (!room.joined) {
        els.membersList.innerHTML = '<div class="nav-empty">Join the room to view members</div>';
        return;
    }
    if (!members.length) {
        els.membersList.innerHTML = '<div class="nav-empty">No members listed</div>';
        return;
    }

    const items = members.map(memberId => {
        const isOwner = memberId === room.owner_id;
        const isSelf = memberId === state.meId;
        const label = isSelf ? 'You' : peerLabel(memberId);
        const shortId = `${memberId.substring(0, 8)}...`;
        const ownerTag = isOwner ? '<span class="member-tag owner">Owner</span>' : '';
        const kickButton = room.is_owner && !isSelf
            ? `<button class="member-action" type="button" data-member="${memberId}">Kick</button>`
            : '';
        const itemClass = `member-item${isSelf ? ' self' : ''}`;
        return `<div class="${itemClass}" data-member="${memberId}">` +
            `<div class="member-avatar">${ICONS.USER}</div>` +
            `<div class="member-info">` +
            `<div class="member-name">${label}</div>` +
            `<div class="member-meta"><span class="mono">${shortId}</span>${ownerTag}</div>` +
            `</div>` +
            `${kickButton}` +
            `</div>`;
    });
    els.membersList.innerHTML = items.join('');

    els.membersList.querySelectorAll('.member-item').forEach(item => {
        item.addEventListener('click', e => {
            e.stopPropagation();
            const memberId = item.dataset.member;
            if (!memberId || memberId === state.meId) return;
            showMemberPopover(memberId, room, item);
        });
    });

    if (room.is_owner) {
        els.membersList.querySelectorAll('.member-action').forEach(button => {
            button.addEventListener('click', async e => {
                e.stopPropagation();
                const memberId = button.dataset.member;
                if (!memberId) return;
                if (!confirm(`Remove ${peerLabel(memberId)} from this room?`)) return;
                await kickMember(room.id, memberId);
            });
        });
    }
}

function showMemberPopover(memberId, room, anchor) {
    if (!els.memberPopover || !els.memberPopoverName || !els.memberPopoverId) return;
    els.memberPopoverName.textContent = peerLabel(memberId);
    els.memberPopoverId.textContent = memberId;
    els.memberPopover.dataset.memberId = memberId;
    els.memberPopover.dataset.roomId = room.id;
    if (els.memberPopoverKick) {
        const canKick = room.is_owner && memberId !== state.meId;
        els.memberPopoverKick.classList.toggle('hidden', !canKick);
    }
    els.memberPopover.classList.remove('hidden');
    els.memberPopover.setAttribute('aria-hidden', 'false');

    const rect = anchor.getBoundingClientRect();
    requestAnimationFrame(() => {
        const popRect = els.memberPopover.getBoundingClientRect();
        let top = rect.bottom + 8;
        if (top + popRect.height > window.innerHeight - 8) {
            top = rect.top - popRect.height - 8;
        }
        let left = rect.left;
        if (left + popRect.width > window.innerWidth - 8) {
            left = window.innerWidth - popRect.width - 8;
        }
        if (left < 8) {
            left = 8;
        }
        if (top < 8) {
            top = 8;
        }
        els.memberPopover.style.top = `${top}px`;
        els.memberPopover.style.left = `${left}px`;
    });
}

function hideMemberPopover() {
    if (!els.memberPopover) return;
    els.memberPopover.classList.add('hidden');
    els.memberPopover.setAttribute('aria-hidden', 'true');
    delete els.memberPopover.dataset.memberId;
    delete els.memberPopover.dataset.roomId;
}
