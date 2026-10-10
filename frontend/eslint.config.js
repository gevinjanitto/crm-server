const js = require('@eslint/js');
const globals = require('globals');
const react = require('eslint-plugin-react');
module.exports = [
  { ignores: ['node_modules/**', 'build/**', 'public/**', 'plugins/**'] },
  { files: ['src/**/*.{js,jsx}'], languageOptions: { ecmaVersion: 'latest', sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } }, globals: { ...globals.browser, ...globals.jest, process: 'readonly' } }, plugins: { react }, settings: { react: { version: 'detect' } }, rules: { ...js.configs.recommended.rules, 'no-unused-vars': 'off', 'react/jsx-uses-react': 'error', 'react/jsx-uses-vars': 'error' } },
];