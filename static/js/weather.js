async function getUserLocation() {
    const cityInput = document.getElementById('cityInput');
    const weatherDisplay = document.getElementById('weatherDisplay');

    if (!navigator.geolocation) {
        alert('❌ Geolocation is not supported by your browser');
        return;
    }

    weatherDisplay.innerHTML = '<p>📍 Getting your location...</p>';
    cityInput.value = 'Detecting location...';

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            try {
                // Get weather data directly using coordinates
                const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto`;
                const weatherResponse = await fetch(weatherUrl);
                const weatherData = await weatherResponse.json();

                // Try to get city name
                const geoUrl = `https://geocoding-api.open-meteo.com/v1/search?latitude=${lat}&longitude=${lon}&count=1&language=en&format=json`;
                const geoResponse = await fetch(geoUrl);
                const geoData = await geoResponse.json();

                let cityName = 'Your Location';
                if (geoData.results && geoData.results.length > 0) {
                    cityName = geoData.results[0].name;
                }

                cityInput.value = cityName;
                displayWeather(weatherData, cityName);

            } catch (error) {
                weatherDisplay.innerHTML = '<p style="color: red;">❌ Error fetching location data</p>';
                cityInput.value = '';
                console.error('Location error:', error);
            }
        },
        (error) => {
            weatherDisplay.innerHTML = '<p style="color: red;">❌ Unable to get your location. Please enter city manually.</p>';
            cityInput.value = '';
            console.error('Geolocation error:', error);
        }
    );
}

async function getWeather() {
    const city = document.getElementById('cityInput').value.trim();
    const weatherDisplay = document.getElementById('weatherDisplay');

    if (!city || city === 'Detecting location...') {
        alert('⚠️ Please enter a city name or use your location!');
        return;
    }

    weatherDisplay.innerHTML = '<p>🔄 Loading weather data...</p>';

    try {
        const response = await fetch(`/api/weather?city=${encodeURIComponent(city)}`);
        const data = await response.json();

        if (data.success) {
            displayWeather(data.weather, data.city);
        } else {
            weatherDisplay.innerHTML = `<p style="color: red;">❌ ${data.message}</p>`;
        }
    } catch (error) {
        weatherDisplay.innerHTML = '<p style="color: red;">❌ Error fetching weather data. Please try again.</p>';
        console.error('Weather error:', error);
    }
}

function displayWeather(weatherData, cityName) {
    const weatherDisplay = document.getElementById('weatherDisplay');
    const current = weatherData.current;
    const daily = weatherData.daily;

    const weatherHTML = `
        <div class="weather-item">
            <h3>${current.temperature_2m}°C</h3>
            <p>Temperature</p>
        </div>
        <div class="weather-item">
            <h3>${current.relative_humidity_2m}%</h3>
            <p>Humidity</p>
        </div>
        <div class="weather-item">
            <h3>${current.wind_speed_10m} km/h</h3>
            <p>Wind Speed</p>
        </div>
        <div class="weather-item">
            <h3>${current.precipitation} mm</h3>
            <p>Precipitation</p>
        </div>
    `;

    weatherDisplay.innerHTML = weatherHTML;

    // Auto-fill crop recommendation fields
    document.getElementById('temperature').value = current.temperature_2m;
    document.getElementById('humidity').value = current.relative_humidity_2m;
    document.getElementById('rainfall').value = daily.precipitation_sum[0] || 0;

    // Enable crop recommendation button
    const cropBtn = document.getElementById('cropRecommendBtn');
    if (cropBtn) {
        cropBtn.disabled = false;
    }

    // Update crop display message
    const cropDisplay = document.getElementById('cropDisplay');
    if (cropDisplay) {
        cropDisplay.innerHTML = '<p style="color: var(--green-primary);">✅ Weather data loaded! Select soil type and click "Get Crop Recommendations"</p>';
    }
}
