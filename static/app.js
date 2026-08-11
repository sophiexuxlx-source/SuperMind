document.addEventListener("DOMContentLoaded", () => {
    const messagesContainer = document.getElementById("messages-container");
    const chatForm = document.getElementById("chat-form");
    const promptInput = document.getElementById("prompt-input");
    const modelSelect = document.getElementById("model-select");
    const clearChatBtn = document.getElementById("clear-chat-btn");
    const newChatBtn = document.getElementById("new-chat-btn");
    const historyList = document.getElementById("history-list");

    // Image Attachment Elements
    const attachBtn = document.getElementById("attach-btn");
    const fileInput = document.getElementById("file-input");
    const imagePreviewBar = document.getElementById("image-preview-bar");
    const previewImg = document.getElementById("preview-img");
    const removeImgBtn = document.getElementById("remove-img-btn");

    let currentImageData = null; // Base64 data URL
    let currentChatId = Date.now().toString();
    let currentChatMessages = [];
    let chatsHistory = JSON.parse(localStorage.getItem("supermind_chats_history") || "[]");

    // Configure marked for Markdown rendering
    if (typeof marked !== "undefined") {
        marked.setOptions({
            breaks: true,
            gfm: true
        });
    }

    // Initialize UI
    renderHistoryPanel();

    // New Chat Button Handler
    newChatBtn.addEventListener("click", startNewChat);

    function startNewChat() {
        if (currentChatMessages.length > 0) {
            saveCurrentChatToHistory();
        }
        currentChatId = Date.now().toString();
        currentChatMessages = [];
        messagesContainer.innerHTML = `
            <div class="welcome-card">
                <div class="welcome-icon">✨</div>
                <h3>Welcome to SuperMind Core Agentic Engine</h3>
                <p>Experience an AI system equipped with autonomous tool calling, multi-step reasoning, and live Web Search.</p>
            </div>
        `;
        clearImagePreview();
        renderHistoryPanel();
    }

    // Save Chat to LocalStorage
    function saveCurrentChatToHistory() {
        if (currentChatMessages.length === 0) return;
        
        const firstUserMsg = currentChatMessages.find(m => m.role === "user");
        const title = firstUserMsg ? firstUserMsg.content.slice(0, 30) : "Chat Session";

        const existingIdx = chatsHistory.findIndex(c => c.id === currentChatId);
        const chatData = {
            id: currentChatId,
            title: title,
            messages: currentChatMessages,
            timestamp: new Date().toISOString()
        };

        if (existingIdx >= 0) {
            chatsHistory[existingIdx] = chatData;
        } else {
            chatsHistory.unshift(chatData);
        }

        if (chatsHistory.length > 20) chatsHistory.pop();

        localStorage.setItem("supermind_chats_history", JSON.stringify(chatsHistory));
        renderHistoryPanel();
    }

    // Render Chat History Sidebar Panel
    function renderHistoryPanel() {
        if (!historyList) return;
        historyList.innerHTML = "";

        if (chatsHistory.length === 0) {
            historyList.innerHTML = `<div style="font-size: 0.75rem; color: var(--text-secondary); text-align: center; padding: 0.5rem;">No saved history</div>`;
            return;
        }

        chatsHistory.forEach(chat => {
            const item = document.createElement("div");
            item.className = `history-item ${chat.id === currentChatId ? "active" : ""}`;
            
            const titleSpan = document.createElement("span");
            titleSpan.className = "history-title";
            titleSpan.textContent = "💬 " + (chat.title || "Untitled Chat");
            titleSpan.addEventListener("click", () => loadChatSession(chat.id));

            const delBtn = document.createElement("button");
            delBtn.className = "delete-history-btn";
            delBtn.innerHTML = "✕";
            delBtn.title = "Delete Chat";
            delBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                deleteChatSession(chat.id);
            });

            item.appendChild(titleSpan);
            item.appendChild(delBtn);
            historyList.appendChild(item);
        });
    }

    // Load Chat Session from History
    function loadChatSession(id) {
        const targetChat = chatsHistory.find(c => c.id === id);
        if (!targetChat) return;

        currentChatId = targetChat.id;
        currentChatMessages = targetChat.messages || [];

        renderChatView();
        renderHistoryPanel();
    }

    // Delete Chat Session
    function deleteChatSession(id) {
        chatsHistory = chatsHistory.filter(c => c.id !== id);
        localStorage.setItem("supermind_chats_history", JSON.stringify(chatsHistory));
        if (currentChatId === id) {
            startNewChat();
        } else {
            renderHistoryPanel();
        }
    }

    // Attachment & Paste Handlers
    attachBtn.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file && file.type.startsWith("image/")) {
            loadImageFile(file);
        }
    });

    removeImgBtn.addEventListener("click", clearImagePreview);

    document.addEventListener("paste", (e) => {
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        for (let index in items) {
            const item = items[index];
            if (item.kind === "file" && item.type.startsWith("image/")) {
                const blob = item.getAsFile();
                loadImageFile(blob);
                break;
            }
        }
    });

    function loadImageFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            currentImageData = e.target.result;
            previewImg.src = currentImageData;
            imagePreviewBar.classList.remove("hidden");
        };
        reader.readAsDataURL(file);
    }

    function clearImagePreview() {
        currentImageData = null;
        previewImg.src = "";
        imagePreviewBar.classList.add("hidden");
        fileInput.value = "";
    }

    // Clear Current Chat
    clearChatBtn.addEventListener("click", () => {
        startNewChat();
    });

    // Auto-resize textarea
    promptInput.addEventListener("input", () => {
        promptInput.style.height = "auto";
        promptInput.style.height = Math.min(promptInput.scrollHeight, 120) + "px";
    });

    // Handle Enter key submit
    promptInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event("submit"));
        }
    });

    // Submit Chat Form
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const promptText = promptInput.value.trim() || (currentImageData ? "Please analyze this image." : "");
        if (!promptText && !currentImageData) return;

        const sentImageData = currentImageData;

        const welcomeCard = messagesContainer.querySelector(".welcome-card");
        if (welcomeCard) welcomeCard.remove();

        appendMessage("user", promptText, sentImageData);
        currentChatMessages.push({ role: "user", content: promptText, imageData: sentImageData });

        promptInput.value = "";
        promptInput.style.height = "auto";
        clearImagePreview();

        await triggerRegenerate(promptText, sentImageData);
    });

    function renderChatView() {
        messagesContainer.innerHTML = "";
        if (currentChatMessages.length === 0) {
            messagesContainer.innerHTML = `
                <div class="welcome-card">
                    <div class="welcome-icon">✨</div>
                    <h3>Welcome to SuperMind Core Agentic Engine</h3>
                    <p>Experience an AI system equipped with autonomous tool calling, multi-step reasoning, and live Web Search.</p>
                </div>
            `;
            return;
        }
        currentChatMessages.forEach((msg, idx) => {
            appendMessage(msg.role, msg.content, msg.imageData, false, msg.toolTraces, idx);
        });
    }

    async function triggerRegenerate(promptText, sentImageData) {
        const assistantMsgDiv = appendMessage("assistant", "", null, true);
        const bubbleDiv = assistantMsgDiv.querySelector(".message-bubble");

        const endpoint = "/agent/chat"; // Always use Agentic Engine
        const selectedModel = modelSelect.value;

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    prompt: promptText,
                    model: selectedModel,
                    image_data: sentImageData
                })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(errData.detail || "Request failed");
            }

            const data = await response.json();

            bubbleDiv.innerHTML = "";

            if (data.tool_calls_executed && data.tool_calls_executed.length > 0) {
                data.tool_calls_executed.forEach(trace => {
                    const toolCard = document.createElement("div");
                    toolCard.className = "tool-trace-card";
                    toolCard.innerHTML = `
                        <div class="tool-header">
                            <span class="badge-icon">🔍 TOOL EXECUTED</span>
                            <span>${trace.tool_name}(${JSON.stringify(trace.arguments)})</span>
                        </div>
                        <div class="tool-snippet">${escapeHtml(trace.output_snippet)}</div>
                    `;
                    bubbleDiv.appendChild(toolCard);
                });
            }

            const contentDiv = document.createElement("div");
            contentDiv.className = "markdown-content";
            if (typeof marked !== "undefined") {
                contentDiv.innerHTML = marked.parse(data.reply);
            } else {
                contentDiv.textContent = data.reply;
            }
            bubbleDiv.appendChild(contentDiv);

            currentChatMessages.push({ 
                role: "assistant", 
                content: data.reply, 
                toolTraces: data.tool_calls_executed || [] 
            });

            saveCurrentChatToHistory();

        } catch (err) {
            bubbleDiv.innerHTML = `<span style="color: #ef4444;">⚠️ Error: ${escapeHtml(err.message)}</span>`;
        }

        scrollToBottom();
    }

    function appendMessage(role, content, imageData = null, isLoading = false, toolTraces = [], msgIdx = -1) {
        const row = document.createElement("div");
        row.className = `message-row ${role}`;

        const avatar = document.createElement("div");
        avatar.className = "avatar";
        avatar.textContent = role === "user" ? "👤" : "🤖";

        const bubble = document.createElement("div");
        bubble.className = "message-bubble";

        if (isLoading) {
            bubble.innerHTML = `
                <div class="thinking-card">
                    <span class="brain-pulse">🤖</span>
                    <span>SuperMind is thinking & searching...</span>
                    <div class="typing-dots">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            `;
        } else {
            if (role === "user") {
                if (content) {
                    const textP = document.createElement("p");
                    textP.textContent = content;
                    bubble.appendChild(textP);
                }
                if (imageData) {
                    const img = document.createElement("img");
                    img.src = imageData;
                    img.className = "message-image";
                    bubble.appendChild(img);
                }
            } else {
                if (toolTraces && toolTraces.length > 0) {
                    toolTraces.forEach(trace => {
                        const toolCard = document.createElement("div");
                        toolCard.className = "tool-trace-card";
                        toolCard.innerHTML = `
                            <div class="tool-header">
                                <span class="badge-icon">🔍 TOOL EXECUTED</span>
                                <span>${trace.tool_name}(${JSON.stringify(trace.arguments)})</span>
                            </div>
                            <div class="tool-snippet">${escapeHtml(trace.output_snippet)}</div>
                        `;
                        bubble.appendChild(toolCard);
                    });
                }
                const contentDiv = document.createElement("div");
                contentDiv.className = "markdown-content";
                contentDiv.innerHTML = typeof marked !== "undefined" ? marked.parse(content) : escapeHtml(content);
                bubble.appendChild(contentDiv);
            }
        }

        if (role === "user") {
            row.appendChild(bubble);
            row.appendChild(avatar);

            if (!isLoading) {
                const editBtn = document.createElement("button");
                editBtn.className = "edit-msg-btn";
                editBtn.innerHTML = "✏️";
                editBtn.title = "Edit prompt";

                editBtn.addEventListener("click", () => {
                    bubble.innerHTML = `
                        <div class="inline-edit-box">
                            <textarea class="inline-edit-textarea">${escapeHtml(content)}</textarea>
                            <div class="inline-edit-actions">
                                <button type="button" class="cancel-edit-btn">Cancel</button>
                                <button type="button" class="save-edit-btn">Save & Regenerate</button>
                            </div>
                        </div>
                    `;

                    const cancelBtn = bubble.querySelector(".cancel-edit-btn");
                    const saveBtn = bubble.querySelector(".save-edit-btn");
                    const textarea = bubble.querySelector(".inline-edit-textarea");
                    textarea.focus();

                    cancelBtn.addEventListener("click", () => {
                        renderChatView();
                    });

                    saveBtn.addEventListener("click", async () => {
                        const newPrompt = textarea.value.trim();
                        if (!newPrompt) return;

                        const targetIdx = msgIdx >= 0 ? msgIdx : currentChatMessages.findIndex(m => m.role === "user" && m.content === content);
                        if (targetIdx >= 0) {
                            currentChatMessages = currentChatMessages.slice(0, targetIdx);
                            currentChatMessages.push({ role: "user", content: newPrompt, imageData: imageData });
                            renderChatView();
                            await triggerRegenerate(newPrompt, imageData);
                        }
                    });
                });

                row.appendChild(editBtn);
            }
        } else {
            row.appendChild(avatar);
            row.appendChild(bubble);
        }

        messagesContainer.appendChild(row);
        scrollToBottom();
        return row;
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function escapeHtml(str) {
        return str.replace(/[&<>"']/g, function(m) {
            return {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            }[m];
        });
    }
});
