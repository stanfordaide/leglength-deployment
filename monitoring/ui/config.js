// RADWATCH Configuration
// Edit this file to customize your deployment

window.RADWATCH_CONFIG = {
    // Orthanc PACS server (proxied through nginx /orthanc/)
    // All requests go through the same host to avoid CORS issues
    orthancUrl: window.location.protocol + '//' + window.location.host + '/orthanc',
    orthancWebUrl: window.location.protocol + '//' + window.location.host + '/orthanc',
    
    // OHIF Viewer (via Orthanc proxy)
    ohifUrl: window.location.protocol + '//' + window.location.host + '/orthanc/ohif/',
    
    // Grafana for metrics/dashboards (could also be proxied if needed)
    // For now uses direct connection - adjust if you need to proxy it too
    grafanaUrl: window.location.protocol + '//' + window.location.host.split(':')[0] + ':9032',
    
    // Workflow API (served through nginx proxy at /api/)
    // This proxies to workflow-api:5000 inside Docker
    apiBaseUrl: '/api'
};
