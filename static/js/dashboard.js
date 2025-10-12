let selectedImage = null;
let selectedPlant = null;
let cameraStream = null;

function plantSelected() {
    const plantSelect = document.getElementById('plantSelect');
    selectedPlant = plantSelect.value;

    const imageUploadSection = document.getElementById('imageUploadSection');
    const imageInput = document.getElementById('imageInput');
    const selectedPlantInfo = document.getElementById('selectedPlantInfo');
    const step1 = document.getElementById('step1-indicator');
    const step2 = document.getElementById('step2-indicator');

    if (selectedPlant) {
        imageUploadSection.style.opacity = '1';
        imageUploadSection.style.pointerEvents = 'auto';
        imageInput.disabled = false;

        selectedPlantInfo.style.display = 'block';
        selectedPlantInfo.innerHTML = `
            <strong>✓ Selected Plant:</strong> ${selectedPlant}<br>
            <small>Please upload or capture a clear image of a ${selectedPlant} leaf.</small>
        `;

        step1.classList.add('completed');
        step2.classList.add('active');

        document.getElementById('resultDisplay').innerHTML = '';
        document.getElementById('imagePreview').innerHTML = '';
        selectedImage = null;
        document.getElementById('detectBtn').disabled = true;
    } else {
        imageUploadSection.style.opacity = '0.5';
        imageUploadSection.style.pointerEvents = 'none';
        imageInput.disabled = true;
        selectedPlantInfo.style.display = 'none';

        step1.classList.remove('completed');
        step2.classList.remove('active');
    }
}

// ============= CAMERA FUNCTIONS =============

function switchToUpload() {
    document.getElementById('uploadBtn').classList.add('active');
    document.getElementById('cameraBtn').classList.remove('active');
    document.getElementById('uploadOption').style.display = 'block';
    document.getElementById('cameraOption').style.display = 'none';
    stopCamera();
}

function switchToCamera() {
    document.getElementById('cameraBtn').classList.add('active');
    document.getElementById('uploadBtn').classList.remove('active');
    document.getElementById('uploadOption').style.display = 'none';
    document.getElementById('cameraOption').style.display = 'block';
}

async function startCamera() {
    const video = document.getElementById('cameraVideo');
    const startBtn = document.getElementById('startCameraBtn');
    const captureBtn = document.getElementById('captureBtn');
    const stopBtn = document.getElementById('stopCameraBtn');

    try {
        const constraints = {
            video: {
                facingMode: 'environment',
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }
        };

        cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
        video.srcObject = cameraStream;

        startBtn.style.display = 'none';
        captureBtn.style.display = 'inline-block';
        stopBtn.style.display = 'inline-block';

        // Add guide overlay
        const container = document.querySelector('.camera-container');
        if (!document.querySelector('.camera-guide-text')) {
            const guideText = document.createElement('div');
            guideText.className = 'camera-guide-text';
            guideText.textContent = `📸 Position ${selectedPlant} leaf in center`;
            container.appendChild(guideText);
        }

    } catch (error) {
        console.error('Camera error:', error);
        alert('❌ Unable to access camera. Please:\n1. Allow camera permission\n2. Use HTTPS or localhost\n3. Or use file upload instead');
    }
}

function captureImage() {
    const video = document.getElementById('cameraVideo');
    const canvas = document.getElementById('cameraCanvas');
    const context = canvas.getContext('2d');

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
        const fileName = `${selectedPlant}_${Date.now()}.jpg`;
        selectedImage = new File([blob], fileName, { type: 'image/jpeg' });

        const previewDiv = document.getElementById('imagePreview');
        previewDiv.innerHTML = `
            <div class="preview-container">
                <img src="${canvas.toDataURL()}" alt="Captured Image">
                <p class="preview-label">✅ Captured: ${selectedPlant} leaf image</p>
            </div>
        `;

        document.getElementById('detectBtn').disabled = false;

        const step2 = document.getElementById('step2-indicator');
        const step3 = document.getElementById('step3-indicator');
        step2.classList.add('completed');
        step3.classList.add('active');

        stopCamera();
    }, 'image/jpeg', 0.95);
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }

    const video = document.getElementById('cameraVideo');
    video.srcObject = null;

    const startBtn = document.getElementById('startCameraBtn');
    const captureBtn = document.getElementById('captureBtn');
    const stopBtn = document.getElementById('stopCameraBtn');

    if (startBtn) startBtn.style.display = 'inline-block';
    if (captureBtn) captureBtn.style.display = 'none';
    if (stopBtn) stopBtn.style.display = 'none';

    const guideText = document.querySelector('.camera-guide-text');
    if (guideText) guideText.remove();
}

// ============= UPLOAD FUNCTIONS =============

function previewImage(event) {
    const file = event.target.files[0];
    if (file) {
        selectedImage = file;
        const reader = new FileReader();
        reader.onload = function(e) {
            const previewDiv = document.getElementById('imagePreview');
            previewDiv.innerHTML = `
                <div class="preview-container">
                    <img src="${e.target.result}" alt="Preview">
                    <p class="preview-label">✅ Selected: ${selectedPlant} leaf image</p>
                </div>
            `;

            document.getElementById('detectBtn').disabled = false;

            const step2 = document.getElementById('step2-indicator');
            const step3 = document.getElementById('step3-indicator');
            step2.classList.add('completed');
            step3.classList.add('active');
        };
        reader.readAsDataURL(file);
    }
}

