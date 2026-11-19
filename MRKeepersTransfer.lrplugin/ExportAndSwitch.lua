local LrApplication = import 'LrApplication'
local LrBinding = import 'LrBinding'
local LrColor = import 'LrColor'
local LrDialogs = import 'LrDialogs'
local LrExportSession = import 'LrExportSession'
local LrFileUtils = import 'LrFileUtils'
local LrFunctionContext = import 'LrFunctionContext'
local LrPathUtils = import 'LrPathUtils'
local LrPrefs = import 'LrPrefs'
local LrProgressScope = import 'LrProgressScope'
local LrTasks = import 'LrTasks'
local LrView = import 'LrView'

-- CRITICAL: In Lightroom Classic's Lua 5.1 VM, SDK methods (photo:getRawMetadata, catalog:findPhotos,
-- LrTasks.execute, catalog:withWriteAccessDo, etc.) yield the coroutine!
-- Standard Lua `pcall()` fails with "attempt to yield across metamethod/C-call boundary" on yielding calls.
-- Always use `LrTasks.pcall` for protected calls inside async tasks!
local taskPcall = LrTasks.pcall or pcall

local homeDir = LrPathUtils.getStandardFilePath('home') or os.getenv("HOME") or '/Users/mitch'
local pluginDir = _PLUGIN.path
local prefs = LrPrefs.prefsForPlugin()
local localQueuePath = LrPathUtils.child(homeDir, "Library/Application Support/MRDarkroom/keeper_import_queue.json")
local logFilePath = LrPathUtils.child(homeDir, "Library/Application Support/MRDarkroom/lr_plugin.log")

local function logMsg(msg)
    pcall(function()
        LrFileUtils.createAllDirectories(LrPathUtils.parent(logFilePath))
        local f = io.open(logFilePath, "a")
        if f then
            f:write(os.date("%Y-%m-%d %H:%M:%S") .. " [ExportAndSwitch] " .. tostring(msg) .. "\n")
            f:close()
        end
    end)
end

-- Safe file I/O helpers using standard Lua io.open (note: LrFileUtils does NOT have writeFile!)
local function writeTextFile(filePath, textContent)
    if not filePath then return false end
    local ok, written = pcall(function()
        local parentDir = LrPathUtils.parent(filePath)
        if parentDir then
            LrFileUtils.createAllDirectories(parentDir)
        end
        local f, err = io.open(filePath, "wb")
        if not f then
            logMsg("writeTextFile failed for " .. tostring(filePath) .. ": " .. tostring(err))
            return false
        end
        f:write(tostring(textContent or ""))
        f:close()
        return true
    end)
    return ok and (written == true)
end

local function readTextFile(filePath)
    if not filePath or not LrFileUtils.exists(filePath) then return nil end
    local content = nil
    pcall(function()
        local f = io.open(filePath, "rb")
        if f then
            content = f:read("*all")
            f:close()
        elseif LrFileUtils.readFile then
            content = LrFileUtils.readFile(filePath)
        end
    end)
    return content
end

-- Picks the active/newest .lrcat file in a directory (prefers highest -v12/-v13 suffix and newest mtime)
local function scanDirectoryForBestLrcat(dirPath)
    if not dirPath or not LrFileUtils.exists(dirPath) then return nil end
    local bestPath = nil
    local bestScore = -1

    for entry in LrFileUtils.directoryEntries(dirPath) do
        local ext = string.lower(LrPathUtils.extension(entry) or "")
        local leaf = LrPathUtils.leafName(entry) or ""
        if ext == "lrcat" and not string.match(leaf, "^%._") then
            local vNum = tonumber(string.match(leaf, "%-v(%d+)%.lrcat$")) or 0
            local mtime = 0
            local attrs = LrFileUtils.fileAttributes(entry)
            if attrs and attrs.fileModificationDate then
                mtime = tonumber(attrs.fileModificationDate) or 0
            end
            local score = (vNum * 10000000000) + mtime
            if score > bestScore then
                bestScore = score
                bestPath = entry
            end
        end
    end
    return bestPath
end

local function resolveImagesFolderForCatalogDir(folderPath, preferredSubdirs)
    if preferredSubdirs then
        for _, sub in ipairs(preferredSubdirs) do
            local cand = LrPathUtils.child(folderPath, sub)
            if LrFileUtils.exists(cand) == "directory" then
                return cand
            end
        end
    end
    for _, fallback in ipairs({ "Images", "Keepers Images", "Keepers" }) do
        local cand = LrPathUtils.child(folderPath, fallback)
        if LrFileUtils.exists(cand) == "directory" then
            return cand
        end
    end
    return LrPathUtils.child(folderPath, "Images")
end

local function isSystemOrHiddenVolume(volName)
    local lower = string.lower(volName or "")
    if lower == "" or string.sub(lower, 1, 1) == "." then return true end
    if lower == "macintosh hd" or lower == "macintosh hd - data" or lower == "recovery" or lower == "preboot" or lower == "vm" or lower == "update" then
        return true
    end
    return false
