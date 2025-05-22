document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing dashboard...');
    initializeCharts();
    updateDashboard();
    setInterval(updateDashboard, 2000);
    document.getElementById('loading-overlay').style.display = 'none';
    document.querySelector('.dashboard-grid').style.display = 'grid';
});

function generateData(min, max, count, previousData = []) {
    return Array.from({length: count}, (_, i) => {
        const prevValue = previousData[i] || (Math.random() * (max - min) + min);
        const change = (Math.random() - 0.5) * (max - min) * 0.1;
        return Math.max(min, Math.min(max, prevValue + change));
    });
}

function initializeCharts() {
    try {
        // Temperature Chart with critical temperature highlighted
        const tempCtx = document.getElementById('tempChart').getContext('2d');
        window.tempChart = new Chart(tempCtx, {
            type: 'line',
            data: {
                labels: ['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', 
                        '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'],
                datasets: [{
                    label: 'Temperature (°F)',
                    data: generateData(70, 95, 12),
                    borderColor: '#3498db',
                    tension: 0.4,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 800,
                    easing: 'easeInOutQuad'
                },
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        suggestedMin: 65,
                        suggestedMax: 100
                    }
                }
            }
        });

        // Energy Chart
        const energyCtx = document.getElementById('energyChart').getContext('2d');
        window.energyChart = new Chart(energyCtx, {
            type: 'bar',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Energy Consumption (kWh)',
                    data: generateData(500, 1000, 7),
                    backgroundColor: '#2ecc71'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 800,
                    easing: 'easeInOutQuad'
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });

        // Quality Chart
        const qualityCtx = document.getElementById('qualityChart').getContext('2d');
        window.qualityChart = new Chart(qualityCtx, {
            type: 'bar',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
                datasets: [{
                    label: 'Defect Rate (%)',
                    data: generateData(0.5, 1.5, 5),
                    backgroundColor: '#3498db'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 800,
                    easing: 'easeInOutQuad'
                },
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 2
                    }
                }
            }
        });

        // Initialize OEE Gauges
        ['availabilityGauge', 'performanceGauge', 'qualityGauge'].forEach((gaugeId, index) => {
            const ctx = document.getElementById(gaugeId).getContext('2d');
            window[gaugeId] = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    datasets: [{
                        data: [85, 15],
                        backgroundColor: [
                            '#2ecc71',
                            '#ecf0f1'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    circumference: 180,
                    rotation: -90,
                    cutout: '80%',
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            enabled: false
                        }
                    }
                }
            });
        });

        // System Health Chart
        const systemHealthCtx = document.getElementById('systemHealthChart').getContext('2d');
        window.systemHealthChart = new Chart(systemHealthCtx, {
            type: 'line',
            data: {
                labels: Array.from({length: 20}, (_, i) => i),
                datasets: [{
                    label: 'System Load',
                    data: generateData(20, 80, 20),
                    borderColor: '#3498db',
                    tension: 0.4,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        display: false
                    },
                    y: {
                        display: false,
                        suggestedMin: 0,
                        suggestedMax: 100
                    }
                },
                elements: {
                    point: {
                        radius: 0
                    }
                }
            }
        });

    } catch (error) {
        console.error('Error initializing charts:', error);
    }
}

// Keep the critical temperature steady for PLC-003
function updateReading(id, min, max) {
    const element = document.getElementById(id);
    if (element) {
        let newValue;
        if (id === 'temp-reading-3') {
            newValue = '95.2'; // Keep critical temperature steady
        } else if (id === 'pressure-reading-3') {
            newValue = '3.2';  // Keep critical pressure steady
        } else {
            newValue = (Math.random() * (max - min) + min).toFixed(1);
        }
        element.textContent = `${newValue}${id.includes('temp') ? '°F' : ' bar'}`;
        return newValue;
    }
}

function updateProductionStats() {
    const dailyOutput = document.getElementById('daily-output');
    const efficiency = document.getElementById('efficiency');
    const qualityRate = document.getElementById('quality-rate');

    if (dailyOutput) dailyOutput.textContent = `${Math.floor(Math.random() * 1000 + 5000)} units`;
    if (efficiency) efficiency.textContent = `${(Math.random() * 10 + 90).toFixed(1)}%`;
    if (qualityRate) qualityRate.textContent = `${(Math.random() * 1 + 98.5).toFixed(1)}%`;
}

function updateEnvironmentalMetrics() {
    document.getElementById('humidity').textContent = `${Math.floor(Math.random() * 20 + 40)}%`;
    document.getElementById('co2').textContent = `${Math.floor(Math.random() * 50 + 400)} ppm`;
    document.getElementById('noise').textContent = `${Math.floor(Math.random() * 10 + 68)} dB`;
}

function updateResourceUtilization() {
    ['cpu-load', 'memory-usage', 'network-usage'].forEach(resource => {
        const element = document.getElementById(resource);
        const newValue = Math.floor(Math.random() * 30 + 50);
        element.style.width = `${newValue}%`;
        element.parentElement.nextElementSibling.textContent = `${newValue}%`;
    });
}

function updateOEEGauges() {
    ['availability', 'performance', 'quality'].forEach(metric => {
        const chart = window[`${metric}Gauge`];
        const valueElement = document.getElementById(`${metric}-value`);
        const newValue = Math.floor(Math.random() * 20 + 80);
        chart.data.datasets[0].data = [newValue, 100 - newValue];
        chart.data.datasets[0].backgroundColor[0] = newValue > 90 ? '#2ecc71' : newValue > 70 ? '#f1c40f' : '#e74c3c';
        chart.update();
        valueElement.textContent = `${newValue}%`;
    });
}

function updateSystemHealth() {
    document.getElementById('system-uptime').textContent = `${(99 + Math.random()).toFixed(2)}%`;
    document.getElementById('network-latency').textContent = `${Math.floor(20 + Math.random() * 10)}ms`;
    document.getElementById('api-response').textContent = `${Math.floor(180 + Math.random() * 40)}ms`;

    window.systemHealthChart.data.datasets[0].data = generateData(20, 80, 20, 
        window.systemHealthChart.data.datasets[0].data);
    window.systemHealthChart.update();
}

function updateTimestamp() {
    const now = new Date();
    document.getElementById('timestamp').textContent = `Last updated: ${now.toLocaleString()}`;
}

function updateDashboard() {
    // Update all readings except PLC-003 which stays in critical state
    updateReading('temp-reading-1', 70, 80);
    updateReading('pressure-reading-1', 2.0, 2.8);
    updateReading('temp-reading-2', 70, 80);
    updateReading('pressure-reading-2', 2.0, 2.8);
    updateReading('temp-reading-3', 95, 95.5); // Keep critical
    updateReading('pressure-reading-3', 3.1, 3.3); // Keep critical

    updateProductionStats();
    updateEnvironmentalMetrics();
    updateResourceUtilization();
    updateOEEGauges();
    updateSystemHealth();

    // Update charts
    window.tempChart.data.datasets[0].data = generateData(70, 95, 12, window.tempChart.data.datasets[0].data);
    window.tempChart.update();

    window.energyChart.data.datasets[0].data = generateData(500, 1000, 7, window.energyChart.data.datasets[0].data);
    window.energyChart.update();

    window.qualityChart.data.datasets[0].data = generateData(0.5, 1.5, 5, window.qualityChart.data.datasets[0].data);
    window.qualityChart.update();

    updateTimestamp();
}
