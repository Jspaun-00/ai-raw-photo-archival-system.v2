local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local LrDialogs = import 'LrDialogs'

local homeDir = LrPathUtils.getStandardFilePath('home') or '/Users/mitch'
local localQueuePath = LrPathUtils.child(homeDir, "Library/Application Support/MRDarkroom/keeper_import_queue.json")

LrTasks.startAsyncTask(function()
    local queuePath = nil
    if LrFileUtils.exists(localQueuePath) then
        queuePath = localQueuePath
    else
        -- Check any mounted volume
        pcall(function()
            if LrFileUtils.exists("/Volumes") then
                for vol in LrFileUtils.directoryEntries("/Volumes") do
                    local cand = LrPathUtils.child(vol, ".keeper_import_queue.json")
                    if LrFileUtils.exists(cand) then
                        queuePath = cand
                        break
                    end
                end
            end
        end)
    end

    if not queuePath then
        LrDialogs.message("Keepers Transfer", "No pending keepers queue found.\nAll previous exports have already been imported.", "info")
        return
    end

    local content = LrFileUtils.readFile(queuePath)
    if not content or #content == 0 then
        LrDialogs.message("Keepers Transfer", "The keepers queue file was empty.", "info")
        return
    end

    local catalog = LrApplication.activeCatalog()
    if not catalog then
        LrDialogs.message("Keepers Transfer", "No active catalog is currently open in Lightroom.", "warning")
        return
    end

    local currentCatPath = catalog:getPath()
    local targetCat = string.match(content, '"target_catalog":%s*"([^"]+)"') or ""
    local catalogName = string.match(content, '"catalog_name":%s*"([^"]+)"') or "Destination Catalog"

    local curLeaf = string.lower(LrPathUtils.leafName(currentCatPath) or "")
    local targetLeaf = string.lower(LrPathUtils.leafName(targetCat) or "")

    if #targetCat > 0 and curLeaf ~= targetLeaf and currentCatPath ~= targetCat then
        local confirm = LrDialogs.confirm(
            "Catalog Mismatch",
            string.format("These keepers were exported for:\n%s\n\nYour current catalog is:\n%s\n\nDo you want to import them into this catalog anyway?", targetCat, currentCatPath),
            "Import Anyway",
            "Cancel"
        )
        if confirm ~= "ok" then return end
    end

    -- Clear queue files
    pcall(function() LrFileUtils.delete(queuePath) end)
    if LrFileUtils.exists(localQueuePath) then pcall(function() LrFileUtils.delete(localQueuePath) end) end

    local photoPaths = {}
    for p in string.gmatch(content, '"([^"]+%.dng)"') do
        if LrFileUtils.exists(p) then
            table.insert(photoPaths, p)
        end
    end

    if #photoPaths == 0 then
        LrDialogs.message("Keepers Transfer", "None of the queued DNG files could be found on disk.", "warning")
        return
    end

    local importedPhotos = {}
    catalog:withWriteAccessDo("Manual Import Keepers", function(context)
        for _, p in ipairs(photoPaths) do
            local photo = catalog:addPhoto(p)
            if photo then
                table.insert(importedPhotos, photo)
            end
        end

        if #importedPhotos > 0 then
            local colName = "Keepers Imported - " .. os.date("%Y-%m-%d %H:%M")
            local col = catalog:createCollection(colName, nil, true)
            if col then col:addPhotos(importedPhotos) end
        end
    end)

    if #importedPhotos > 0 then
        pcall(function()
            catalog:setSelectedPhotos(importedPhotos[1], importedPhotos)
        end)
        LrDialogs.showBezel(string.format("✓ %d Keepers successfully imported into %s!", #importedPhotos, catalogName), 4)
    else
        LrDialogs.message("Keepers Transfer", "Photos could not be added (they may already exist in this catalog).", "info")
    end
end)
