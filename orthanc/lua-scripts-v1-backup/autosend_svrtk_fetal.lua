-- SVRTK Fetal MRI Auto-Processing Script
-- Automatically detects fetal MRI studies and sends them to Mercure for intelligent SVRTK reconstruction
-- Integrates with intelligent_svrtk_processor.py for automated series grouping and processing
-- Version 2.0 - Updated for intelligent processing pipeline

-- Helper function to safely convert table to string for debugging
function tableToString(t, indent)
    if type(t) ~= "table" then
        return tostring(t)
    end
    
    indent = indent or 0
    local spacing = string.rep("  ", indent)
    local result = "{\n"
    
    for k, v in pairs(t) do
        if type(v) == "table" then
            result = result .. spacing .. "  " .. tostring(k) .. " = " .. tableToString(v, indent + 1) .. ",\n"
        else
            result = result .. spacing .. "  " .. tostring(k) .. " = " .. tostring(v) .. ",\n"
        end
    end
    
    result = result .. spacing .. "}"
    return result
end

-- Helper function to safely get table length
function getTableLength(t)
    if type(t) ~= "table" then
        return 0
    end
    
    local count = 0
    for _ in pairs(t) do
        count = count + 1
    end
    return count
end

-- Function to check if study has already been processed by SVRTK
function hasSVRTKOutput(instances)
    if not instances or type(instances) ~= "table" then
        print('   No instances provided or invalid instances table')
        return false
    end
    
    for _, instance in pairs(instances) do
        if instance and instance['ID'] then
            local success, instanceTags = pcall(function()
                local response = RestApiGet('/instances/' .. instance['ID'] .. '/tags?simplify')
                return response and ParseJson(response) or nil
            end)
            
            if success and instanceTags then
                -- Check for SVRTK reconstruction output
                local seriesDescription = instanceTags['SeriesDescription'] or ''
                local softwareVersions = instanceTags['SoftwareVersions'] or ''
                local imageComments = instanceTags['ImageComments'] or ''
                
                -- Primary check: SVRTK series description patterns
                local normalizedSeriesDesc = string.upper(seriesDescription)
                if string.find(normalizedSeriesDesc, 'SVRTK') or
                   string.find(normalizedSeriesDesc, 'BRAIN.*RECON') or
                   string.find(normalizedSeriesDesc, 'BODY.*RECON') or
                   string.find(normalizedSeriesDesc, 'SSFSE.*RECON') or
                   string.find(normalizedSeriesDesc, 'FIESTA.*RECON') then
                    print('   Found SVRTK reconstruction series: ' .. tostring(seriesDescription or 'Unknown'))
                    return true
                end
                
                -- Secondary check: SVRTK software version
                if string.find(string.upper(softwareVersions), 'SVRTK') then
                    print('   Found SVRTK software version: ' .. tostring(softwareVersions or 'Unknown'))
                    return true
                end
                
                -- Tertiary check: SVRTK image comments
                if string.find(string.upper(imageComments), 'SVRTK') or
                   string.find(string.upper(imageComments), 'RECONSTRUCTION') then
                    print('   Found SVRTK image comments: ' .. tostring(imageComments or 'Unknown'))
                    return true
                end
            end
        end
    end
    
    return false
end

