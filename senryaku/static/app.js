// Sidebar toggle
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    sidebar.classList.toggle('-translate-x-full');
    overlay.classList.toggle('hidden');
}

// Close sidebar on nav link click (mobile only)
document.addEventListener('DOMContentLoaded', function() {
    const sidebarLinks = document.querySelectorAll('.sidebar-link');
    sidebarLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            // Only toggle on mobile (when sidebar is in fixed position)
            if (window.innerWidth < 1024) {
                const sidebar = document.getElementById('sidebar');
                if (!sidebar.classList.contains('-translate-x-full')) {
                    toggleSidebar();
                }
            }
        });
    });
});

// Close modal — clears modal container by removing all child nodes
function closeModal() {
    const container = document.getElementById('modal-container');
    while (container.firstChild) {
        container.removeChild(container.firstChild);
    }
    document.body.classList.remove('modal-open');
}

// Watch for modal content being added (via HTMX) and lock body scroll
const modalObserver = new MutationObserver(function(mutations) {
    const container = document.getElementById('modal-container');
    if (container && container.children.length > 0) {
        document.body.classList.add('modal-open');
    }
});
document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('modal-container');
    if (container) {
        modalObserver.observe(container, { childList: true });
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

// Timer functionality (used in sortie focus view)
let timerInterval = null;
let timerSeconds = 0;

function startTimer(durationMinutes) {
    timerSeconds = durationMinutes * 60;
    updateTimerDisplay();
    timerInterval = setInterval(() => {
        timerSeconds--;
        if (timerSeconds <= 0) {
            clearInterval(timerInterval);
            timerSeconds = 0;
        }
        updateTimerDisplay();

        // Micro-break reminders at 30 and 60 minutes elapsed
        const elapsed = (durationMinutes * 60) - timerSeconds;
        if (elapsed === 30 * 60 || elapsed === 60 * 60) {
            showBreakReminder();
        }
    }, 1000);
}

function updateTimerDisplay() {
    const display = document.getElementById('timer-display');
    if (!display) return;
    const mins = Math.floor(timerSeconds / 60);
    const secs = timerSeconds % 60;
    display.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

    // Color changes based on time remaining
    if (timerSeconds <= 300) {  // Last 5 minutes
        display.classList.add('text-red-400');
    } else if (timerSeconds <= 900) {  // Last 15 minutes
        display.classList.add('text-yellow-400');
    }
}

function showBreakReminder() {
    const reminder = document.createElement('div');
    reminder.className = 'fixed top-4 right-4 bg-indigo-600 text-white px-4 py-3 rounded-lg shadow-lg z-50 transition-opacity duration-500';
    reminder.textContent = 'Time for a micro-break — stretch, breathe, refocus.';
    document.body.appendChild(reminder);
    setTimeout(() => {
        reminder.style.opacity = '0';
        setTimeout(() => reminder.remove(), 500);
    }, 5000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

// ---------------------------------------------------------------------------
// Campaign reranking via drag-and-drop (SortableJS)
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', function() {
    initSortable();
});

// Re-init after HTMX swaps
document.addEventListener('htmx:afterSettle', function() {
    initSortable();
});

function initSortable() {
    const list = document.querySelector('[data-sortable="true"]');
    if (!list || list.sortableInstance) return;

    const apiKey = document.querySelector('meta[name="api-key"]')?.content || '';

    list.sortableInstance = new Sortable(list, {
        animation: 150,
        ghostClass: 'opacity-50',
        handle: '.campaign-accent',
        onEnd: function() {
            const cards = list.querySelectorAll('[data-campaign-id]');
            const ranks = [];
            cards.forEach(function(card, index) {
                ranks.push({
                    id: card.dataset.campaignId,
                    rank: index + 1,
                });
            });

            fetch('/api/v1/campaigns/rerank', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': apiKey,
                },
                body: JSON.stringify({ ranks: ranks }),
            }).then(function(response) {
                if (response.ok) {
                    htmx.ajax('GET', '/dashboard', {target: '#main-content', swap: 'innerHTML'});
                }
            });
        }
    });
}
