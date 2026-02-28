function updateApp(el) {
    const id = el.dataset.id;
    const field = el.dataset.field;
    let value;

    if (el.type === "checkbox") {
        value = el.checked ? 1 : 0;
    } else {
        value = el.value;
    }

    fetch(`/tracker/update/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: value })
    });
}

function deleteApp(id) {
    if (!confirm("Remove this application?")) return;
    fetch(`/tracker/delete/${id}`, { method: "POST" })
        .then(() => {
            const row = document.getElementById(`app-${id}`);
            if (row) row.remove();
        });
}
