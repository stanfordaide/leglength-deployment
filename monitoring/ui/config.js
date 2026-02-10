// RADWATCH Configuration
// Edit this file to customize your deployment
// NOTE: config-generated.js is used in production (generated from config.env)
// This file is the fallback for development

window.RADWATCH_CONFIG = {
    // Orthanc PACS server (proxied through nginx /orthanc/)
    orthancUrl: window.location.protocol + '//' + window.location.host + '/orthanc',
    orthancWebUrl: window.location.protocol + '//' + window.location.host + '/orthanc',
    
    // OHIF Viewer (at /ohif/viewer path)
    ohifUrl: window.location.protocol + '//' + window.location.host + '/ohif/viewer',
    
    // Grafana for metrics/dashboards (port 9032 in this deployment)
    grafanaUrl: window.location.protocol + '//' + window.location.host.split(':')[0] + ':9032',
    
    // Workflow API (served through nginx proxy at /api/)
    apiBaseUrl: '/api'
};
