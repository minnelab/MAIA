function OnStableStudy(studyId, tags, metadata)

  local models_file = io.open("/etc/models.json", "r")
  local models_json = models_file:read("*a")
  models_file:close()
  local models = ParseJson(models_json)
  local study = ParseJson(RestApiGet('/studies/' .. studyId))
  local studyUID = study['MainDicomTags']['StudyInstanceUID']

  -- Check if study already has a SEG series with description "MAIA-Segmentation-Portal"
  for _, series in ipairs(study['Series'] or {}) do
    local seriesDetails = ParseJson(RestApiGet('/series/' .. series))
    local modality = seriesDetails['MainDicomTags']['Modality']
    local description = seriesDetails['MainDicomTags']['SeriesDescription']
    if modality == "SEG" and description == "MAIA-Segmentation-Portal" then
      print(">>> Skipping study " .. studyUID .. " (already has MAIA-Segmentation-Portal SEG series)")
      return
    end
  end

  -- Check each series and instance for MSP-Spleen
  for _, series in ipairs(study['Series'] or {}) do
    local seriesDetails = ParseJson(RestApiGet('/series/' .. series))
    for _, instance in ipairs(seriesDetails['Instances'] or {}) do
      local instanceTags = ParseJson(RestApiGet('/instances/' .. instance .. '/tags'))
      if instanceTags and instanceTags['0020,4000'] then
        local imageComments = instanceTags['0020,4000']['Value']
        for model, model_info in pairs(models) do
          if imageComments == model then
            print(">>> Queuing " .. model .. " study: " .. studyUID)
            -- Append UID to a queue file for external processing
            local f = io.open("/tmp/" .. model .. "_inference_queue.txt", "a")
            f:write(studyUID .. "\n")
            f:close()
            -- Stop processing further; job queued
            return
          end
        end
      end
    end
  end
end
