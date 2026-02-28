// Sidebar toggle for mobile
document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector(".menu-toggle");
    const sidebar = document.querySelector(".sidebar");

    if (toggle) {
        toggle.addEventListener("click", () => {
            sidebar.classList.toggle("open");
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener("click", (e) => {
            if (sidebar.classList.contains("open") &&
                !sidebar.contains(e.target) &&
                !toggle.contains(e.target)) {
                sidebar.classList.remove("open");
            }
        });
    }

    // Check LLM status on pages that need it
    const llmBanner = document.getElementById("llm-banner");
    if (llmBanner) {
        fetch("/api/llm-status")
            .then(r => r.json())
            .then(data => {
                if (!data.available) {
                    llmBanner.style.display = "block";
                }
            })
            .catch(() => {
                llmBanner.style.display = "block";
            });
    }
});

// Flash messages
function showFlash(message, type = "success") {
    const flash = document.createElement("div");
    flash.className = `banner banner-${type}`;
    flash.textContent = message;
    flash.style.position = "fixed";
    flash.style.top = "1rem";
    flash.style.right = "1rem";
    flash.style.zIndex = "300";
    flash.style.minWidth = "200px";
    document.body.appendChild(flash);
    setTimeout(() => flash.remove(), 3000);
}
