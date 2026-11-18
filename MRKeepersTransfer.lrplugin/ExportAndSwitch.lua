local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrView = import 'LrView'
local LrTasks = import 'LrTasks'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local LrExportSession = import 'LrExportSession'
local LrProgressScope = import 'LrProgressScope'
local LrPrefs = import 'LrPrefs'
local LrColor = import 'LrColor'

local homeDir = LrPathUtils.getStandardFilePath('home') or '/Users/mitch'
local pluginDir = _PLUGIN.path
local prefs = LrPrefs.prefsForPlugin()

local function scanDirectoryForLrcat(dirPath)
    if not LrFileUtils.exists(dirPath) then return nil end
    local lrcatPath = nil
    pcall(function()
        for entry in LrFileUtils.directoryEntries(dirPath) do
            local ext = string.lower(LrPathUtils.extension(entry) or "")
            local leaf = LrPathUtils.leafName(entry) or ""
            if ext == "lrcat" and not string.match(leaf, "^%._") then
                lrcatPath = entry
                break
            end
        end
    end)
    return lrcatPath
end

local function discoverCatalogs()
    local catalogs = {}
    local seen = {}

    local targetDefs = {
        {
            key = "landscape_keepers",
            name = "Landscape Keepers (Terrestrial)",
            rel_folder = "Landscape Keepers",
            img_subdirs = { "Images" }
        },
        {
            key = "aerial_keepers",
            name = "Aerial Keepers",
            rel_folder = "Aerial Keepers",
            img_subdirs = { "Keepers Images", "Images" }
        },
        {
            key = "family_catalog",
            name = "Family Catalog",
            rel_folder = "Family Catalog",
            img_subdirs = { "Images" }
        },
        {
            key = "pegasus_terrestrial",
            name = "Pegasus Terrestrial Keepers",
            rel_folder = "7 Terestrial Catalog/KEEPERS/Terestrial Keepers ",
            img_subdirs = { "Images/Landscape and Pano Keepers", "Images" }
        }
    }

    -- 1. Scan all mounted volumes in /Volumes dynamically
    local candidateRoots = {}
    pcall(function()
        if LrFileUtils.exists("/Volumes") then
            for vol in LrFileUtils.directoryEntries("/Volumes") do
                if LrFileUtils.exists(vol) == "directory" then
                    table.insert(candidateRoots, vol)
                end
            end
        end
    end)

    -- Also check user home, Pictures, and Desktop
    if homeDir then
        table.insert(candidateRoots, LrPathUtils.child(homeDir, "Pictures"))
        table.insert(candidateRoots, homeDir)
    end

    for _, rootDir in ipairs(candidateRoots) do
        local rootName = LrPathUtils.leafName(rootDir) or "Disk"
        for _, def in ipairs(targetDefs) do
            local folderPath = LrPathUtils.child(rootDir, def.rel_folder)
            if LrFileUtils.exists(folderPath) == "directory" then
                local lrcat = scanDirectoryForLrcat(folderPath)
                if lrcat and not seen[lrcat] then
                    seen[lrcat] = true

                    -- Find images folder
                    local imgFolder = LrPathUtils.child(folderPath, def.img_subdirs[1])
                    for _, sub in ipairs(def.img_subdirs) do
                        local cand = LrPathUtils.child(folderPath, sub)
                        if LrFileUtils.exists(cand) == "directory" then
                            imgFolder = cand
                            break
                        end
                    end

                    table.insert(catalogs, {
                        key = def.key .. "_" .. rootName,
                        name = def.name,
                        volume = rootName,
                        catalog_path = lrcat,
                        images_folder = imgFolder,
                        display_label = string.format("%s [%s]", def.name, rootName)
                    })
                end
            end
        end
    end

    -- 2. Add saved custom catalog if it exists
    if prefs.customCatalogPath and LrFileUtils.exists(prefs.customCatalogPath) then
        local catPath = prefs.customCatalogPath
        local catName = prefs.customCatalogName or LrPathUtils.leafName(catPath)
        local imgFolder = prefs.customImagesFolder or LrPathUtils.parent(catPath)
        table.insert(catalogs, {
            key = "custom_saved",
            name = catName,
            volume = "Custom",
            catalog_path = catPath,
            images_folder = imgFolder,
            display_label = string.format("📂 %s (Saved Custom)", catName),
            is_custom = true
        })
    end

    return catalogs
