module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',    // New feature
        'fix',     // Bug fix
        'docs',    // Documentation
        'style',   // Code style
        'refactor',// Code refactoring
        'test',    // Tests
        'chore',   // Maintenance
        'ci',      // CI/CD changes
        'perf'     // Performance improvements
      ]
    ]
  }
}; 