end

local function isExcludedSubfolder(folderName)
    local lower = string.lower(folderName or "")
    if lower == "" or string.sub(lower, 1, 1) == "." or string.sub(lower, 1, 1) == "$" then return true end
    if lower == "operating files (do not touch)" or lower == "mr_darkroom_studio" or lower == "guides and plugins" or lower == "system volume information" or lower == "backups" or lower == "old lightroom catalogs" then
        return true
    end
    if string.match(lower, "%.app$") or string.match(lower, "%.lrdata$") or string.match(lower, "%.lrplugin$") then
        return true
    end
    return false
end

local function discoverCatalogs(currentCatPath)
    local catalogs = {}
    local seenLrcat = {}

    local targetDefs = {
        {
            key = "landscape_keepers",
            name = "Landscape Keepers",
            rel_folder = "Landscape Keepers",
            img_subdirs = { "Images" },
        },
        {
            key = "aerial_keepers",
            name = "Aerial Keepers",
            rel_folder = "Aerial Keepers",
            img_subdirs = { "Keepers Images", "Images" },
        },
        {
            key = "family_catalog",
            name = "Family Catalog",
            rel_folder = "Family Catalog",
            img_subdirs = { "Images" },
        },
        {
            key = "aerial_catalog",
            name = "Aerial Catalog",
            rel_folder = "Aerial Catalog",
            img_subdirs = { "Images", "Keepers Images" },
        },
        {
            key = "pegasus_terrestrial",
            name = "Pegasus Terrestrial Keepers",
            rel_folder = "7 Terestrial Catalog/KEEPERS/Terestrial Keepers ",
            img_subdirs = { "Images/Landscape and Pano Keepers", "Images" },
        },
    }

    local candidateRoots = {}
    local seenRoot = {}
    local function addCandidateRoot(volPath)
        if volPath and not seenRoot[volPath] and LrFileUtils.exists(volPath) == "directory" then
            seenRoot[volPath] = true
            table.insert(candidateRoots, volPath)
        end
    end

    -- Explicitly probe standard external drives first in case /Volumes listing is restricted by macOS TCC
    addCandidateRoot("/Volumes/2TB_Archive")
    addCandidateRoot("/Volumes/Pegasus32 R8")

    if LrFileUtils.exists("/Volumes") then
        for vol in LrFileUtils.directoryEntries("/Volumes") do
            local vName = LrPathUtils.leafName(vol) or ""
            if LrFileUtils.exists(vol) == "directory" and not isSystemOrHiddenVolume(vName) then
                addCandidateRoot(vol)
            end
        end
    end

    -- Sort external volumes so 2TB / Archive / SSD drives appear first
    table.sort(candidateRoots, function(a, b)
        local la = string.lower(LrPathUtils.leafName(a) or "")
        local lb = string.lower(LrPathUtils.leafName(b) or "")
        local aPri = (string.find(la, "2tb") or string.find(la, "archive") or string.find(la, "ssd")) and 0 or 1
        local bPri = (string.find(lb, "2tb") or string.find(lb, "archive") or string.find(lb, "ssd")) and 0 or 1
        if aPri ~= bPri then return aPri < bPri end
        return la < lb
    end)

    if homeDir then
        local pics = LrPathUtils.child(homeDir, "Pictures")
        if LrFileUtils.exists(pics) == "directory" then table.insert(candidateRoots, pics) end
        local desk = LrPathUtils.child(homeDir, "Desktop")
        if LrFileUtils.exists(desk) == "directory" then table.insert(candidateRoots, desk) end
    end

    -- 1. Match known catalog definitions across all mounted volumes
    for _, rootDir in ipairs(candidateRoots) do
        local rootName = LrPathUtils.leafName(rootDir) or "Drive"
        for _, def in ipairs(targetDefs) do
            local folderPath = LrPathUtils.child(rootDir, def.rel_folder)
            if LrFileUtils.exists(folderPath) == "directory" then
                local lrcat = scanDirectoryForBestLrcat(folderPath)
                if lrcat and not seenLrcat[lrcat] and lrcat ~= currentCatPath then
                    seenLrcat[lrcat] = true
                    local imgFolder = resolveImagesFolderForCatalogDir(folderPath, def.img_subdirs)
                    table.insert(catalogs, {
                        key = def.key .. "_" .. rootName,
                        name = def.name,
                        volume = rootName,
                        catalog_path = lrcat,
                        images_folder = imgFolder,
                        display_label = string.format("%s  [%s]", def.name, rootName),
                    })
                end
            end
        end
    end

    -- 2. Dynamic scan of top-level folders on all external volumes for any other .lrcat catalogs
    for _, rootDir in ipairs(candidateRoots) do
        local rootName = LrPathUtils.leafName(rootDir) or "Drive"
        if rootDir ~= LrPathUtils.child(homeDir, "Pictures") and rootDir ~= LrPathUtils.child(homeDir, "Desktop") then
            for subDir in LrFileUtils.directoryEntries(rootDir) do
                local subName = LrPathUtils.leafName(subDir) or ""
                if LrFileUtils.exists(subDir) == "directory" and not isExcludedSubfolder(subName) then
                    local lrcat = scanDirectoryForBestLrcat(subDir)
                    if lrcat and not seenLrcat[lrcat] and lrcat ~= currentCatPath then
                        seenLrcat[lrcat] = true
                        local imgFolder = resolveImagesFolderForCatalogDir(subDir, nil)
                        table.insert(catalogs, {
                            key = "dyn_" .. string.gsub(string.lower(subName .. "_" .. rootName), "[^a-z0-9_]", "_"),
                            name = subName,
                            volume = rootName,
                            catalog_path = lrcat,
                            images_folder = imgFolder,
                            display_label = string.format("%s  [%s]", subName, rootName),
                        })
                    end
                end
            end
        end
    end

    -- 3. Saved custom catalog (if previously browsed by user)
    if prefs.customCatalogPath and LrFileUtils.exists(prefs.customCatalogPath) then
        local catPath = prefs.customCatalogPath
        if not seenLrcat[catPath] and catPath ~= currentCatPath then
            seenLrcat[catPath] = true
            local catName = prefs.customCatalogName or LrPathUtils.leafName(catPath)
            local imgFolder = prefs.customImagesFolder or LrPathUtils.parent(catPath)
            table.insert(catalogs, {
                key = "custom_saved",
                name = catName,
                volume = "Custom",
                catalog_path = catPath,
                images_folder = imgFolder,
                display_label = string.format("%s  [Saved Custom]", catName),
                is_custom = true,
            })
        end
    end

    return catalogs
