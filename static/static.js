async function loadMessages(filter = 'All') {
    const container = document.getElementById('messageContainer');
    if(!container) return;
    
    try {
        const response = await fetch('/api/messages');
        const result = await response.json();
        
        if (result.status === 'success') {
            container.innerHTML = '';
            const messages = result.data;

            const filteredMessages = filter === 'All' 
                ? messages 
                : messages.filter(msg => msg.platform === filter);

            if (filteredMessages.length === 0) {
                container.innerHTML = '<p style="color:#94a3b8;">No messages found.</p>';
                return;
            }

            filteredMessages.forEach(msg => {
                const card = document.createElement('div');
                card.className = 'msg-card';
                card.style.cssText = "background:#1f2937; padding:12px; margin-bottom:10px; border-radius:8px;";
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between;">
                        <strong style="color:#38bdf8;">[${msg.platform}] ${msg.sender}</strong>
                        <small style="color:#94a3b8;">${msg.timestamp}</small>
                    </div>
                    <p style="color:#e2e8f0; margin-top:5px;">${msg.message}</p>
                `;
                container.appendChild(card);
            });
        }
    } catch (error) {
        console.error("Error loading messages:", error);
    }
}

async function sendTestMessage() {
    const input = document.getElementById('testMsg');
    if(!input) return;
    const msg = input.value.trim();

    if (!msg) {
        alert("Please enter a message!");
        return;
    }

    try {
        const response = await fetch('/api/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                platform: 'Web',
                sender: 'Me (Test)',
                message: msg
            })
        });

        const result = await response.json();
        if(result.status === 'success') {
            input.value = '';
            loadMessages(); // Reload message feed
        }
    } catch (error) {
        alert("Failed to send message. Check if app.py is running!");
    }
}

window.onload = () => {
    loadMessages('All');
};