-- Function to analyze series for fetal MRI characteristics
function analyzeFetaISeries(instances)
    if not instances or getTableLength(instances) == 0 then
        print('   No instances to analyze')
        return {
            hasFetalSeries = false,
            ssfseCount = 0,
            fiestaCount = 0,
            brainCount = 0,
            bodyCount = 0,
            totalSeries = 0
        }
    end
    
    local seriesMap = {}
    local analysis = {
        hasFetalSeries = false,
        ssfseCount = 0,
        fiestaCount = 0,
        brainCount = 0,
        bodyCount = 0,
        totalSeries = 0
    }
    
    -- Group instances by series
    for _, instance in pairs(instances) do
        if instance and instance['ID'] then
            local success, instanceTags = pcall(function()
                local response = RestApiGet('/instances/' .. instance['ID'] .. '/tags?simplify')
                return response and ParseJson(response) or nil
            end)
            
            if success and instanceTags then
                local seriesUID = instanceTags['SeriesInstanceUID'] or 'Unknown'
                if not seriesMap[seriesUID] then
                    seriesMap[seriesUID] = {
                        description = instanceTags['SeriesDescription'] or '',
                        sequenceName = instanceTags['SequenceName'] or '',
                        instanceCount = 0
                    }
                end
                seriesMap[seriesUID].instanceCount = seriesMap[seriesUID].instanceCount + 1
            end
        end
    end
    
    -- Analyze each unique series
    for seriesUID, seriesInfo in pairs(seriesMap) do
        analysis.totalSeries = analysis.totalSeries + 1
        
        local normalizedDesc = string.upper(seriesInfo.description)
        local normalizedSeq = string.upper(seriesInfo.sequenceName)
        
        print('   Series: ' .. tostring(seriesInfo.description or '') .. ' (' .. tostring(seriesInfo.instanceCount or 0) .. ' instances)')
        
        -- Check for fetal characteristics
        if string.find(normalizedDesc, 'FETAL') or 
           string.find(normalizedDesc, 'FETUS') or
           string.find(normalizedDesc, 'BRAIN') or
           string.find(normalizedDesc, 'BODY') or
           string.find(normalizedDesc, 'T2') or
           string.find(normalizedDesc, 'SSFSE') or
           string.find(normalizedDesc, 'FIESTA') or
           string.find(normalizedDesc, 'TSE') or
           string.find(normalizedDesc, 'HASTE') then
            analysis.hasFetalSeries = true
        end
        
        -- Count specific sequence types
        if string.find(normalizedDesc, 'SSFSE') or string.find(normalizedSeq, 'SSFSE') then
            analysis.ssfseCount = analysis.ssfseCount + 1
        end
        
        if string.find(normalizedDesc, 'FIESTA') or string.find(normalizedSeq, 'FIESTA') then
            analysis.fiestaCount = analysis.fiestaCount + 1
        end
        
        if string.find(normalizedDesc, 'BRAIN') then
            analysis.brainCount = analysis.brainCount + 1
        end
        
        if string.find(normalizedDesc, 'BODY') or string.find(normalizedDesc, 'ABDOMEN') then
            analysis.bodyCount = analysis.bodyCount + 1
        end
    end
    
    print('   Analysis: Total=' .. tostring(analysis.totalSeries or 0) .. ', SSFSE=' .. tostring(analysis.ssfseCount or 0) .. ', FIESTA=' .. tostring(analysis.fiestaCount or 0) .. ', Brain=' .. tostring(analysis.brainCount or 0) .. ', Body=' .. tostring(analysis.bodyCount or 0))
    
    return analysis
end

