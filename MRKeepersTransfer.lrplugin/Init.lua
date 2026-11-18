local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local LrDialogs = import 'LrDialogs'

local homeDir = LrPathUtils.getStandardFilePath('home') or '/Users/mitch'
local localQueuePath = LrPathUtils.child(homeDir, "Library/Application Support/MRDarkroom/keeper_import_queue.json")
local ssdQueuePath = "/Volumes/2TB_Archive/.keeper_import_queue.json"

local isImporting = false

local function checkAndImportQueue()
    if isImporting then return end

    local queuePath = nil
    if LrFileUtils.exists(localQueuePath) then
        queuePath = localQueuePath
    elseif LrFileUtils.exists(ssdQueuePath) then
        queuePath = ssdQueuePath
    end

    if not queuePath then return end

    local content = LrFileUtils.readFile(queuePath)
    if not content or #content == 0 then return end

    local catalog = LrApplication.activeCatalog()
    if not catalog then return end

    local currentCatPath = catalog:getPath()
    if not currentCatPath or #currentCatPath == 0 then return end

    local targetCat = string.match(content, '"target_catalog":%s*"([^"]+)"')
    if not targetCat then return end

    local curLeaf = string.lower(LrPathUtils.leafName(currentCatPath) or "")
    local targetLeaf = string.lower(LrPathUtils.leafName(targetCat) or "")

    if curLeaf ~= targetLeaf and currentCatPath ~= targetCat then
        -- Destination catalog is not open yet; wait until it is active
        return
    end

    isImporting = true

    -- Target catalog matches! Clear the queue files immediately to avoid duplicate runs
    pcall(function() LrFileUtils.delete(queuePath) end)
    if LrFileUtils.exists(localQueuePath) then
        pcall(function() LrFileUtils.delete(localQueuePath) end)
    end
    if LrFileUtils.exists(ssdQueuePath) then
        pcall(function() LrFileUtils.delete(ssdQueuePath) end)
    end

    local catalogName = string.match(content, '"catalog_name":%s*"([^"]+)"') or curLeaf

    -- Extract DNG photo paths
    local photoPaths = {}
    for p in string.gmatch(content, '"([^"]+%.dng)"') do
        if LrFileUtils.exists(p) then
            table.insert(photoPaths, p)
        end
    end

    if #photoPaths == 0 then
        isImporting = false
        return
    end

    -- Allow catalog UI 2.5 seconds to settle
    LrTasks.sleep(2.5)

    local importedPhotos = {}
    catalog:withWriteAccessDo("Import Keepers via Plugin", function(context)
        for _, p in ipairs(photoPaths) do
            local photo = catalog:addPhoto(p)
            if photo then
                table.insert(importedPhotos, photo)
            end
        end

        if #importedPhotos > 0 then
            local colName = "Keepers Imported - " .. os.date("%Y-%m-%d %H:%M")
            local col = catalog:createCollection(colName, nil, true)
            if col then
                col:addPhotos(importedPhotos)
            end
        end
    end)

    if #importedPhotos > 0 then
        pcall(function()
            catalog:setSelectedPhotos(importedPhotos[1], importedPhotos)
        end)
        LrDialogs.showBezel(string.format("✓ %d Keepers imported into %s!", #importedPhotos, catalogName), 4)
    end

    isImporting = false
end

-- Start background listener task
LrTasks.startAsyncTask(function()
    LrTasks.sleep(2.0)
    pcall(checkAndImportQueue)

    while true do
        LrTasks.sleep(2.0)
        pcall(checkAndImportQueue)
    end
end)
