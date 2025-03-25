// Completing the handleSendMessage function
function handleSendMessage(e) {
    e.preventDefault();
    
    const messageText = messageInput.value.trim();
    if (!messageText || isWaitingForResponse || !currentConversationId) return;
    
    // Disable input and show loading state
    messageInput.disabled = true;
    isWaitingForResponse = true;
    updateStatus('Thinking...', 'loading');
    
    // Add user message to UI immediately
    addMessage({
        role: 'user',
        content: messageText,
        timestamp: new Date().toISOString()
    });
    
    // Clear input and reset height
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    // Send message to server
    fetch(`/chat/${currentConversationId}/message`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': '{{ g.csrf_token }}'
        },
        body: JSON.stringify({ message: messageText })
    })
    .then(response => response.json())
    .then(data => {
        // Re-enable input
        messageInput.disabled = false;
        isWaitingForResponse = false;
        
        if (data.status === 'success') {
            // Add AI response to UI
            addMessage(data.message);
            
            // Update conversation title if it's still default
            if (chatTitle.textContent === 'New Conversation') {
                // Extract a title from first few words of user message
                const words = messageText.split(' ');
                if (words.length > 2) {
                    const newTitle = words.slice(0, 5).join(' ') + '...';
                    chatTitle.textContent = newTitle;
                    
                    // Update in sidebar too
                    const conversationItem = document.querySelector(`.conversation-item[data-id="${currentConversationId}"]`);
                    if (conversationItem) {
                        const titleElement = conversationItem.querySelector('.conversation-title');
                        if (titleElement) {
                            titleElement.textContent = newTitle;
                        }
                    }
                }
            }
            
            // Enable feedback button after a few messages
            const messageCount = document.querySelectorAll('.message').length;
            if (messageCount >= 4) {
                feedbackBtn.disabled = false;
            }
            
            // Focus back on input
            messageInput.focus();
            updateStatus('Ready', 'ready');
        } else {
            showError(data.error || 'Failed to send message');
            updateStatus('Error', 'error');
        }
    })
    .catch(error => {
        messageInput.disabled = false;
        isWaitingForResponse = false;
        showError('Error sending message: ' + error.message);
        updateStatus('Error', 'error');
    });
}

// Function to request feedback for current conversation
function requestFeedback() {
    if (!currentConversationId || feedbackBtn.disabled) return;
    
    updateStatus('Generating feedback...', 'loading');
    feedbackBtn.disabled = true;
    
    fetch(`/chat/${currentConversationId}/feedback`)
        .then(response => response.json())
        .then(data => {
            feedbackBtn.disabled = false;
            
            if (data.status === 'success') {
                // Show feedback in modal
                showFeedbackModal(data.feedback);
                updateStatus('Ready', 'ready');
            } else {
                showError(data.error || 'Failed to generate feedback');
                updateStatus('Error', 'error');
            }
        })
        .catch(error => {
            feedbackBtn.disabled = false;
            showError('Error generating feedback: ' + error.message);
            updateStatus('Error', 'error');
        });
}

// Function to add a message to the UI
function addMessage(message) {
    if (!message) return;
    
    // Remove empty state if present
    emptyState.classList.remove('active');
    
    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = `message ${message.role}`;
    
    // Format timestamp
    let timestampStr = '';
    try {
        const timestamp = new Date(message.timestamp);
        timestampStr = timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        timestampStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    // Format content with Markdown-like features
    let formattedContent = message.content;
    if (message.role === 'assistant') {
        // Convert headers
        formattedContent = formattedContent.replace(/### (.*?)( ###)?/g, '<h3>$1</h3>');
        
        // Convert bullet points
        formattedContent = formattedContent.replace(/- (.*?)(\n|$)/g, '<li>$1</li>');
        
        // Wrap bullet points in lists
        if (formattedContent.includes('<li>')) {
            formattedContent = formattedContent.replace(/<li>(.*?)<\/li>/g, function(match) {
                return '<ul>' + match + '</ul>';
            }).replace(/<\/ul><ul>/g, '');
        }
        
        // Convert line breaks
        formattedContent = formattedContent.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
    }
    
    // Create message HTML
    messageElement.innerHTML = `
        <div class="message-avatar">
            <div class="avatar ${message.role === 'assistant' ? 'assistant' : 'user'}">
                <i class="fas ${message.role === 'assistant' ? 'fa-robot' : 'fa-user'}"></i>
            </div>
        </div>
        <div class="message-bubble">
            <div class="message-content">${formattedContent}</div>
            <div class="message-timestamp">${timestampStr}</div>
        </div>
    `;
    
    // Add to chat
    chatMessages.appendChild(messageElement);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Add animation
    setTimeout(() => {
        messageElement.classList.add('visible');
    }, 10);
}

// Function to update status indicator
function updateStatus(message, state) {
    if (!statusIndicator) return;
    
    // Remove previous state classes
    statusIndicator.classList.remove('ready', 'loading', 'error');
    
    // Add appropriate icon and class
    let icon = '';
    if (state === 'ready') {
        icon = '<i class="fas fa-check-circle"></i> ';
        statusIndicator.classList.add('ready');
    } else if (state === 'loading') {
        icon = '<i class="fas fa-spinner fa-spin"></i> ';
        statusIndicator.classList.add('loading');
    } else if (state === 'error') {
        icon = '<i class="fas fa-exclamation-circle"></i> ';
        statusIndicator.classList.add('error');
    }
    
    statusIndicator.innerHTML = icon + message;
}

// Function to show error message
function showError(message) {
    const errorElement = document.createElement('div');
    errorElement.className = 'error-message';
    errorElement.innerHTML = `
        <i class="fas fa-exclamation-circle"></i>
        <span>${message}</span>
    `;
    
    chatMessages.appendChild(errorElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        errorElement.classList.add('fade-out');
        setTimeout(() => {
            if (errorElement.parentNode) {
                errorElement.parentNode.removeChild(errorElement);
            }
        }, 500);
    }, 5000);
}

// Setup voice recognition
function setupVoiceRecognition() {
    // Check if browser supports speech recognition
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        
        // Setup recognition options
        recognition.lang = 'en-US';
        
        // Setup voice button
        if (voiceBtn) {
            voiceBtn.addEventListener('click', toggleVoiceInput);
        }
        
        if (stopVoiceBtn) {
            stopVoiceBtn.addEventListener('click', stopVoiceInput);
        }
        
        // Set up recognition events
        recognition.onstart = function() {
            isRecording = true;
            voiceIndicator.classList.add('active');
            voiceBtn.classList.add('active');
        };
        
        recognition.onend = function() {
            isRecording = false;
            voiceIndicator.classList.remove('active');
            voiceBtn.classList.remove('active');
        };
        
        recognition.onresult = function(event) {
            const transcript = Array.from(event.results)
                .map(result => result[0])
                .map(result => result.transcript)
                .join('');
                
            messageInput.value = transcript;
            messageInput.style.height = 'auto';
            messageInput.style.height = (messageInput.scrollHeight) + 'px';
        };
        
        recognition.onerror = function(event) {
            if (event.error === 'not-allowed') {
                showError('Microphone access denied. Please check your browser permissions.');
            } else {
                showError('Voice recognition error: ' + event.error);
            }
            
            isRecording = false;
            voiceIndicator.classList.remove('active');
            voiceBtn.classList.remove('active');
        };
    } else {
        // Hide voice button if not supported
        if (voiceBtn) {
            voiceBtn.style.display = 'none';
        }
    }
}

