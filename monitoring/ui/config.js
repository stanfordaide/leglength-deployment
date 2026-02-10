// RADWATCH Configuration
// Edit this file to customize your deployment
// NOTE: These ports should match your config.env values

window.RADWATCH_CONFIG = {
    // Orthanc PACS server (port 9011 in this deployment)
    orthancUrl: 'http://' + window.location.hostname + ':9011',
    orthancWebUrl: 'http://' + window.location.hostname + ':9011',
    
    // OHIF Viewer (port 9012 in this deployment)
    ohifUrl: 'http://' + window.location.hostname + ':9012',
    
    // Grafana for metrics/dashboards (port 9032 in this deployment)
    grafanaUrl: 'http://' + window.location.hostname + ':9032',
    
    // Workflow API (served through nginx proxy at /api/)
    // This proxies to workflow-api:5000 inside Docker
    apiBaseUrl: '/api'
};