-- Main function called when a study is stable
function OnStableStudy(studyId, tags, metadata, origin)
    -- Get study instances
    local success, instances = pcall(function()
        local response = RestApiGet('/studies/' .. studyId .. '/instances')
        return response and ParseJson(response) or nil
    end)

    if not success or not instances then
        print('Failed to retrieve instances for study: ' .. tostring(studyId or 'Unknown'))
        return
    end

    print('OnStableStudy called for studyId: ' .. tostring(studyId))
    
    -- Check if study description matches fetal MRI studies
    local studyDescription = tags['StudyDescription'] or ''
    local patientName = tags['PatientName'] or ''
    local normalizedDescription = string.upper(studyDescription)
    local normalizedPatientName = string.upper(patientName)
    
    -- Identify fetal MRI studies with more comprehensive patterns
    local isFetalStudy = false
    
    -- Primary indicators in study description
    if string.find(normalizedDescription, 'FETAL') or 
       string.find(normalizedDescription, 'FETUS') or
       string.find(normalizedDescription, 'PRENATAL') or
       string.find(normalizedDescription, 'OB ') or
       string.find(normalizedDescription, 'OB MRI') or
       string.find(normalizedDescription, 'OBSTETRIC') or
       string.find(normalizedDescription, 'MATERNAL') or
       string.find(normalizedDescription, 'PREGNANCY') then
        isFetalStudy = true
    end
    
    -- Secondary indicators in patient name
    if string.find(normalizedPatientName, 'FETAL') or 
       string.find(normalizedPatientName, 'FETUS') then
        isFetalStudy = true
    end
    
    -- Analyze series content for fetal characteristics
    local seriesAnalysis = analyzeFetaISeries(instances)
    
    -- If no obvious fetal study markers, check if series content suggests fetal MRI
    if not isFetalStudy and seriesAnalysis.hasFetalSeries then
        -- Additional heuristics for fetal studies without obvious study description
        if (seriesAnalysis.ssfseCount > 0 or seriesAnalysis.fiestaCount > 0) and 
           (seriesAnalysis.brainCount > 0 or seriesAnalysis.bodyCount > 0) then
            isFetalStudy = true
            print('   Detected potential fetal study based on series content')
        end
    end
    
    if not isFetalStudy then
        print('Not a fetal MRI study, ignoring')
        return
    end
    
    print('🧠 DETECTED FETAL MRI STUDY FOR INTELLIGENT PROCESSING')
    print('   Study ID: ' .. tostring(studyId or 'Unknown'))
    print('   Patient: ' .. tostring(patientName or 'Unknown'))  
    print('   Study Description: ' .. tostring(studyDescription or 'Unknown'))
    print('   Series Summary: ' .. tostring(seriesAnalysis.totalSeries or 0) .. ' total series')
    print('   Fetal Series: SSFSE=' .. tostring(seriesAnalysis.ssfseCount or 0) .. ', FIESTA=' .. tostring(seriesAnalysis.fiestaCount or 0) .. ', Brain=' .. tostring(seriesAnalysis.brainCount or 0) .. ', Body=' .. tostring(seriesAnalysis.bodyCount or 0))
    
    -- Check if study has already been processed by SVRTK
    if hasSVRTKOutput(instances) then
        print('   ✓ SVRTK output already detected - study already processed, skipping')
        return
    end
    
    -- Original study (no SVRTK output yet) - send entire study to MERCURE for intelligent processing
    print('🚀 PROCESSING NEW FETAL MRI STUDY (No SVRTK output detected)')
    print('   Found ' .. tostring(getTableLength(instances) or 0) .. ' instances in study')
    print('   Sending ENTIRE STUDY to MERCURE for intelligent SVRTK processing')
    
    -- Send the entire study to MERCURE for intelligent processing
    -- The intelligent_svrtk_processor.py will handle series grouping and reconstruction selection
    local sent = 0
    local failed = 0
    for _, instanceId in ipairs(instances) do
        local ok, err = pcall(function()
            SendToModality(instanceId, 'MERCURE')
        end)
        if ok then
            sent = sent + 1
        else
            failed = failed + 1
            print('   ✗ FAILED instance ' .. tostring(instanceId or 'Unknown') .. ': ' .. tostring(err))
        end
    end
    local success = failed == 0
    local job = 'sent=' .. tostring(sent or 0) .. ' failed=' .. tostring(failed or 0)
    
    if success and job then
        print('   ✅ FETAL STUDY QUEUED FOR INTELLIGENT MERCURE PROCESSING')
        print('   Job ID: ' .. tostring(job))
        print('   The intelligent processor will:')
        print('      - Analyze all series descriptions automatically')
        print('      - Group series into SSFSE/FIESTA + Brain/Body categories')
        print('      - Run up to 4 separate SVRTK reconstructions as needed')
        print('      - Return processed results automatically')
        print('AUTO-FORWARD: Fetal MRI study forwarded to MERCURE for intelligent SVRTK processing')
        print('  Patient: ' .. tostring(patientName or 'Unknown') .. ', Study: ' .. tostring(studyId or 'Unknown') .. ', Job: ' .. tostring(job))
    else
        print('   ❌ FAILED to queue study to MERCURE - Error: ' .. tostring(job))
        print('AUTO-FORWARD FAILED: Could not send study for intelligent SVRTK processing - Study: ' .. tostring(studyId or 'Unknown'))
    end
end

-- Callback function for when SVRTK results are received back
function OnStoredInstance(instanceId, tags, metadata, origin)
    if origin and origin['RequestOrigin'] == 'RestApi' then
        -- This might be a processed result coming back from MERCURE
        local seriesDescription = tags['SeriesDescription'] or ''
        local normalizedDesc = string.upper(seriesDescription)
        
        -- Check if this is an SVRTK reconstruction result
        if string.find(normalizedDesc, 'SVRTK') or
           string.find(normalizedDesc, 'RECONSTRUCTION') then
            
            local studyId = tags['StudyInstanceUID'] or 'Unknown'
            local patientName = tags['PatientName'] or 'Unknown'
            
            print('📥 SVRTK RECONSTRUCTION RESULT RECEIVED')
            print('   Patient: ' .. tostring(patientName or 'Unknown'))
            print('   Study: ' .. tostring(studyId or 'Unknown'))
            print('   Series: ' .. tostring(seriesDescription or 'Unknown'))
            print('   Instance: ' .. tostring(instanceId or 'Unknown'))
            
            -- Auto-forward to LPCHROUTER
            local ok, err = pcall(function()
                SendToModality(instanceId, 'LPCHROUTER')
            end)
            if ok then
                print('   ✅ Forwarded to LPCHROUTER')
            else
                print('   ❌ Failed to forward to LPCHROUTER: ' .. tostring(err))
            end
        end
    end
end

print('🔧 SVRTK Fetal MRI Auto-Processing Script v2.0 Loaded Successfully')
print('   Features: Intelligent series detection, automated study forwarding, result tracking')
print('   Integration: Works with intelligent_svrtk_processor.py for optimal reconstruction')