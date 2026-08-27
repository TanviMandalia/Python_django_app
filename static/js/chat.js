document.addEventListener("DOMContentLoaded", function () {
  const messagesContainer = document.getElementById("chatMessagesContainer");
  const messageInput = document.getElementById("chatMessageInput");

  // Auto scroll to bottom
  function scrollToBottom() {
    if (messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  }

  scrollToBottom();

  // Typing debounce indicator
  let typingTimeout;
  if (messageInput) {
    messageInput.addEventListener("input", function () {
      fetch("/start-typing/");
      clearTimeout(typingTimeout);
      typingTimeout = setTimeout(function () {
        fetch("/stop-typing/");
      }, 2000);
    });
  }
});

