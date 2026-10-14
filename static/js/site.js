const mobileMenu = document.getElementById("mobileMenu");
const sidebar = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebarOverlay");

if (mobileMenu && sidebar && sidebarOverlay) {
    mobileMenu.addEventListener("click", function () {
        const isOpen = sidebar.classList.toggle("mobile-open");
        sidebarOverlay.classList.toggle("mobile-open", isOpen);
        mobileMenu.setAttribute("aria-expanded", String(isOpen));
        mobileMenu.setAttribute("aria-label", isOpen ? "Close navigation menu" : "Open navigation menu");
    });
}

if (sidebar && sidebarOverlay) {
    sidebarOverlay.addEventListener("click", function () {
        sidebar.classList.remove("mobile-open");
        sidebarOverlay.classList.remove("mobile-open");
        if (mobileMenu) {
            mobileMenu.setAttribute("aria-expanded", "false");
            mobileMenu.setAttribute("aria-label", "Open navigation menu");
        }
    });
}

if (sidebar && mobileMenu) {
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && sidebar.classList.contains("mobile-open")) {
            sidebar.classList.remove("mobile-open");
            if (sidebarOverlay) sidebarOverlay.classList.remove("mobile-open");
            mobileMenu.setAttribute("aria-expanded", "false");
            mobileMenu.setAttribute("aria-label", "Open navigation menu");
            mobileMenu.focus();
        }
    });

    sidebar.querySelectorAll("a").forEach(function (link) {
        link.addEventListener("click", function () {
            sidebar.classList.remove("mobile-open");
            if (sidebarOverlay) sidebarOverlay.classList.remove("mobile-open");
            mobileMenu.setAttribute("aria-expanded", "false");
            mobileMenu.setAttribute("aria-label", "Open navigation menu");
        });
    });
}

document.addEventListener("submit", function (event) {
    const submitter = event.submitter;
    if (!submitter || !submitter.dataset.confirm) {
        return;
    }
    if (!window.confirm(submitter.dataset.confirm)) {
        event.preventDefault();
    }
});
