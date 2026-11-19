local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local LrDialogs = import 'LrDialogs'

local homeDir = LrPathUtils.getStandardFilePath('home') or os.getenv("HOME") or '/Users/mitch'
local localQueuePath = LrPathUtils.child(homeDir, "Library/Application Support/MRDarkroom/keeper_import_queue.json")
local logFilePath = LrPathUtils.child(homeDir, "Library/Application Support/MRDarkroom/lr_plugin.log")

local isImporting = false

local function logMsg(msg)
    pcall(function()
        LrFileUtils.createAllDirectories(LrPathUtils.parent(logFilePath))
        local f = io.open(logFilePath, "a")
        if f then
            f:write(os.date("%Y-%m-%d %H:%M:%S") .. " [Init] " .. tostring(msg) .. "\n")
            f:close()
        end
    end)
end

local function findActiveQueuePath(currentCatPath)
    if LrFileUtils.exists(localQueuePath) then
        return localQueuePath
    end
    if currentCatPath and #currentCatPath > 0 then
        local catDir = LrPathUtils.parent(currentCatPath)
        if catDir then
            local catQueue = LrPathUtils.child(catDir, ".keeper_import_queue.json")
            if LrFileUtils.exists(catQueue) then
                return catQueue
            end
        end
    end
    local foundVolQueue = nil
    pcall(function()
        if LrFileUtils.exists("/Volumes") then
            for vol in LrFileUtils.directoryEntries("/Volumes") do
                local cand = LrPathUtils.child(vol, ".keeper_import_queue.json")
                if LrFileUtils.exists(cand) then
                    foundVolQueue = cand
                    break
                end
            end
        end
    end)
    return foundVolQueue
end

local function clearAllQueueFiles(currentCatPath, activeQueuePath)
    if activeQueuePath and LrFileUtils.exists(activeQueuePath) then
        pcall(function() LrFileUtils.delete(activeQueuePath) end)
    end
    if LrFileUtils.exists(localQueuePath) then
        pcall(function() LrFileUtils.delete(localQueuePath) end)
    end
    if currentCatPath and #currentCatPath > 0 then
        local catDir = LrPathUtils.parent(currentCatPath)
        if catDir then
            local catQueue = LrPathUtils.child(catDir, ".keeper_import_queue.json")
            if LrFileUtils.exists(catQueue) then
                pcall(function() LrFileUtils.delete(catQueue) end)
            end
        end
    end
    pcall(function()
        if LrFileUtils.exists("/Volumes") then
            for vol in LrFileUtils.directoryEntries("/Volumes") do
                local cand = LrPathUtils.child(vol, ".keeper_import_queue.json")
                if LrFileUtils.exists(cand) then
                    pcall(function() LrFileUtils.delete(cand) end)
                end
            end
        end
    end)
end

local function checkAndImportQueue()
    if isImporting then return end

    local catalog = LrApplication.activeCatalog()
    if not catalog then return end

    local currentCatPath = catalog:getPath()
    if not currentCatPath or #currentCatPath == 0 then return end

    local queuePath = findActiveQueuePath(currentCatPath)
    if not queuePath then return end

    local content = LrFileUtils.readFile(queuePath)
    if not content or #content == 0 then return end

    local targetCat = string.match(content, '"target_catalog":%s*"([^"]+)"')
    if not targetCat then return end

    local curLeaf = string.lower(LrPathUtils.leafName(currentCatPath) or "")
    local targetLeaf = string.lower(LrPathUtils.leafName(targetCat) or "")

    if curLeaf ~= targetLeaf and currentCatPath ~= targetCat then
        -- Destination catalog is not open yet; wait until it becomes active
        return
    end

    isImporting = true
    logMsg("Matched destination catalog: " .. tostring(currentCatPath) .. " from queue: " .. tostring(queuePath))

    -- Clear queue files immediately to prevent duplicate runs
    clearAllQueueFiles(currentCatPath, queuePath)

    local catalogName = string.match(content, '"catalog_name":%s*"([^"]+)"') or LrPathUtils.leafName(currentCatPath)

    local photoPaths = {}
    for p in string.gmatch(content, '"([^"]+%.dng)"') do
        if LrFileUtils.exists(p) then
            table.insert(photoPaths, p)
        end
    end
    if #photoPaths == 0 then
        for p in string.gmatch(content, '"([^"]+%.DNG)"') do
            if LrFileUtils.exists(p) then
                table.insert(photoPaths, p)
            end
        end
    end

    if #photoPaths == 0 then
        logMsg("No existing DNG files found in queue manifest.")
        isImporting = false
        return
    end

    -- Give Lightroom catalog UI a brief moment to finish opening
    LrTasks.sleep(2.0)

    local importedPhotos = {}
    local okWrite, errWrite = pcall(function()
        catalog:withWriteAccessDo("Import 5★ Keepers", function(context)
            for _, p in ipairs(photoPaths) do
                local photo = catalog:addPhoto(p)
                if photo then
                    table.insert(importedPhotos, photo)
                else
                    local existing = catalog:findPhotoByPath(p)
                    if existing then
                        table.insert(importedPhotos, existing)
                    end
                end
            end

            if #importedPhotos > 0 then
                local colName = "Keepers Imported - " .. os.date("%Y-%m-%d %H:%M")
                local col = catalog:createCollection(colName, nil, true)
                if col then
                    col:addPhotos(importedPhotos)
                end
            end
        end, { timeout = 30 })
    end)

    if not okWrite then
        logMsg("withWriteAccessDo error: " .. tostring(errWrite))
    end

    if #importedPhotos > 0 then
        pcall(function()
            catalog:setSelectedPhotos(importedPhotos[1], importedPhotos)
        end)
        LrDialogs.showBezel(string.format("✓ %d Keepers imported into %s!", #importedPhotos, catalogName), 4)
        logMsg(string.format("Imported %d keepers into %s", #importedPhotos, catalogName))
    end

    isImporting = false
end

LrTasks.startAsyncTask(function()
    LrTasks.sleep(1.5)
    pcall(checkAndImportQueue)

    while true do
        LrTasks.sleep(2.5)
        pcall(checkAndImportQueue)
    end
end)