end

-- Checks if a photo has a 5-star rating WITHOUT standard `pcall` (since getRawMetadata yields in Lua 5.1!)
local function isPhotoFiveStars(photo)
    if not photo then return false end
    local rawRating = photo:getRawMetadata("rating")
    if tonumber(rawRating) == 5 then
        return true
    end
    local fmtRating = photo:getFormattedMetadata("rating")
    if tonumber(fmtRating) == 5 or (type(fmtRating) == "string" and string.find(fmtRating, "5")) then
        return true
    end
    return false
end

-- Unique key for a Lightroom photo object (by file path first, fallback to localIdentifier/tostring)
local function getPhotoUniqueKey(photo)
    if not photo then return "" end
    local pPath = photo:getRawMetadata("path")
    if pPath and #pPath > 0 then
        return pPath
    end
    if photo.localIdentifier then
        return "id:" .. tostring(photo.localIdentifier)
    end
    return tostring(photo)
end

-- Checks if a photo has already been exported as DNG (or original filename) into destImagesFolder
local function getExistingExportedPathInFolder(photo, destImagesFolder)
    if not photo or not destImagesFolder or not LrFileUtils.exists(destImagesFolder) then
        return nil
    end
    local srcPath = photo:getRawMetadata("path")
    if not srcPath or #srcPath == 0 then return nil end
    local leaf = LrPathUtils.leafName(srcPath) or ""
    local stem = LrPathUtils.removeExtension(leaf) or leaf
    if #stem == 0 then return nil end

    for _, ext in ipairs({ ".dng", ".DNG" }) do
        local cand = LrPathUtils.child(destImagesFolder, stem .. ext)
        if LrFileUtils.exists(cand) == "file" then
            return cand
        end
    end
    local origCand = LrPathUtils.child(destImagesFolder, leaf)
    if LrFileUtils.exists(origCand) == "file" then
        return origCand
    end
    return nil
end