end

LrTasks.startAsyncTask(function()
    local catalog = LrApplication.activeCatalog()
    if not catalog then
        LrDialogs.message("Keepers Transfer", "No active catalog is currently open in Lightroom Classic.", "warning")
        return
    end

    -- 1. Find 5-star photos in current catalog
    local allFiveStarPhotos = catalog:findPhotos {
        searchDesc = {
            {
                criteria = "rating",
                operation = "==",
                value = 5,
            }
        }
    } or {}

    -- Check user's current selection
    local targetPhotos = catalog:getTargetPhotos() or {}
    local selectedFiveStars = {}
    for _, p in ipairs(targetPhotos) do
        local r = p:getFormattedMetadata("rating") or 0
        if tonumber(r) == 5 then
            table.insert(selectedFiveStars, p)
        end
    end

    local photosToExport = allFiveStarPhotos
    if #allFiveStarPhotos == 0 then
        if #targetPhotos > 0 then
            local confirm = LrDialogs.confirm(
                "No 5★ Photos Found",
                string.format("No 5-star photos were found in this catalog, but you have %d photo(s) selected.\n\nDo you want to export your current selection as Keepers?", #targetPhotos),
                "Export Selected",
                "Cancel"
            )
            if confirm ~= "ok" then return end
            photosToExport = targetPhotos
        else
            LrDialogs.message("Keepers Transfer", "No 5-star (★★★★★) photos found and no photos currently selected.\n\nPlease rate your keepers as 5 Stars (★★★★★) or select the photos you wish to transfer.", "info")
            return
        end
    end

    -- 2. Discover available target catalogs dynamically across all mounted drives
    local availableCatalogs = discoverCatalogs()

    -- 3. Set up UI properties
    local f = LrView.osFactory()
    local props = LrView.makePropertyTable()

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
    props.useSelectedOnly = (#selectedFiveStars > 0 and #selectedFiveStars < #allFiveStarPhotos)
    props.customChosenPath = prefs.customCatalogPath or ""
    props.customPathDisplay = (prefs.customCatalogPath and ("Selected: " .. prefs.customCatalogPath)) or "No custom path selected yet (Click 'Browse...')"

    -- 4. Construct Dialog View
    local catalogRows = {}
    for _, c in ipairs(availableCatalogs) do
        table.insert(catalogRows, f:row {
            f:radio_button {
                title = c.display_label,
                value = LrView.bind 'selectedKey',
                checked_value = c.key,
                font = "<system/bold>",
            },
        })
        table.insert(catalogRows, f:row {
            margin_left = 22,
            f:static_text {
                title = "📁 Catalog: " .. LrPathUtils.leafName(c.catalog_path) .. "\n📥 Images: " .. c.images_folder,
                font = "<system/small>",
                text_color = LrColor(0.35, 0.35, 0.35),
                fill_horizontal = 1,
            },
        })
        table.insert(catalogRows, f:spacer { height = 6 })
    end

    -- Custom Manual Choice Row (Always available!)
    table.insert(catalogRows, f:row {
        f:radio_button {
            title = "📂 Choose Any Catalog (.lrcat) or Folder Manually...",
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
    table.insert(catalogRows, f:row {
        margin_left = 22,
        f:static_text {
            title = LrView.bind 'customPathDisplay',
            font = "<system/small>",
            text_color = LrColor(0.2, 0.45, 0.8),
            fill_horizontal = 1,
        }
    })

    local countText = string.format("Ready to transfer %d photo(s) as full-resolution Keepers (DNG)", #photosToExport)
    if #allFiveStarPhotos > 0 then
        countText = string.format("Found %d photos with 5-star rating (★★★★★)", #allFiveStarPhotos)
        if #selectedFiveStars > 0 and #selectedFiveStars < #allFiveStarPhotos then
            countText = string.format("Found %d selected (and %d total) 5-star photos", #selectedFiveStars, #allFiveStarPhotos)
        end
    end

    local viewContents = f:column {
        bind_to_object = props,
        spacing = f:control_spacing(),
        width = 560,

        f:row {
            f:static_text {
                title = countText,
                font = "<system/bold>",
                fill_horizontal = 1,
            },
        },
        f:separator { fill_horizontal = 1 },
        f:spacer { height = 4 },

        f:static_text {
            title = "Select destination catalog (Dynamic Scan + Custom Choice):",
            font = "<system>",
        },
        f:spacer { height = 4 },

        f:column {
            spacing = 2,
            unpack(catalogRows)
        },

        f:separator { fill_horizontal = 1 },
        f:spacer { height = 4 },

        f:checkbox {
            title = "Automatically close this catalog, open destination, and import photos",
            value = LrView.bind 'autoSwitch',
            font = "<system/bold>",
        },
    }

    -- 5. Present modal dialog
    local action = LrDialogs.presentModalDialog {
        title = "MR Keepers Transfer — Send Keepers to Catalog",
        contents = viewContents,
        actionVerb = "Transfer Keepers (DNG)",
        cancelVerb = "Cancel",
    }

    if action ~= "ok" then
        return
    end

    -- Identify chosen catalog
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
                LrDialogs.message("Keepers Transfer", "No destination catalog or folder was selected.", "warning")
                return
            end
        end

        local catPath = ""
        local imgFolder = ""
        local catName = LrPathUtils.leafName(chosenPath)

        if string.lower(LrPathUtils.extension(chosenPath) or "") == "lrcat" then
            catPath = chosenPath
            local parent = LrPathUtils.parent(chosenPath)
            local candImages = LrPathUtils.child(parent, "Images")
            local candKeepers = LrPathUtils.child(parent, "Keepers Images")
            if LrFileUtils.exists(candImages) == "directory" then
                imgFolder = candImages
            elseif LrFileUtils.exists(candKeepers) == "directory" then
                imgFolder = candKeepers
            else
                imgFolder = parent
            end
        else
            -- Directory selected: check if it contains an .lrcat
            local insideLrcat = scanDirectoryForLrcat(chosenPath)
            if insideLrcat then
                catPath = insideLrcat
                catName = LrPathUtils.leafName(insideLrcat)
                local candImages = LrPathUtils.child(chosenPath, "Images")
                if LrFileUtils.exists(candImages) == "directory" then
                    imgFolder = candImages
                else
                    imgFolder = chosenPath
                end
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
            display_label = catName
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
        LrDialogs.message("Keepers Transfer", "Invalid catalog selection.", "warning")
        return
    end

    -- Save user preferences
    prefs.lastTargetCatalogKey = props.selectedKey
    prefs.lastAutoSwitch = props.autoSwitch

    -- Determine which photos to export
    if props.useSelectedOnly and #selectedFiveStars > 0 then
        photosToExport = selectedFiveStars
    end

    if #photosToExport == 0 then
        LrDialogs.message("Keepers Transfer", "No photos available to export.", "warning")
        return
    end

    -- Ensure destination image directory exists
    LrFileUtils.createAllDirectories(chosenCatalog.images_folder)

    -- 6. Export photos as DNG with edits embedded
    local exportSettings = {
        LR_format = 'DNG',
        LR_export_destinationType = 'specificFolder',
        LR_export_destinationPathPrefix = chosenCatalog.images_folder,
        LR_export_useSubfolder = false,
        LR_collisionHandling = 'rename',
        LR_reimportExportedPhoto = false,
    }

    local exportSession = LrExportSession {
        photosToExport = photosToExport,
        exportSettings = exportSettings,
    }

    local progressScope = LrProgressScope {
        title = string.format("Exporting %d Keepers as DNG to %s...", #photosToExport, chosenCatalog.name),
    }

    local exportedDngs = {}
    for _, rendition in exportSession:renditions({ stopIfCanceled = true }) do
        local success, pathOrMsg = rendition:waitForRender()
        if success then
            table.insert(exportedDngs, pathOrMsg)
        end
    end
    progressScope:done()

    if #exportedDngs == 0 then
        LrDialogs.message("Keepers Transfer", "Export did not produce any DNG files or was cancelled.", "warning")
        return
    end

    -- 7. Write queue manifest file
    local queueData = string.format('{\n  "target_catalog": "%s",\n  "catalog_name": "%s",\n  "photos": [\n',
        chosenCatalog.catalog_path:gsub('\\', '\\\\'),
        chosenCatalog.name:gsub('"', '\\"')
    )
    for i, p in ipairs(exportedDngs) do
        queueData = queueData .. string.format('    "%s"%s\n', p:gsub('\\', '\\\\'), (i < #exportedDngs and "," or ""))
    end
    queueData = queueData .. '  ]\n}\n'

    local localQueuePath = LrPathUtils.child(homeDir, "Library/Application Support/MRDarkroom/keeper_import_queue.json")
    LrFileUtils.createAllDirectories(LrPathUtils.parent(localQueuePath))
    LrFileUtils.writeFile(localQueuePath, queueData)

    -- Also save queue to parent of images folder if accessible
    pcall(function()
        local parentDir = LrPathUtils.parent(chosenCatalog.images_folder)
        if parentDir and LrFileUtils.exists(parentDir) then
            LrFileUtils.writeFile(LrPathUtils.child(parentDir, ".keeper_import_queue.json"), queueData)
        end
    end)

    -- 8. Check if current catalog is ALREADY the destination catalog
    local currentCatPath = catalog:getPath()
    local isSameCatalog = (#chosenCatalog.catalog_path > 0) and (
                          (currentCatPath == chosenCatalog.catalog_path) or
                          (LrPathUtils.leafName(currentCatPath) == LrPathUtils.leafName(chosenCatalog.catalog_path))
    )

    if isSameCatalog then
        -- Ingest directly right now!
        local importedPhotos = {}
        catalog:withWriteAccessDo("Import Keepers Directly", function(context)
            for _, dngPath in ipairs(exportedDngs) do
                local photo = catalog:addPhoto(dngPath)
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

        pcall(function() LrFileUtils.delete(localQueuePath) end)

        if #importedPhotos > 0 then
            catalog:setSelectedPhotos(importedPhotos[1], importedPhotos)
            LrDialogs.showBezel(string.format("✓ %d Keepers imported into %s!", #importedPhotos, chosenCatalog.name), 4)
        end
        return
    end

    -- 9. Handle automatic catalog switch or notify user
    if props.autoSwitch and #chosenCatalog.catalog_path > 0 then
        LrDialogs.showBezel(string.format("✓ Exported %d Keepers! Switching to %s...", #exportedDngs, chosenCatalog.name), 3)
        LrTasks.sleep(0.5)

        local switchScript = LrPathUtils.child(pluginDir, "switch_catalog.sh")
        local cmd = string.format('/bin/bash "%s" "%s" > /dev/null 2>&1 &', switchScript, chosenCatalog.catalog_path)
        pcall(function() LrTasks.execute(cmd) end)
    else
        LrDialogs.message("Keepers Exported", string.format("Successfully exported %d DNG keepers to:\n%s\n\nWhen you open '%s', they will be imported automatically.", #exportedDngs, chosenCatalog.images_folder, chosenCatalog.name), "info")
    end
end)
