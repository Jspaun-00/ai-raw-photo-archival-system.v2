return {
    LrSdkVersion = 11.0,
    LrToolkitIdentifier = 'com.mrdarkroom.keeperstransfer',
    LrPluginName = 'MR Keepers Transfer (5★ to Catalog)',
    VERSION = { major = 1, minor = 0, revision = 0 },
    LrLibraryMenuItems = {
        {
            title = "Send 5★ Keepers to Destination Catalog...",
            file = "ExportAndSwitch.lua",
        },
        {
            title = "Check & Import Pending Keepers Now",
            file = "ManualImport.lua",
        },
    },
    LrFileMenuItems = {
        {
            title = "Send 5★ Keepers to Destination Catalog...",
            file = "ExportAndSwitch.lua",
        },
        {
            title = "Check & Import Pending Keepers Now",
            file = "ManualImport.lua",
        },
    },
}
