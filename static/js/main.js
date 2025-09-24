console.log("Krishi Sakhi JavaScript file loaded!");

// --- Image Preview Logic ---
const imageUpload = document.getElementById('imageUpload');
const imagePreview = document.getElementById('imagePreview');

if (imageUpload) {
    imageUpload.addEventListener('change', function() {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(event) {
                imagePreview.src = event.target.result;
                imagePreview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    });
}

// --- NEW: Voice Recognition Logic ---
const micButton = document.getElementById('micButton');
const questionText = document.getElementById('questionText');

// Check if the browser supports the Web Speech API
if ('webkitSpeechRecognition' in window) {
    const recognition = new webkitSpeechRecognition();
    recognition.continuous = false; // Stop listening after a single phrase
    recognition.interimResults = false;
    recognition.lang = 'ml-IN'; // Set language to Malayalam (India)

    // When the microphone button is clicked
    micButton.addEventListener('click', () => {
        recognition.start();
        questionText.placeholder = 'Listening...';
    });

    // When the API gets a result
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        questionText.value = transcript; // Put the spoken text into the text box
        questionText.placeholder = 'e.g., Which fertilizer is best for bananas during the monsoon?';
    };

    // If there's an error
    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        questionText.placeholder = 'Sorry, I could not hear you. Please try again.';
    };

} else {
    // If the browser doesn't support the API, hide the button
    micButton.style.display = 'none';
    console.log('Speech recognition not supported in this browser.');
}
