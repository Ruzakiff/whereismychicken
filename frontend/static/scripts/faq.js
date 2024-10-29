function showInfo() {
    const modal = document.getElementById('infoModal');
    const content = modal.querySelector('.modal-content');
    modal.style.display = 'block';
    content.offsetHeight; // Trigger reflow
    content.classList.add('show');
}

function hideInfo() {
    const modal = document.getElementById('infoModal');
    const content = modal.querySelector('.modal-content');
    content.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 300);
}

// Close modal when clicking overlay
document.getElementById('infoModal').addEventListener('click', function(e) {
    if (e.target === this) {
        hideInfo();
    }
});