// Toggle voice input on/off
function toggleVoiceInput() {
    if (!recognition) return;
    
    if (!isRecording) {
        try {
            recognition.start();
        } catch (e) {
            // Handle the case where recognition is already active
            console.error('Speech recognition error:', e);
        }
    } else {
        stopVoiceInput();
    }
}

// Stop voice input
function stopVoiceInput() {
    if (!recognition || !isRecording) return;
    
    recognition.stop();
    
    // If there's content in the input, submit the form
    if (messageInput.value.trim()) {
        setTimeout(() => {
            messageForm.dispatchEvent(new Event('submit'));
        }, 300);
    }
}

// Feedback modal functionality
const feedbackModal = document.getElementById('feedbackModal');
const feedbackContent = document.getElementById('feedbackContent');
const closeFeedbackBtn = document.getElementById('closeFeedbackBtn');
const downloadFeedbackBtn = document.getElementById('downloadFeedbackBtn');
const modalCloseBtn = document.querySelector('.modal-close');

if (closeFeedbackBtn) {
    closeFeedbackBtn.addEventListener('click', closeFeedbackModal);
}

if (modalCloseBtn) {
    modalCloseBtn.addEventListener('click', closeFeedbackModal);
}

if (downloadFeedbackBtn) {
    downloadFeedbackBtn.addEventListener('click', downloadFeedback);
}

// Close modal when clicking outside
document.addEventListener('click', function(e) {
    if (feedbackModal && feedbackModal.classList.contains('active') && 
        !e.target.closest('.modal-content') && !e.target.closest('#feedbackBtn')) {
        closeFeedbackModal();
    }
});

function showFeedbackModal(feedback) {
    if (!feedbackModal || !feedbackContent) return;
    
    // Format the feedback
    let formattedFeedback = feedback
        .replace(/### (.*?)( ###)?/g, '<h3>$1</h3>')
        .replace(/- (.*?)(\n|$)/g, '<li>$1</li>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
        
    // Wrap lists
    if (formattedFeedback.includes('<li>')) {
        formattedFeedback = formattedFeedback.replace(/<li>(.*?)<\/li>/g, function(match) {
            return '<ul>' + match + '</ul>';
        }).replace(/<\/ul><ul>/g, '');
    }
    
    feedbackContent.innerHTML = formattedFeedback;
    feedbackModal.classList.add('active');
    document.body.classList.add('modal-open');
}

function closeFeedbackModal() {
    if (!feedbackModal) return;
    
    feedbackModal.classList.remove('active');
    document.body.classList.remove('modal-open');
}

function downloadFeedback() {
    if (!feedbackContent) return;
    
    // Get plain text version
    const plainText = feedbackContent.innerText || feedbackContent.textContent;
    
    // Create download link
    const blob = new Blob([plainText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    
    // Generate filename with date
    const date = new Date().toISOString().slice(0, 10);
    a.href = url;
    a.download = `sales-feedback-${date}.txt`;
    
    document.body.appendChild(a);
    a.click();
    
    // Clean up
    setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, 100);
}
