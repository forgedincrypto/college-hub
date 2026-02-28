let currentConversation = null;
let isStreaming = false;

function setInputEnabled(enabled) {
    document.getElementById("chat-input").disabled = !enabled;
    document.getElementById("send-btn").disabled = !enabled;
}

function scrollToBottom() {
    const container = document.getElementById("chat-messages");
    container.scrollTop = container.scrollHeight;
}

function appendMessage(role, content) {
    const container = document.getElementById("chat-messages");
    document.getElementById("chat-empty").style.display = "none";

    const div = document.createElement("div");
    div.className = `message message-${role}`;
    div.textContent = content;
    container.appendChild(div);
    scrollToBottom();
    return div;
}

async function newConversation() {
    const res = await fetch("/chat/new", { method: "POST" });
    const data = await res.json();
    currentConversation = data.id;

    // Add to sidebar
    const list = document.getElementById("chat-list");
    const item = document.createElement("div");
    item.className = "chat-list-item active";
    item.dataset.id = data.id;
    item.onclick = () => loadConversation(data.id);
    item.innerHTML = `<span class="chat-title">New Conversation</span>
        <button class="btn-icon" onclick="event.stopPropagation(); deleteConversation(${data.id})">&times;</button>`;
    list.prepend(item);

    // Clear active states
    document.querySelectorAll(".chat-list-item").forEach(el => {
        if (el !== item) el.classList.remove("active");
    });

    // Clear messages
    const messages = document.getElementById("chat-messages");
    messages.innerHTML = "";
    document.getElementById("chat-empty").style.display = "none";

    setInputEnabled(true);
    document.getElementById("chat-input").focus();
}

async function loadConversation(id) {
    currentConversation = id;

    // Update active state
    document.querySelectorAll(".chat-list-item").forEach(el => {
        el.classList.toggle("active", el.dataset.id == id);
    });

    // Load messages
    const res = await fetch(`/chat/${id}/messages`);
    const messages = await res.json();

    const container = document.getElementById("chat-messages");
    container.innerHTML = "";

    if (messages.length === 0) {
        document.getElementById("chat-empty").style.display = "flex";
        container.appendChild(document.getElementById("chat-empty") || createEmptyState());
    } else {
        const empty = document.getElementById("chat-empty");
        if (empty) empty.style.display = "none";

        for (const msg of messages) {
            if (msg.role === "system") continue;
            appendMessage(msg.role, msg.content);
        }
    }

    setInputEnabled(true);
    document.getElementById("chat-input").focus();
}

async function sendMessage() {
    if (!currentConversation || isStreaming) return;

    const input = document.getElementById("chat-input");
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    appendMessage("user", message);
    isStreaming = true;
    setInputEnabled(false);

    // Create assistant message placeholder
    const assistantDiv = appendMessage("assistant", "");
    let fullText = "";

    try {
        const res = await fetch(`/chat/${currentConversation}/send`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message })
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value);
            const lines = text.split("\n");

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const payload = line.slice(6).trim();

                if (payload === "[DONE]") continue;

                try {
                    const data = JSON.parse(payload);
                    if (data.token) {
                        fullText += data.token;
                        assistantDiv.textContent = fullText;
                        scrollToBottom();
                    }
                    if (data.title) {
                        // Update conversation title in sidebar
                        const item = document.querySelector(`.chat-list-item[data-id="${currentConversation}"]`);
                        if (item) {
                            item.querySelector(".chat-title").textContent = data.title;
                        }
                    }
                    if (data.error) {
                        fullText += "\n\n[Error: " + data.error + "]";
                        assistantDiv.textContent = fullText;
                    }
                } catch (e) {
                    // Skip unparseable lines
                }
            }
        }
    } catch (err) {
        assistantDiv.textContent = "Failed to connect. Is Ollama running?";
    }

    isStreaming = false;
    setInputEnabled(true);
    document.getElementById("chat-input").focus();
}

async function deleteConversation(id) {
    if (!confirm("Delete this conversation?")) return;
    await fetch(`/chat/${id}/delete`, { method: "POST" });

    const item = document.querySelector(`.chat-list-item[data-id="${id}"]`);
    if (item) item.remove();

    if (currentConversation === id) {
        currentConversation = null;
        document.getElementById("chat-messages").innerHTML = "";
        const empty = document.getElementById("chat-empty");
        if (empty) empty.style.display = "flex";
        setInputEnabled(false);
    }
}
