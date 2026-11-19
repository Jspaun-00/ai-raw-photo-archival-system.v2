return {
    LrSdkVersion = 11.0,
    LrSdkMinimumVersion = 6.0,
    LrToolkitIdentifier = 'com.mrdarkroom.keeperstransfer',
    LrPluginName = 'MR Keepers Transfer (5★ to Catalog)',
    LrInitPlugin = 'Init.lua',
    LrForceInitPlugin = true,
    VERSION = { major = 2, minor = 0, revision = 0 },
    LrLibraryMenuItems = {
        {
            title = "Send 5★ Keepers to Destination Catalog...",
            file = "ExportAndSwitch.lua",
        },
    },
    LrFileMenuItems = {
        {
            title = "Send 5★ Keepers to Destination Catalog...",
            file = "ExportAndSwitch.lua",
        },
    },
}
