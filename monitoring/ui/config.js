// RADWATCH Configuration
// Edit this file to customize your deployment

window.RADWATCH_CONFIG = {
    // Orthanc PACS server
    // Change this to your Orthanc URL
    orthancUrl: 'http://' + window.location.hostname + ':8042',
    orthancWebUrl: 'http://' + window.location.hostname + ':8042',
    
    // OHIF Viewer (usually served by Orthanc plugin)
    ohifUrl: 'http://' + window.location.hostname + ':8042/ohif/',
    
    // Grafana for metrics/dashboards
    grafanaUrl: 'http://' + window.location.hostname + ':3000',
    
    // Workflow API (served through nginx proxy)
    apiBaseUrl: '/api'
};