local function findFiveStarPhotosInCatalog(catalog)
    local foundMap = {}
    local allFiveStars = {}
    local selectedFiveStars = {}
    local selectedMap = {}
    local targetPhotos = {}

    local function addFiveStar(p, isSelected)
        if not p then return end
        local key = getPhotoUniqueKey(p)
        if not foundMap[key] then
            foundMap[key] = true
            table.insert(allFiveStars, p)
        end
        if isSelected and not selectedMap[key] then
            selectedMap[key] = true
            table.insert(selectedFiveStars, p)
        end
    end

    -- 1. Check user's current selection / target photos first
    taskPcall(function()
        targetPhotos = catalog:getTargetPhotos() or {}
        for _, p in ipairs(targetPhotos) do
            if isPhotoFiveStars(p) then
                addFiveStar(p, true)
            end
        end
    end)

    -- 2. Also check catalog:getMultipleSelectedOrAllPhotos() in case Loupe view only returned 1 target photo
    taskPcall(function()
        local multiSel = catalog:getMultipleSelectedOrAllPhotos() or {}
        local everyCount = #(catalog:getAllPhotos() or {})
        local isExplicitMultiSelection = (#multiSel > 1 and #multiSel < everyCount)
        if isExplicitMultiSelection and #multiSel > #targetPhotos then
            targetPhotos = multiSel
        end
        for _, p in ipairs(multiSel) do
            if isPhotoFiveStars(p) then
                addFiveStar(p, isExplicitMultiSelection)
            end
        end
    end)

    -- 3. ALWAYS scan catalog:getAllPhotos() across the entire catalog so we NEVER stop after just 1 selected photo!
    taskPcall(function()
        local everyPhoto = catalog:getAllPhotos() or {}
        if #everyPhoto > 0 then
            local batchRatings = catalog:batchGetRawMetadata(everyPhoto, { "rating" })
            for _, p in ipairs(everyPhoto) do
                local r = batchRatings and batchRatings[p] and batchRatings[p].rating
                if tonumber(r) == 5 or isPhotoFiveStars(p) then
                    addFiveStar(p, false)
                end
            end
        end
    end)

    -- 4. Also run catalog:findPhotos as an additional check
    taskPcall(function()
        local searched = catalog:findPhotos {
            searchDesc = {
                criteria = "rating",
                operation = "==",
                value = 5,
            }
        }
        if searched then
            for _, p in ipairs(searched) do
                addFiveStar(p, false)
            end
        end
    end)

    return allFiveStars, selectedFiveStars, targetPhotos
end

-- Check if there is a pending queue targeting the currently open catalog and import it if requested
local function checkPendingQueueForCurrentCatalog(catalog)
    local currentCatPath = catalog:getPath()
    if not currentCatPath or #currentCatPath == 0 then return false end

    local candidateQueues = { localQueuePath }
    local catDir = LrPathUtils.parent(currentCatPath)
    if catDir then
        table.insert(candidateQueues, LrPathUtils.child(catDir, ".keeper_import_queue.json"))
    end
    if LrFileUtils.exists("/Volumes") then
        for vol in LrFileUtils.directoryEntries("/Volumes") do
            table.insert(candidateQueues, LrPathUtils.child(vol, ".keeper_import_queue.json"))
        end
    end

    local activeQueue = nil
    local content = nil
    for _, qp in ipairs(candidateQueues) do
        if LrFileUtils.exists(qp) then
            local c = readTextFile(qp)
            if c and #c > 0 then
                local targetCat = string.match(c, '"target_catalog":%s*"([^"]+)"') or ""
                local curLeaf = string.lower(LrPathUtils.leafName(currentCatPath) or "")
                local targetLeaf = string.lower(LrPathUtils.leafName(targetCat) or "")
                if curLeaf == targetLeaf or currentCatPath == targetCat then
                    activeQueue = qp
                    content = c
                    break
                end
            end
        end
    end

    if not activeQueue or not content then return false end

    local photoPaths = {}
    local photosBlock = string.match(content, '"photos"%s*:%s*%[(.-)%]') or content
    for p in string.gmatch(photosBlock, '"([^"]+)"') do
        local ext = string.lower(LrPathUtils.extension(p) or "")
        if (ext == "dng" or ext == "tif" or ext == "tiff" or ext == "jpg" or ext == "jpeg") and LrFileUtils.exists(p) then
            table.insert(photoPaths, p)
        end
    end

    if #photoPaths == 0 then
        for _, qp in ipairs(candidateQueues) do
            if LrFileUtils.exists(qp) then
                pcall(function() LrFileUtils.delete(qp) end)
            end
        end
        return false
    end

    local catalogName = string.match(content, '"catalog_name":%s*"([^"]+)"') or LrPathUtils.leafName(currentCatPath)
    local importedPhotos = {}
    local newlyAddedCount = 0
    local skippedExistingCount = 0
    catalog:withWriteAccessDo("Import Pending 5★ Keepers", function()
        for _, p in ipairs(photoPaths) do
            local existing = nil
            taskPcall(function()
                existing = catalog:findPhotoByPath(p)
            end)
            if existing then
                skippedExistingCount = skippedExistingCount + 1
                table.insert(importedPhotos, existing)
            else
                local photo = nil
                taskPcall(function()
                    photo = catalog:addPhoto(p)
                end)
                if photo then
                    newlyAddedCount = newlyAddedCount + 1
                    table.insert(importedPhotos, photo)
                end
            end
        end
        if #importedPhotos > 0 then
            local colName = "Keepers Imported - " .. os.date("%Y-%m-%d %H:%M")
            local col = catalog:createCollection(colName, nil, true)
            if col then col:addPhotos(importedPhotos) end
        end
    end, { timeout = 30 })

    for _, qp in ipairs(candidateQueues) do
        if LrFileUtils.exists(qp) then
            pcall(function() LrFileUtils.delete(qp) end)
        end
    end

    if #importedPhotos > 0 then
        taskPcall(function() catalog:setSelectedPhotos(importedPhotos[1], importedPhotos) end)
        LrDialogs.message(
            "MR Keepers Transfer",
            string.format("✓ Imported %d pending 5★ Keeper DNG(s) into '%s'!", #importedPhotos, catalogName),
            "info"
        )
        return true
    end
    return false
end

LrFunctionContext.postAsyncTaskWithContext("MRKeepersTransferTask", function(context)
    local okTask, taskErr = taskPcall(function()
        logMsg("Triggered Send 5★ Keepers to Destination Catalog...")

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            LrDialogs.message("MR Keepers Transfer", "No active catalog is currently open in Lightroom Classic.", "warning")
            return
        end

        -- 0. If this catalog has pending incoming keepers waiting in queue, import them right away
        local importedPending = false
        taskPcall(function()
            importedPending = checkPendingQueueForCurrentCatalog(catalog)
        end)
        if importedPending then
            return
        end

        -- 1. Find 5-star photos in current catalog
        local allFiveStarPhotos, selectedFiveStars, targetPhotos = findFiveStarPhotosInCatalog(catalog)
        logMsg(string.format("Found %d total 5-star photos, %d selected 5-star photos, %d target photos", #allFiveStarPhotos, #selectedFiveStars, #targetPhotos))

        local photosToExport = allFiveStarPhotos
        if #allFiveStarPhotos == 0 then
            if #targetPhotos > 0 then
                local confirm = LrDialogs.confirm(
                    "No 5★ Photos Found in Catalog",
                    string.format("No 5-star (★★★★★) photos were found, but you currently have %d photo(s) selected in the view.\n\nWould you like to transfer your %d selected photo(s) as Keepers?", #targetPhotos, #targetPhotos),
                    "Transfer Selected Photos",
                    "Cancel"
                )
                if confirm ~= "ok" then return end
                photosToExport = targetPhotos
            else
                LrDialogs.message(
                    "No 5★ Keepers Found",
                    "No 5-star (★★★★★) photos were found in this catalog.\n\nPlease rate your keeper photos 5 Stars (press '5' in Lightroom) and run 'Send 5★ Keepers to Destination Catalog...' again.",
                    "info"
                )
                return
            end
        end

        -- 2. Discover available target catalogs dynamically across all mounted drives
        local currentCatPath = catalog:getPath() or ""
        local availableCatalogs = discoverCatalogs(currentCatPath)
        logMsg(string.format("Discovered %d destination catalog(s)", #availableCatalogs))

        -- 3. Set up observable UI property table bound to FunctionContext
        local f = LrView.osFactory()
        local props = LrBinding.makePropertyTable(context)

        local initialKey = "custom_manual"
        if #availableCatalogs > 0 then
            initialKey = availableCatalogs[1].key
            local lastKey = prefs.lastTargetCatalogKey
            if lastKey then
                for _, c in ipairs(availableCatalogs) do
                    if c.key == lastKey then
                        initialKey = c.key
                        break
                    end
                end
            end
        end

        props.selectedKey = initialKey
        props.autoSwitch = (prefs.lastAutoSwitch ~= false)
        -- Default to exporting ALL 5-star photos in the catalog (never limit to 1 highlighted photo by accident!)
        props.useSelectedOnly = false
        props.skipDuplicates = true
        props.includeAllSelectedInView = false
        props.customChosenPath = prefs.customCatalogPath or ""
        props.customPathDisplay = (prefs.customCatalogPath and ("Selected: " .. prefs.customCatalogPath)) or "Click 'Browse...' to select any .lrcat catalog or destination folder"

        -- 4. Build catalog radio rows
        local catalogColumnSpec = { spacing = 3 }

        if #availableCatalogs == 0 then
            table.insert(catalogColumnSpec, f:static_text {
                title = "⚠️ No external archive drive detected in /Volumes. Plug in your 2TB Archive SSD or choose a folder below:",
                text_color = LrColor(0.85, 0.35, 0.1),
                font = "<system/bold>",
            })
            table.insert(catalogColumnSpec, f:spacer { height = 4 })
        end

        for _, c in ipairs(availableCatalogs) do
            table.insert(catalogColumnSpec, f:row {
                f:radio_button {
                    title = c.display_label,
                    value = LrView.bind 'selectedKey',
                    checked_value = c.key,
                    font = "<system/bold>",
                },
            })
            table.insert(catalogColumnSpec, f:row {
                margin_left = 22,
                f:static_text {
                    title = "Catalog: " .. LrPathUtils.leafName(c.catalog_path) .. "   |   Images: " .. c.images_folder,
                    font = "<system/small>",
                    text_color = LrColor(0.4, 0.4, 0.4),
                    fill_horizontal = 1,
                },
            })
            table.insert(catalogColumnSpec, f:spacer { height = 4 })
        end

        -- Manual Browse option (always visible)
        table.insert(catalogColumnSpec, f:row {
            f:radio_button {
                title = "Choose Another Catalog (.lrcat) or Folder Manually...",
                value = LrView.bind 'selectedKey',
                checked_value = 'custom_manual',
                font = "<system/bold>",
            },
            f:push_button {
                title = "Browse...",
                action = function()
                    local picked = LrDialogs.runOpenPanel {
                        title = "Select Destination Catalog (.lrcat) or Folder",
                        canChooseFiles = true,
                        canChooseDirectories = true,
                        allowsMultipleSelection = false,
                        fileTypes = { "lrcat" },
                    }
                    if picked and #picked > 0 then
                        local p = picked[1]
                        props.customChosenPath = p
                        props.selectedKey = 'custom_manual'
                        props.customPathDisplay = "Selected: " .. p
                    end
                end
            }
        })
        table.insert(catalogColumnSpec, f:row {
            margin_left = 22,
            f:static_text {
                title = LrView.bind 'customPathDisplay',
                font = "<system/small>",
                text_color = LrColor(0.2, 0.45, 0.8),
                fill_horizontal = 1,
            }
        })

        local countText = string.format("Ready to transfer %d 5★ Keeper photo(s) as full-resolution DNG", #photosToExport)
        if #selectedFiveStars > 0 and #selectedFiveStars < #allFiveStarPhotos then
            countText = string.format("Found %d total 5★ photos in catalog (%d currently highlighted)", #allFiveStarPhotos, #selectedFiveStars)
        end

        local dialogRows = {
            bind_to_object = props,
            spacing = f:control_spacing(),
            width = 580,

            f:row {
                f:static_text {
                    title = countText,
                    font = "<system/bold>",
                    fill_horizontal = 1,
                },
            },
            f:row {
                f:checkbox {
                    title = "Skip duplicate exports (automatically skip 5★ photos already in destination catalog)",
                    value = LrView.bind 'skipDuplicates',
                    font = "<system/bold>",
                },
            },
        }

        if #selectedFiveStars > 1 and #selectedFiveStars < #allFiveStarPhotos then
            table.insert(dialogRows, f:row {
                f:checkbox {
                    title = string.format("Transfer only the %d currently selected 5★ photos (uncheck to transfer all %d new 5★ photos)", #selectedFiveStars, #allFiveStarPhotos),
                    value = LrView.bind 'useSelectedOnly',
                },
            })
        end

        if #targetPhotos > 1 and #targetPhotos > #selectedFiveStars and #targetPhotos < 100 then
            table.insert(dialogRows, f:row {
                f:checkbox {
                    title = string.format("Also include all %d currently selected photos in view (even if rated under 5★)", #targetPhotos),
                    value = LrView.bind 'includeAllSelectedInView',
                },
            })
        end

        table.insert(dialogRows, f:separator { fill_horizontal = 1 })
        table.insert(dialogRows, f:spacer { height = 2 })
        table.insert(dialogRows, f:static_text {
            title = "Select Destination Catalog:",
            font = "<system/bold>",
        })
        table.insert(dialogRows, f:column(catalogColumnSpec))
        table.insert(dialogRows, f:separator { fill_horizontal = 1 })
        table.insert(dialogRows, f:spacer { height = 2 })
        table.insert(dialogRows, f:checkbox {
            title = "Automatically close this catalog, open destination catalog, and import Keepers",
            value = LrView.bind 'autoSwitch',
            font = "<system/bold>",
        })

        local viewContents = f:column(dialogRows)

        -- 5. Present modal dialog
        local action = LrDialogs.presentModalDialog {
            title = "MR Keepers Transfer — Send 5★ Keepers to Catalog",
            contents = viewContents,
            actionVerb = "Transfer Keepers (DNG)",
            cancelVerb = "Cancel",
        }

        if action ~= "ok" then
            logMsg("User cancelled modal dialog.")
            return
        end

        -- 6. Resolve chosen destination catalog
        local chosenCatalog = nil
        if props.selectedKey == "custom_manual" then
            local chosenPath = props.customChosenPath
            if not chosenPath or #chosenPath == 0 or not LrFileUtils.exists(chosenPath) then
                local picked = LrDialogs.runOpenPanel {
                    title = "Select Destination Catalog (.lrcat) or Folder",
                    canChooseFiles = true,
                    canChooseDirectories = true,
                    allowsMultipleSelection = false,
                    fileTypes = { "lrcat" },
                }
                if picked and #picked > 0 then
                    chosenPath = picked[1]
                else
                    LrDialogs.message("MR Keepers Transfer", "No destination catalog or folder was selected.", "warning")
                    return
                end
            end

            local catPath = ""
            local imgFolder = ""
            local catName = LrPathUtils.leafName(chosenPath)

            if string.lower(LrPathUtils.extension(chosenPath) or "") == "lrcat" then
                catPath = chosenPath
                local parent = LrPathUtils.parent(chosenPath)
                imgFolder = resolveImagesFolderForCatalogDir(parent, nil)
            else
                local insideLrcat = scanDirectoryForBestLrcat(chosenPath)
                if insideLrcat then
                    catPath = insideLrcat
                    catName = LrPathUtils.leafName(insideLrcat)
                    imgFolder = resolveImagesFolderForCatalogDir(chosenPath, nil)
                else
                    catPath = ""
                    imgFolder = chosenPath
                end
            end

            chosenCatalog = {
                key = "custom_manual",
                name = catName,
                volume = "Custom",
                catalog_path = catPath,
                images_folder = imgFolder,
                display_label = catName,
            }

            if #catPath > 0 then
                prefs.customCatalogPath = catPath
                prefs.customCatalogName = catName
                prefs.customImagesFolder = imgFolder
            end
        else
            for _, c in ipairs(availableCatalogs) do
                if c.key == props.selectedKey then
                    chosenCatalog = c
                    break
                end
            end
        end

        if not chosenCatalog then
            LrDialogs.message("MR Keepers Transfer", "Please select a valid destination catalog.", "warning")
            return
        end

        prefs.lastTargetCatalogKey = props.selectedKey
        prefs.lastAutoSwitch = props.autoSwitch

        if props.useSelectedOnly and #selectedFiveStars > 0 then
            photosToExport = selectedFiveStars
        end

        if props.includeAllSelectedInView and #targetPhotos > 1 then
            local merged = {}
            local seenKey = {}
            for _, p in ipairs(photosToExport) do
                local k = getPhotoUniqueKey(p)
                seenKey[k] = true
                table.insert(merged, p)
            end
            for _, p in ipairs(targetPhotos) do
                local k = getPhotoUniqueKey(p)
                if not seenKey[k] then
                    seenKey[k] = true
                    table.insert(merged, p)
                end
            end
            photosToExport = merged
        end

        if #photosToExport == 0 then
            LrDialogs.message("MR Keepers Transfer", "No photos available to export.", "warning")
            return
        end

        LrFileUtils.createAllDirectories(chosenCatalog.images_folder)

        -- Filter out photos that have ALREADY been exported to chosenCatalog.images_folder
        -- so we only export NEW Keepers and never create duplicate -2.dng files!
        local newPhotosToExport = {}
        local alreadyExportedPaths = {}
        for _, p in ipairs(photosToExport) do
            local existingDng = getExistingExportedPathInFolder(p, chosenCatalog.images_folder)
            if existingDng then
                table.insert(alreadyExportedPaths, existingDng)
                if not props.skipDuplicates then
                    table.insert(newPhotosToExport, p)
                end
            else
                table.insert(newPhotosToExport, p)
            end
        end

        local exportedDngs = {}
        local exportErrors = {}

        if #newPhotosToExport == 0 and #alreadyExportedPaths > 0 then
            local choice = LrDialogs.confirm(
                "All 5★ Keepers Already Exported",
                string.format("All %d 5★ Keeper(s) already exist in '%s'.\n\nWould you like to open '%s' (making sure all %d are imported without duplicating) or re-export and overwrite the DNG files?", #alreadyExportedPaths, chosenCatalog.images_folder, chosenCatalog.name, #alreadyExportedPaths),
                "Open Catalog (Skip Re-Export)",
                "Cancel",
                "Re-Export & Overwrite DNGs"
            )
            if choice == "cancel" then
                return
            elseif choice == "other" then
                newPhotosToExport = photosToExport
            else
                exportedDngs = alreadyExportedPaths
            end
        end

        if #newPhotosToExport > 0 then
            logMsg(string.format("Exporting %d NEW photo(s) as DNG to %s (skipped %d already on disk; catalog: %s)", #newPhotosToExport, chosenCatalog.images_folder, #alreadyExportedPaths, chosenCatalog.catalog_path))

            -- 7. Export photos as DNG with all Lightroom develop edits embedded
            -- Use 'overwrite' instead of 'rename' so we never create duplicate -2.dng files!
            local exportSettings = {
                LR_format = 'DNG',
                LR_export_destinationType = 'specificFolder',
                LR_export_destinationPathPrefix = chosenCatalog.images_folder,
                LR_export_useSubfolder = false,
                LR_collisionHandling = 'overwrite',
                LR_reimportExportedPhoto = false,
            }

            local exportSession = LrExportSession {
                photosToExport = newPhotosToExport,
                exportSettings = exportSettings,
            }

            local progressScope = LrProgressScope {
                title = string.format("Exporting %d 5★ Keepers as DNG to %s...", #newPhotosToExport, chosenCatalog.name),
            }

            for _, rendition in exportSession:renditions({ stopIfCanceled = true }) do
                local success, pathOrMsg = rendition:waitForRender()
                if success then
                    table.insert(exportedDngs, pathOrMsg)
                else
                    table.insert(exportErrors, tostring(pathOrMsg))
                end
            end
            progressScope:done()
        end

        -- Also include any previously exported DNGs in the queue manifest so Init.lua ensures
        -- they are present in the destination catalog (Init.lua skips any already in the catalog)
        if #alreadyExportedPaths > 0 then
            local inManifest = {}
            for _, p in ipairs(exportedDngs) do inManifest[p] = true end
            for _, p in ipairs(alreadyExportedPaths) do
                if not inManifest[p] then
                    inManifest[p] = true
                    table.insert(exportedDngs, p)
                end
            end
        end

        if #exportedDngs == 0 then
            local errDetail = (#exportErrors > 0) and ("\n\nDetails: " .. table.concat(exportErrors, "; ")) or ""
            LrDialogs.message("MR Keepers Transfer", "Export did not produce any DNG files or was cancelled." .. errDetail, "warning")
            return
        end

        logMsg(string.format("Prepared %d DNG file(s) for destination catalog (%d newly rendered).", #exportedDngs, #newPhotosToExport))

        -- 8. Write queue manifest to local App Support AND destination catalog folder
        local queueData = string.format('{\n  "target_catalog": "%s",\n  "catalog_name": "%s",\n  "photos": [\n',
            chosenCatalog.catalog_path:gsub('\\', '\\\\'),
            chosenCatalog.name:gsub('"', '\\"')
        )
        for i, p in ipairs(exportedDngs) do
            queueData = queueData .. string.format('    "%s"%s\n', p:gsub('\\', '\\\\'), (i < #exportedDngs and "," or ""))
        end
        queueData = queueData .. '  ]\n}\n'

        writeTextFile(localQueuePath, queueData)

        local catParentDir = (#chosenCatalog.catalog_path > 0) and LrPathUtils.parent(chosenCatalog.catalog_path) or nil
        if catParentDir and LrFileUtils.exists(catParentDir) then
            writeTextFile(LrPathUtils.child(catParentDir, ".keeper_import_queue.json"), queueData)
        end

        local parentDir = LrPathUtils.parent(chosenCatalog.images_folder)
        if parentDir and parentDir ~= catParentDir and LrFileUtils.exists(parentDir) then
            writeTextFile(LrPathUtils.child(parentDir, ".keeper_import_queue.json"), queueData)
        end

        -- 9. If current catalog is already the destination catalog, import directly
        local isSameCatalog = (#chosenCatalog.catalog_path > 0) and (
            (currentCatPath == chosenCatalog.catalog_path) or
            (LrPathUtils.leafName(currentCatPath) == LrPathUtils.leafName(chosenCatalog.catalog_path))
        )

        if isSameCatalog then
            local importedPhotos = {}
            catalog:withWriteAccessDo("Import Keepers Directly", function()
                for _, dngPath in ipairs(exportedDngs) do
                    local existing = nil
                    taskPcall(function()
                        existing = catalog:findPhotoByPath(dngPath)
                    end)
                    if existing then
                        table.insert(importedPhotos, existing)
                    else
                        local photo = nil
                        taskPcall(function()
                            photo = catalog:addPhoto(dngPath)
                        end)
                        if photo then
                            table.insert(importedPhotos, photo)
                        end
                    end
                end
                if #importedPhotos > 0 then
                    local colName = "Keepers Imported - " .. os.date("%Y-%m-%d %H:%M")
                    local col = catalog:createCollection(colName, nil, true)
                    if col then col:addPhotos(importedPhotos) end
                end
            end, { timeout = 30 })

            pcall(function() LrFileUtils.delete(localQueuePath) end)

            if #importedPhotos > 0 then
                taskPcall(function() catalog:setSelectedPhotos(importedPhotos[1], importedPhotos) end)
                LrDialogs.showBezel(string.format("✓ %d Keepers imported into %s!", #importedPhotos, chosenCatalog.name), 4)
            end
            return
        end

        -- 10. Switch to destination catalog and auto-import via Init.lua
        -- CRITICAL: Do NOT wrap LrTasks.execute in standard Lua `pcall` (it yields in Lua 5.1!).
        -- Also launch switch_catalog.sh with `nohup` so Lightroom quitting does not kill the script.
        if props.autoSwitch and #chosenCatalog.catalog_path > 0 then
            LrDialogs.showBezel(string.format("✓ Exported %d Keepers! Opening %s...", #exportedDngs, chosenCatalog.name), 3)
            LrTasks.sleep(0.5)

            local switchScript = LrPathUtils.child(pluginDir, "switch_catalog.sh")
            local cmd = string.format('nohup /bin/bash "%s" "%s" </dev/null >> "%s" 2>&1 &', switchScript, chosenCatalog.catalog_path, logFilePath)
            logMsg("Executing catalog switch: " .. cmd)
            LrTasks.execute(cmd)
        else
            LrDialogs.message(
                "Keepers Exported Successfully",
                string.format("Exported %d full-resolution DNG Keeper(s) to:\n%s\n\nThey will be imported automatically the next time you open '%s'.", #exportedDngs, chosenCatalog.images_folder, chosenCatalog.name),
                "info"
            )
        end
    end)

    if not okTask then
        logMsg("CRITICAL ERROR: " .. tostring(taskErr))
        LrDialogs.message(
            "MR Keepers Transfer Error",
            "An unexpected error occurred while running MR Keepers Transfer:\n\n" .. tostring(taskErr),
            "critical"
        )
    end
end)
