/**
 * CARFul - Electron Forge Configuration
 *
 * Configures how the application is packaged and distributed.
 */

const { FusesPlugin } = require('@electron-forge/plugin-fuses');
const { FuseV1Options, FuseVersion } = require('@electron/fuses');

module.exports = {
  packagerConfig: {
    name: 'CARFul',
    executableName: 'carful',
    appBundleId: 'com.carful.app',
    appCategoryType: 'public.app-category.business',
    icon: './resources/icon',
    asar: true,
    // Extra resources to include
    extraResource: [
      '../carful',           // Python backend
      './resources',         // App resources
      './resources/python-win', // Bundled Python for Windows (only present in CI builds)
    ],
    // Files to ignore in packaging
    ignore: [
      /node_modules\/.*\/test/,
      /node_modules\/.*\/tests/,
      /node_modules\/.*\/\.git/,
      /\.git/,
      /\.gitignore/,
      /README\.md/,
      /\.env/,
    ],
  },
  rebuildConfig: {},
  makers: [
    // macOS DMG
    {
      name: '@electron-forge/maker-dmg',
      config: {
        name: 'CARFul',
        icon: './resources/icon.icns',
        background: './resources/dmg-background.png',
        format: 'ULFO',
      },
    },
    // macOS ZIP (for auto-update)
    {
      name: '@electron-forge/maker-zip',
      platforms: ['darwin'],
    },
    // Windows installer
    {
      name: '@electron-forge/maker-squirrel',
      config: {
        name: 'CARFul',
        authors: 'CARFul',
        description: 'CARF XML Generation Tool for Crypto Asset Reporting',
        iconUrl: 'https://carful.com/icon.ico',
        setupIcon: './resources/icon.ico',
      },
    },
    // Linux DEB
    {
      name: '@electron-forge/maker-deb',
      config: {
        options: {
          name: 'carful',
          productName: 'CARFul',
          genericName: 'CARF Compliance Tool',
          description: 'CARF XML Generation Tool for Crypto Asset Reporting',
          categories: ['Office', 'Finance'],
          icon: './resources/icon.png',
        },
      },
    },
  ],
  plugins: [
    {
      name: '@electron-forge/plugin-auto-unpack-natives',
      config: {},
    },
    // Fuses are used to enable/disable various Electron functionality
    new FusesPlugin({
      version: FuseVersion.V1,
      [FuseV1Options.RunAsNode]: false,
      [FuseV1Options.EnableCookieEncryption]: true,
      [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
      [FuseV1Options.EnableNodeCliInspectArguments]: false,
      [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
      [FuseV1Options.OnlyLoadAppFromAsar]: true,
    }),
  ],
  publishers: [
    {
      name: '@electron-forge/publisher-github',
      config: {
        repository: {
          owner: 'carful',
          name: 'carful',
        },
        prerelease: false,
      },
    },
  ],
};