// ============= DETECTION FUNCTION =============

async function detectDisease() {
    if (!selectedPlant) {
        alert('⚠️ Please select a plant type first!');
        return;
    }

    if (!selectedImage) {
        alert('⚠️ Please select or capture an image!');
        return;
    }

    const language = document.getElementById('languageSelect').value;
    const loadingSpinner = document.getElementById('loadingSpinner');
    const resultDisplay = document.getElementById('resultDisplay');
    const analyzingPlant = document.getElementById('analyzingPlant');

    loadingSpinner.style.display = 'block';
    resultDisplay.innerHTML = '';
    analyzingPlant.textContent = selectedPlant;

    const formData = new FormData();
    formData.append('image', selectedImage);
    formData.append('language', language);
    formData.append('plant_name', selectedPlant);

    try {
        const response = await fetch('/api/detect-disease', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        loadingSpinner.style.display = 'none';

        if (data.success) {
            let resultHTML = '<div class="result-success">';
            resultHTML += '<h3>✅ Analysis Complete</h3>';

            resultHTML += `<div class="plant-info">
                <strong>🌿 Plant:</strong> ${data.plant_name || selectedPlant}
            </div>`;

            if (data.method === 'model') {
                resultHTML += `
                    <div class="confidence-badge ${data.confidence > 0.8 ? 'high-confidence' : 'medium-confidence'}">
                        <strong>Confidence:</strong> ${(data.confidence * 100).toFixed(2)}%
                    </div>
                    <div class="disease-name">
                        <strong>🦠 Disease:</strong> ${data.disease_name}
                    </div>
                `;
            } else {
                resultHTML += '<div class="ai-badge">📊 Analyzed by Gemini AI</div>';
            }

            resultHTML += `
                <div class="disease-info-content">
                    ${formatDiseaseInfo(data.disease_info)}
                </div>
            </div>`;

            resultDisplay.innerHTML = resultHTML;

            const step3 = document.getElementById('step3-indicator');
            step3.classList.add('completed');
        } else {
            resultDisplay.innerHTML = `
                <div class="result-error">
                    <h3>⚠️ ${data.message}</h3>
                    <p>Please try again with a clear image of a ${selectedPlant} leaf.</p>
                </div>
            `;
        }
    } catch (error) {
        loadingSpinner.style.display = 'none';
        resultDisplay.innerHTML = `
            <div class="result-error">
                <h3>❌ Error</h3>
                <p>Failed to detect disease. Please try again.</p>
            </div>
        `;
        console.error('Detection error:', error);
    }
}

function formatDiseaseInfo(info) {
    let formatted = info.replace(/\n/g, '<br>');
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/- (.*?)<br>/g, '<li>$1</li>');
    formatted = formatted.replace(/(<li>.*<\/li>)+/g, '<ul>$1</ul>');
    return formatted;
}

// ============= CROP RECOMMENDATION =============

async function getCropRecommendation() {
    const temperature = document.getElementById('temperature').value;
    const humidity = document.getElementById('humidity').value;
    const rainfall = document.getElementById('rainfall').value;
    const soilType = document.getElementById('soilType').value;

    if (!temperature || !humidity || !rainfall) {
        alert('⚠️ Please fetch weather data first!');
        return;
    }

    if (!soilType) {
        alert('⚠️ Please select soil type!');
        return;
    }

    const cropDisplay = document.getElementById('cropDisplay');
    cropDisplay.innerHTML = '<p>🔄 Loading recommendations...</p>';

    try {
        const response = await fetch('/api/crop-recommendation', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                temperature: parseFloat(temperature),
                humidity: parseFloat(humidity),
                rainfall: parseFloat(rainfall),
                soil_type: soilType
            })
        });

        const data = await response.json();

        if (data.success) {
            const formattedText = formatCropRecommendations(data.recommendations);
            cropDisplay.innerHTML = formattedText;
        } else {
            cropDisplay.innerHTML = `<p style="color: red;">❌ ${data.message}</p>`;
        }
    } catch (error) {
        cropDisplay.innerHTML = '<p style="color: red;">❌ Error getting recommendations.</p>';
        console.error('Recommendation error:', error);
    }
}

function formatCropRecommendations(text) {
    let formatted = text;
    formatted = formatted.replace(/\n\n/g, '<br><br>');
    formatted = formatted.replace(/\n/g, '<br>');
    formatted = formatted.replace(/(\d+\.\s+)/g, '<strong>$1</strong>');
    return `<div style="line-height: 1.8;">${formatted}</div>`;
}

// ============= LOGOUT =============

function logout() {
    fetch('/api/logout', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = '/';
        }
    })
    .catch(error => console.error('Logout error:', error));
}

// Clean up camera on page unload
window.addEventListener('beforeunload', () => {
    stopCamera();
});
