// Sidebar toggle
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    sidebar.classList.toggle('-translate-x-full');
    overlay.classList.toggle('hidden');
}

// Close modal — clears modal container by removing all child nodes
function closeModal() {
    const container = document.getElementById('modal-container');
    while (container.firstChild) {
        container.removeChild(container.firstChild);
    }
}

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
